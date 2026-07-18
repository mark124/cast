"""Prove the B2 credentials, region, and bucket actually work — end to end.

Runs the smallest real exercise of every operation the pipeline will depend on:
put -> exists -> get (bytes match) -> list -> delete. If auth, region, or the
bucket name is wrong, this fails here — loudly, in seconds — instead of deep
inside a pipeline run.

Reads B2_* from the environment or ../.env. Writes and then deletes one tiny
object under cast/_selftest/, so it leaves the bucket as it found it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from genblaze_s3 import S3StorageBackend

HERE = Path(__file__).resolve().parent


def load_env() -> None:
    env = HERE.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    load_env()
    missing = [v for v in ("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET", "B2_REGION")
               if not os.getenv(v)]
    if missing:
        sys.exit(f"missing in .env: {', '.join(missing)}")

    bucket = os.environ["B2_BUCKET"]
    region = os.environ["B2_REGION"]
    print(f"bucket   : {bucket}")
    print(f"region   : {region}   (must be passed explicitly; auto-detect 403s on B2)")

    # preflight=True makes the constructor verify access before returning, so a bad
    # key or region surfaces here rather than on first put.
    backend = S3StorageBackend.for_backblaze(
        bucket,
        region=region,
        key_id=os.environ["B2_KEY_ID"],
        app_key=os.environ["B2_APP_KEY"],
        preflight=True,
    )
    print("preflight: OK (credentials + bucket + region accepted)")

    key = "cast/_selftest/roundtrip.txt"
    payload = b"cast b2 roundtrip - safe to delete\n"

    try:
        backend.put(key, payload, content_type="text/plain")
        print(f"put      : {key} ({len(payload)} bytes)")

        assert backend.exists(key), "object not found immediately after put"
        print("exists   : True")

        got = backend.get(key)
        got_bytes = got if isinstance(got, (bytes, bytearray)) else got.read()
        assert got_bytes == payload, "downloaded bytes != uploaded bytes"
        print(f"get      : bytes match ({len(got_bytes)} bytes)")

        page = backend.list(prefix="cast/_selftest/")
        print(f"list     : {len(page.entries)} object(s) under cast/_selftest/")
    finally:
        backend.delete(key)
        print("delete   : cleaned up")

    print()
    print("B2 is live. Storage step unblocked.")


if __name__ == "__main__":
    main()
