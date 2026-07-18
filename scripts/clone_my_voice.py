"""Clone a real voice to both providers and wire it into Cast as a selectable voice.

Give it a clean 30 to 60 second recording of one speaker (wav or mp3). It clones
that voice on ElevenLabs (the primary) and LMNT (the failover), then writes both
ids into custom_voices.json at the project root. synthesize.py loads that file, so
the voice appears in the app's voice picker after the next server restart.

Usage (from the project root, venv active):
    python scripts/clone_my_voice.py path/to/you.wav mark "Mark (my voice)"

Args: <sample> [key] [label]. key defaults to "mine"; label is what shows in the UI.

Consent note: only clone a voice you have the right to use, which for this tool is
your own. Cloning a third party needs their consent, and the providers' terms
require it.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit("usage: python scripts/clone_my_voice.py <sample.wav> [key] [label]")
    sample = pathlib.Path(args[0])
    if not sample.exists():
        sys.exit(f"sample not found: {sample}")
    key = args[1] if len(args) > 1 else "mine"
    label = args[2] if len(args) > 2 else f"{key} (cloned)"

    print(f"cloning '{sample.name}' as '{key}' ...")

    # ElevenLabs (primary). Instant Voice Cloning needs a paid tier (Starter is fine).
    from elevenlabs.client import ElevenLabs

    el = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    with sample.open("rb") as fh:
        el_resp = el.voices.ivc.create(name=f"cast-{key}", files=[fh])
    el_id = el_resp.voice_id
    print(f"  ElevenLabs voice_id: {el_id}")

    # LMNT (failover). Cloning is available on the free tier.
    from lmnt import Lmnt

    lm = Lmnt(api_key=os.environ["LMNT_API_KEY"])
    with sample.open("rb") as fh:
        lm_voice = lm.voices.create(file=fh, name=f"cast-{key}")
    lm_id = getattr(lm_voice, "id", None) or getattr(lm_voice, "voice", None)
    print(f"  LMNT voice id: {lm_id}")

    # Wire it in.
    out = ROOT / "custom_voices.json"
    data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    data[key] = {"elevenlabs_id": el_id, "lmnt_id": str(lm_id), "label": label}
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print()
    print(f"wired into {out.name}. Restart the server and '{label}' is in the voice picker.")
    print("Note: a cloned voice on ElevenLabs + LMNT is the same source sample on both,")
    print("so failover keeps the actual voice identity, not just the gender.")


if __name__ == "__main__":
    main()
