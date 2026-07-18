"""Backblaze B2 as the pipeline's system of record.

Every localized cut and its manifest land in B2 through Genblaze's ObjectStorageSink.
Two deliberate choices:

  * CONTENT_ADDRESSABLE keys — assets stored at assets/<sha256[:2]>/<sha256[2:4]>/
    <sha256>.ext, manifests at manifests/<run_id>.json. Byte-identical output dedupes
    for free, and the key *is* the integrity check.

  * The sink hashes asset bytes on transfer. The ElevenLabs connector doesn't set
    sha256 on its file:// assets, so before upload Manifest.verify() fails on them;
    after the sink transfers the bytes into B2 it fills sha256 in and verify() passes.
    That's the moment a cut becomes provenance-complete.

Object Lock (manifest_lock) makes the manifest immutable for a retention window — the
audit anchor a publisher needs. It requires Object Lock enabled on the bucket, which is
an irreversible bucket setting, so it's opt-in here rather than on by default.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from genblaze_core import KeyStrategy, ObjectStorageSink

DEFAULT_PREFIX = "cast"


def b2_backend(**overrides: Any):
    """Build the B2 S3 backend from the B2_* environment, failing fast on bad creds.

    Region must be passed explicitly — B2's us-east-005 returns 403 to the
    region-autodetect probe instead of the 301 the SDK expects, so autodetect
    silently fails there.
    """
    from genblaze_s3 import S3StorageBackend

    kwargs = dict(
        bucket=os.environ["B2_BUCKET"],
        region=os.environ["B2_REGION"],
        key_id=os.environ["B2_KEY_ID"],
        app_key=os.environ["B2_APP_KEY"],
        preflight=True,
    )
    kwargs.update(overrides)
    return S3StorageBackend.for_backblaze(**kwargs)


def b2_sink(
    *,
    prefix: str = DEFAULT_PREFIX,
    lock_days: int | None = None,
    backend: Any = None,
) -> ObjectStorageSink:
    """A content-addressable B2 sink. Pass lock_days to make manifests immutable.

    lock_days requires Object Lock enabled on the bucket; leave it None until the
    bucket has it turned on.
    """
    backend = backend or b2_backend()
    manifest_lock = None
    if lock_days is not None:
        from genblaze_core import ObjectLockConfig

        retain_until = datetime.now(timezone.utc) + timedelta(days=lock_days)
        manifest_lock = ObjectLockConfig(retain_until=retain_until)

    return ObjectStorageSink(
        backend,
        prefix=prefix,
        key_strategy=KeyStrategy.CONTENT_ADDRESSABLE,
        manifest_lock=manifest_lock,
    )
