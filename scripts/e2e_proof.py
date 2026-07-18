"""End-to-end proof on the real source clip: translate -> speak, with failover.

Uses a short excerpt of the real Coleman transcript (already verified against
AssemblyAI) so this stays fast and cheap while exercising the whole back half of
the pipeline against live providers:

  1. translate the excerpt into a few languages with Claude (a real Genblaze step)
  2. synthesize each with ElevenLabs primary -> LMNT failover, in one voice
  3. force ElevenLabs to fail and confirm LMNT takes over and still produces audio

Writes mp3s to work/e2e/. Run from cast/ with the venv active.
"""

from __future__ import annotations

import os
import pathlib
import sys

# Windows consoles default to cp1252 and choke on translated text (Japanese, etc.).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from cast.failover import Attempt  # noqa: E402
from cast.genblaze_anthropic import text_of  # noqa: E402
from cast.synthesize import DEMO_VOICE_FEMALE, speak  # noqa: E402
from cast.translate import translate_text  # noqa: E402

# Real first two sentences of the Coleman clip (verified via AssemblyAI).
EXCERPT = (
    "I think it's human nature to explore. I don't actually think you could stop "
    "people from doing it, even if you'd like to."
)
LANGS = ["es", "fr", "ja"]
OUT = ROOT / "work" / "e2e"
VOICE = DEMO_VOICE_FEMALE


def narrate(a: Attempt) -> None:
    mark = "OK" if a.ok else f"failed ({a.error_code.value if a.error_code else '?'})"
    print(f"      {a.label:32} {mark}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f'source excerpt: "{EXCERPT}"')
    print(f"voice: {VOICE.label} (elevenlabs={VOICE.elevenlabs_id[:8]}.. / lmnt={VOICE.lmnt_id})")
    print()

    for lang in LANGS:
        print(f"[{lang}] translating with Claude ...")
        tr = translate_text(EXCERPT, lang)
        text = text_of(tr.run.steps[0])
        print(f'      -> "{text}"')

        print(f"[{lang}] speaking (ElevenLabs -> LMNT failover) ...")
        res = speak(text, language=lang, voice=VOICE, output_dir=OUT, parent=tr, on_attempt=narrate)
        asset = res.assets[0]
        path = asset.url.replace("file://", "")
        # Rename to a friendly name for listening.
        friendly = OUT / f"{lang}_{res.winner.provider.name}.mp3"
        pathlib.Path(_unquote(path)).replace(friendly)
        print(f"      won on {res.winner.provider.name}; wrote {friendly.name} "
              f"({asset.size_bytes:,} bytes); manifest verify_hash={res.manifest.verify_hash()}")
        print(f"      lineage: run parent_run_id set? {res.run.parent_run_id is not None}")
        print()

    # --- the demo's kill shot: pull the primary key, watch LMNT take over --------
    print("FAILOVER TEST — ElevenLabs key deliberately broken:")
    res = speak(
        "Esta es la voz de respaldo.",
        language="es",
        voice=VOICE,
        output_dir=OUT,
        on_attempt=narrate,
        elevenlabs_key="sk_intentionally_invalid",
    )
    print(f"   recovered on: {res.winner.provider.name} (failed_over={res.failed_over})")
    assert res.ok and res.winner.provider.name == "lmnt", "failover did not reach LMNT"
    print("   PASS — the localized cut still gets made when the primary is down.")


def _unquote(p: str) -> str:
    from urllib.parse import unquote

    return unquote(p)


if __name__ == "__main__":
    main()
