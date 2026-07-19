"""Assemble per-segment speech into one timed track, and mux onto the source.

Each localized segment is placed at the source segment's start time, so the dub
tracks the original's pacing. Sync is segment-level (AssemblyAI timing is ~400ms
accurate) — right for podcasts/audiobooks/narration, where there are no lips to
match.

ffmpeg does the placing: adelay shifts each segment audio to its start offset, amix
sums them onto a common timeline (normalize=0 so summing doesn't duck the volume),
apad+atrim pin the result to the source duration.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


@dataclass(frozen=True)
class Placement:
    start: float  # seconds into the timeline
    audio_path: Path


class FfmpegError(RuntimeError):
    pass


def _run(args: list[str]) -> None:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FfmpegError(f"ffmpeg failed ({proc.returncode}):\n{proc.stderr[-1500:]}")


def assemble_track(
    placements: list[Placement],
    out_path: str | Path,
    *,
    total_duration: float | None = None,
    zero_base: bool = True,
    lead_in: float = 0.25,
    sample_rate: int = 44100,
) -> Path:
    """Lay each placement's audio at its start offset into one mp3.

    zero_base (default) shifts the whole timeline so the first segment starts at
    `lead_in` seconds instead of its absolute source time — right for an audio-only
    deliverable (a podcast/audiobook has no video to sync to, and leading silence
    reads as a broken file). Set zero_base=False to preserve absolute source timing
    for muxing onto the source video, and pass total_duration to pad/pin the length.
    """
    placements = [p for p in placements if Path(p.audio_path).exists()]
    if not placements:
        raise FfmpegError("no segment audio to assemble")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    args: list[str] = [FFMPEG, "-y"]
    for p in placements:
        args += ["-i", str(Path(p.audio_path).resolve())]

    base = max(0.0, min(p.start for p in placements) - lead_in) if zero_base else 0.0

    # Per input: resample to a common rate, then delay to its (rebased) start time.
    parts: list[str] = []
    labels: list[str] = []
    for i, p in enumerate(placements):
        delay_ms = max(0, int(round((p.start - base) * 1000)))
        parts.append(f"[{i}:a]aresample={sample_rate},adelay={delay_ms}|{delay_ms}[a{i}]")
        labels.append(f"[a{i}]")

    graph = list(parts)
    if len(placements) == 1:
        mixed = "a0"  # amix needs >=2 inputs; a single delayed stream is already the mix
    else:
        graph.append(f"{''.join(labels)}amix=inputs={len(placements)}:normalize=0[mixed]")
        mixed = "mixed"

    # Only force a fixed length when matching a video timeline; a zero-based audio
    # track just ends when the last segment does (amix already spans exactly that).
    if not zero_base and total_duration:
        graph.append(f"[{mixed}]apad,atrim=0:{total_duration:.3f}[out]")
        out_label = "out"
    else:
        out_label = mixed

    args += [
        "-filter_complex", ";".join(graph),
        "-map", f"[{out_label}]",
        "-ac", "2",
        "-c:a", "libmp3lame", "-q:a", "2",
        str(out_path.resolve()),
    ]
    _run(args)
    return out_path


def mux_video(
    source_video: str | Path,
    audio_path: str | Path,
    out_path: str | Path,
) -> Path:
    """Replace the source video's audio with `audio_path` (video copied, not re-encoded)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run([
        FFMPEG, "-y",
        "-i", str(Path(source_video).resolve()),
        "-i", str(Path(audio_path).resolve()),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_path.resolve()),
    ])
    return out_path


def apply_tempo(path: str | Path, factor: float) -> Path:
    """Ease (or quicken) an audio file's pace in place, without changing pitch.

    factor < 1 slows down, > 1 speeds up; ~1.0 is a no-op. Localized speech tends to
    run fast because translations expand over the source (Romance and German add
    ~20-30% more words for the same meaning) and the TTS packs them into the same air.
    A gentle slow-down lets a dub breathe. ffmpeg's atempo preserves pitch, so the
    cloned voice identity is unchanged. atempo takes 0.5-2.0 in one pass, which covers
    every pace we use.
    """
    path = Path(path)
    if abs(factor - 1.0) < 1e-3:
        return path
    tmp = path.with_name(f"{path.stem}.tempo{path.suffix}")
    _run([
        FFMPEG, "-y", "-i", str(path.resolve()),
        "-filter:a", f"atempo={factor:.4f}",
        "-c:a", "libmp3lame", "-q:a", "2",
        str(tmp.resolve()),
    ])
    tmp.replace(path)
    return path


def probe_duration(path: str | Path) -> float:
    ffprobe = shutil.which("ffprobe") or "ffprobe"
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(Path(path).resolve())],
        capture_output=True, text=True,
    )
    try:
        return float(proc.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0
