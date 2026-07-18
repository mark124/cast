"""LMNT text-to-speech on the lmnt>=2 SDK, as a Genblaze Pipeline step.

The shipped genblaze_lmnt connector imports the pre-2.0 `lmnt.api` layout and breaks
on the current package; this is the 2.x-compatible replacement. See
docs/upstream-findings.md #7.
"""

from .provider import DEFAULT_MODEL, DEFAULT_VOICE, LmntTTSProvider

__all__ = ["LmntTTSProvider", "DEFAULT_MODEL", "DEFAULT_VOICE"]
