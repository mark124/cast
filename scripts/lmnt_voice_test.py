"""Does one LMNT voice keep its identity across languages?

The whole backup-voice story rests on this: when the primary TTS provider stalls
and we fail over to LMNT, the localized cut must still sound like the *same
speaker*. LMNT documents multilingual synthesis but not whether a single voice
preserves its timbre across languages. This settles it by ear.

Two modes:

  builtin  (default) — one built-in LMNT voice speaks the same sentence in six
           Tier-1 languages. No audio upload needed. Answers: does LMNT's model
           hold a voice's identity across languages at all?

  clone <sample.wav> — clone a voice from a ~20-60s clean speech sample, then do
           the same sweep with the clone. This is the definitive test, because
           the product fails over into a *cloned* voice, not a built-in one.

Usage (from cast/, with the venv active):
    python scripts/lmnt_voice_test.py                 # auto-pick a built-in voice
    python scripts/lmnt_voice_test.py builtin <voice> # a specific built-in voice
    python scripts/lmnt_voice_test.py list            # list voices (name/gender/id)
    python scripts/lmnt_voice_test.py clone path/to/sample.wav

Reads LMNT_API_KEY from the environment or ../.env. Costs a few cents at most.
Writes .mp3 files to work/lmnt_test/ — listen and ask yourself: same person?
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from lmnt import Lmnt

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "work" / "lmnt_test"

# One sentence, translated per language, spanning Latin / Japanese scripts and
# the RTL-adjacent set. Same meaning everywhere so the *voice* is what varies.
SENTENCE = {
    "en": "This is the same voice, speaking your language.",
    "es": "Esta es la misma voz, hablando tu idioma.",
    "fr": "C'est la même voix, qui parle votre langue.",
    "de": "Das ist dieselbe Stimme, die deine Sprache spricht.",
    "pt": "Esta é a mesma voz, falando o seu idioma.",
    "ja": "これは同じ声で、あなたの言語を話しています。",
}


def load_key() -> str:
    key = os.getenv("LMNT_API_KEY")
    if key:
        return key
    env = HERE.parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("LMNT_API_KEY=") and not line.startswith("#"):
                value = line.split("=", 1)[1].strip()
                if value:
                    return value
    sys.exit("LMNT_API_KEY not set (env or ../.env). Add it and re-run.")


def pick_builtin_voice(client: Lmnt) -> str:
    """Choose a built-in voice, preferring one flagged multilingual."""
    voices = client.voices.list()
    items = list(getattr(voices, "voices", None) or voices)
    if not items:
        sys.exit("LMNT returned no voices — check the key/account.")

    def is_multilingual(v) -> bool:
        blob = " ".join(str(getattr(v, f, "")) for f in ("languages", "tags", "description")).lower()
        return "multi" in blob or "en" in getattr(v, "languages", []) and len(getattr(v, "languages", [])) > 1

    chosen = next((v for v in items if is_multilingual(v)), items[0])
    vid = getattr(chosen, "id", None) or getattr(chosen, "voice", None) or getattr(chosen, "name")
    print(f"  using built-in voice: {getattr(chosen, 'name', vid)} ({vid})")
    print(f"  ({len(items)} voices available on this account)")
    return str(vid)


def clone_voice(client: Lmnt, sample: Path) -> str:
    if not sample.exists():
        sys.exit(f"sample not found: {sample}")
    print(f"  cloning from {sample.name} ...")
    with sample.open("rb") as fh:
        voice = client.voices.create(file=fh, name="cast-clone-test")
    vid = getattr(voice, "id", None) or getattr(voice, "voice", None)
    print(f"  cloned voice id: {vid}")
    return str(vid)


def synth_sweep(client: Lmnt, voice: str, tag: str) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for lang, text in SENTENCE.items():
        # model='blizzard' is LMNT's multilingual model; language= enforces the
        # target rather than letting it auto-detect from the text.
        audio = client.speech.generate(text=text, voice=voice, language=lang,
                                       model="blizzard", format="mp3")
        out = OUT_DIR / f"{tag}_{lang}.mp3"
        out.write_bytes(audio.read())
        written.append(out)
        print(f"    {lang}: {out.name}  ({out.stat().st_size:,} bytes)")
    return written


def list_voices(client: Lmnt) -> None:
    voices = client.voices.list()
    items = list(getattr(voices, "voices", None) or voices)
    print(f"{len(items)} voices:")
    for v in items:
        vid = getattr(v, "id", None) or getattr(v, "voice", None) or getattr(v, "name")
        gender = getattr(v, "gender", "") or ""
        langs = getattr(v, "languages", "") or ""
        print(f"  {str(vid):24} {str(gender):8} {getattr(v, 'name', ''):16} {langs}")


def main() -> None:
    args = sys.argv[1:]
    mode = args[0] if args else "builtin"
    client = Lmnt(api_key=load_key())

    if mode == "list":
        list_voices(client)
        return

    if mode == "builtin":
        print("LMNT cross-lingual voice test — built-in voice")
        voice = args[1] if len(args) > 1 else pick_builtin_voice(client)
        if len(args) > 1:
            print(f"  using requested voice: {voice}")
        files = synth_sweep(client, voice, f"builtin_{voice}")
    elif mode == "clone":
        if len(args) < 2:
            sys.exit("usage: python scripts/lmnt_voice_test.py clone <sample.wav>")
        print("LMNT cross-lingual voice test — cloned voice")
        voice = clone_voice(client, Path(args[1]))
        files = synth_sweep(client, voice, "clone")
    else:
        sys.exit(f"unknown mode {mode!r} — use 'builtin' or 'clone'")

    print()
    print(f"Wrote {len(files)} files to {OUT_DIR}")
    print("Listen in language order. The question is only: does it sound like the")
    print("same speaker in every clip? If yes, LMNT is a viable voice-preserving")
    print("backup. If it swaps to a generic voice in some languages, it is not.")


if __name__ == "__main__":
    main()
