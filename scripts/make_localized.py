"""Produce a finished localized video from the source clip, one language, end to end.

transcribe (cached) -> segment -> translate -> speak each segment (failover) ->
assemble a timed track -> mux onto the source video.

Usage (from cast/, venv active):
    python scripts/make_localized.py es
    python scripts/make_localized.py fr --voice male
"""

from __future__ import annotations

import os
import pathlib
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from cast.assemble import probe_duration  # noqa: E402
from cast.localize import localize_language  # noqa: E402
from cast.synthesize import DEMO_VOICE_FEMALE, DEMO_VOICE_MALE  # noqa: E402
from cast.transcribe import transcribe  # noqa: E402

SOURCE_VIDEO = ROOT / "work" / "source" / "coleman.mp4"
SOURCE_AUDIO = ROOT / "work" / "source" / "coleman.wav"
CACHE = ROOT / "work" / "transcript.json"
OUT = ROOT / "work" / "localized"


def main() -> None:
    args = sys.argv[1:]
    lang = args[0] if args else "es"
    voice = DEMO_VOICE_MALE if "--voice" in args and "male" in args else DEMO_VOICE_FEMALE

    print(f"transcribing {SOURCE_AUDIO.name} (cached: {CACHE.exists()}) ...")
    transcript, run = transcribe(SOURCE_AUDIO, cache_path=CACHE)
    print(f"  {len(transcript.segments)} segments, {transcript.duration:.0f}s source")
    for s in transcript.segments[:3]:
        print(f"    [{s.start:5.1f}-{s.end:5.1f}] {s.text[:60]}")
    print()

    def progress(stage: str, detail: dict) -> None:
        if stage == "speak.done":
            fo = " (failed over)" if detail.get("failed_over") else ""
            print(f"  spoke segment {detail['segment']} via {detail['provider']}{fo}")
        elif stage in ("translate.done", "assemble.done", "mux.done"):
            print(f"  {stage}: {detail.get('segments', detail.get('path',''))}")

    print(f"localizing -> {lang} (voice: {voice.label}) ...")
    result = localize_language(
        transcript, lang,
        voice=voice, out_dir=OUT,
        source_video=SOURCE_VIDEO, parent=run,
        on_progress=progress,
    )

    print()
    print(f"audio: {result.audio_path}  ({probe_duration(result.audio_path):.1f}s)")
    print(f"video: {result.video_path}  ({probe_duration(result.video_path):.1f}s)")
    print(f"segments spoken: {len(result.segment_texts)} | failovers: {result.failovers}")
    print(f"source duration: {transcript.duration:.1f}s  (localized should track it)")


if __name__ == "__main__":
    main()
