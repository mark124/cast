"""Localize one source into one language, end to end.

Ties the stages together for a single language:
  translate the segments -> speak each at its source time -> assemble the track
  -> (optionally) mux onto the source video -> (optionally) store in B2.

The whole per-language pipeline hangs off the transcription run for provenance:
every translation and every spoken segment carries parent_run_id back to it, so a
finished cut can be traced to the master it came from.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .assemble import Placement, apply_tempo, assemble_track, mux_video, probe_duration
from .genblaze_anthropic import text_of
from .languages import Language, get
from .synthesize import Voice, pace_for, speak
from .transcribe import Transcript
from .translate import translate_segments

# Progress event: (stage, detail) — the SSE app renders these live.
ProgressFn = Callable[[str, dict], None]


@dataclass
class LocalizedLanguage:
    language: str
    audio_path: Path | None = None
    video_path: Path | None = None
    segment_texts: list[str] = field(default_factory=list)
    failovers: int = 0  # how many segments had to fail over to the backup provider
    b2_urls: list[str] = field(default_factory=list)
    segments: list[dict] = field(default_factory=list)  # caption timing: id/source/target/start/dur


def localize_language(
    transcript: Transcript,
    target: str | Language,
    *,
    voice: Voice,
    out_dir: Path,
    source_video: Path | None = None,
    parent: Any = None,
    sink: Any = None,
    on_progress: ProgressFn | None = None,
    elevenlabs_key: str | None = None,
    lmnt_key: str | None = None,
) -> LocalizedLanguage:
    lang = target if isinstance(target, Language) else get(target)
    seg_dir = out_dir / lang.code / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    def emit(stage: str, **detail: Any) -> None:
        if on_progress:
            on_progress(stage, {"language": lang.code, **detail})

    # 1. translate segments (ids preserved, so timings still map)
    emit("translate.start")
    src_segments = [{"id": s.id, "text": s.text} for s in transcript.segments]
    translated = translate_segments(src_segments, lang, parent=parent)
    by_id = {t["id"]: t["text"] for t in translated}
    emit("translate.done", segments=len(translated))

    # 2. speak each segment
    texts: list[str] = []
    failovers = 0
    b2_urls: list[str] = []
    recorded: list[tuple] = []  # (segment, target_text, local_audio_path) for captions
    for seg in transcript.segments:
        text = by_id.get(seg.id, "").strip()
        if not text:
            continue
        emit("speak.start", segment=seg.id)
        res = speak(
            text, language=lang.code, voice=voice,
            output_dir=seg_dir, parent=parent, sink=sink,
            elevenlabs_key=elevenlabs_key, lmnt_key=lmnt_key,
        )
        if not res.ok:
            emit("speak.failed", segment=seg.id)
            continue
        if res.failed_over:
            failovers += 1
        texts.append(text)
        # When a sink ran the asset url is a B2 https url; either way the provider
        # wrote the bytes locally first to output_dir/<step_id>.<ext>, and that file
        # survives the transfer. Recover it for ffmpeg by step id.
        url = res.assets[0].url
        if url.startswith("http"):
            b2_urls.append(url)
        local = _local_segment_file(res, seg_dir) or (
            None if url.startswith("http") else Path(_fs_from_file_url(url))
        )
        if local and local.exists():
            # Ease the wordier languages so the dub doesn't sound rushed. Audio-only
            # mode only (a video mux keeps segment lengths intact, or the dub drifts
            # off the picture). Placement and caption timing are both derived from this
            # eased file below, so the karaoke highlight stays in sync automatically.
            if source_video is None:
                apply_tempo(local, pace_for(lang.code))
            recorded.append((seg, text, local))
        emit("speak.done", segment=seg.id, provider=res.winner.provider.name,
             failed_over=res.failed_over)

    # 3. assemble one timed track, and record where each segment lands so the UI can
    # follow along. Two modes:
    #   audio-only -> lay segments end to end, preserving the *pauses* that separated
    #                 them in the source but never overlapping, so an eased or long dub
    #                 just extends the timeline instead of bleeding into the next line.
    #   video mux  -> keep absolute source timing so the dub tracks the picture.
    # Caption start/dur come from the same timeline and files, so the karaoke highlight
    # is exact either way.
    lead_in = 0.25
    audio_out = out_dir / lang.code / f"{lang.code}.mp3"
    emit("assemble.start", segments=len(recorded))
    placements: list[Placement] = []
    caption_segments: list[dict] = []

    if source_video is None:
        cursor = lead_in
        prev_source_end: float | None = None
        for s, t, local in recorded:
            if prev_source_end is not None:
                cursor += max(0.0, s.start - prev_source_end)  # preserve source silence
            dur = probe_duration(local)
            placements.append(Placement(start=cursor, audio_path=local))
            caption_segments.append({
                "id": s.id, "source": s.text, "target": t,
                "start": round(cursor, 3), "dur": round(dur, 3),
            })
            cursor += dur
            prev_source_end = s.end
        assemble_track(placements, audio_out, total_duration=None, zero_base=False)
    else:
        for s, t, local in recorded:
            placements.append(Placement(start=s.start, audio_path=local))
            caption_segments.append({
                "id": s.id, "source": s.text, "target": t,
                "start": round(s.start, 3), "dur": round(probe_duration(local), 3),
            })
        assemble_track(placements, audio_out,
                       total_duration=transcript.duration or None, zero_base=False)
    emit("assemble.done", path=str(audio_out))

    (out_dir / lang.code / "segments.json").write_text(
        json.dumps({"language": lang.code, "segments": caption_segments}, ensure_ascii=False),
        encoding="utf-8",
    )

    # 4. optional: mux onto the source video
    video_out = None
    if source_video is not None:
        video_out = out_dir / lang.code / f"localized_{lang.code}.mp4"
        mux_video(source_video, audio_out, video_out)
        emit("mux.done", path=str(video_out))

    return LocalizedLanguage(
        language=lang.code,
        audio_path=audio_out,
        video_path=video_out,
        segment_texts=texts,
        failovers=failovers,
        b2_urls=b2_urls,
        segments=caption_segments,
    )


def _fs_from_file_url(url: str) -> str:
    from ._fileurl import file_url_to_path

    return str(file_url_to_path(url))


def _local_segment_file(res: Any, seg_dir: Path) -> Path | None:
    """Find the local audio file the winning provider wrote to output_dir.

    Providers write to output_dir/<step_id>.<ext>; the file survives a sink
    transfer, so we can recover it by step id for ffmpeg assembly.
    """
    step = res.step
    sid = getattr(step, "step_id", None)
    if not sid:
        return None
    matches = sorted(seg_dir.glob(f"{sid}.*"))
    return matches[0] if matches else None
