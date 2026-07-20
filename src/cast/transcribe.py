"""Transcribe a source file into timed sentence segments, via Genblaze.

Segments are the unit of localization: each carries the source start/end time, so
a translated cut can be placed back at the moment it was spoken. That's how dub
sync works at segment level (~400ms, which is AssemblyAI's timing accuracy) without
needing lip-accurate alignment — perfect for the audio-first sources this is built
for (podcasts, audiobooks).

Transcription is the one stage that costs real money per run, so the result caches
to JSON keyed on the audio's content hash.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from genblaze_core import Modality, Pipeline, StepStatus

from .genblaze_anthropic import text_of

# Sentence boundary: end punctuation (incl. CJK/。！？) followed by space or end.
_SENT_END = re.compile(r"([.!?。！？])")


@dataclass
class Segment:
    id: int
    start: float  # seconds into the source
    end: float
    text: str


@dataclass
class Transcript:
    text: str
    segments: list[Segment]
    duration: float
    run_id: str | None = None  # transcription run, for provenance lineage

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "segments": [asdict(s) for s in self.segments],
            "duration": self.duration,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Transcript":
        return cls(
            text=d["text"],
            segments=[Segment(**s) for s in d["segments"]],
            duration=d["duration"],
            run_id=d.get("run_id"),
        )


def transcript_from_text(text: str, *, max_sentences: int = 8) -> Transcript:
    """Build a Transcript from typed text, with no source audio.

    Splits on sentence-ending punctuation into segments. There is no audio to align
    to, so every segment carries zero timing and the audio-only assembler lays them
    end to end. Capped at max_sentences to bound cost on the public endpoint. run_id
    is None: typed text has no transcription master to trace a manifest back to.
    """
    text = (text or "").strip()
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    sentences = [p.strip() for p in parts if p.strip()]
    if not sentences and text:
        sentences = [text]
    sentences = sentences[:max_sentences]
    segments = [Segment(id=i, start=0.0, end=0.0, text=s) for i, s in enumerate(sentences)]
    return Transcript(text=text, segments=segments, duration=0.0, run_id=None)


def _content_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _segments_from_words(words: list[Any], full_text: str) -> list[Segment]:
    """Group word timings into sentence segments.

    Walk the words, starting a new segment after a word whose text ends a sentence.
    Each segment's start is its first word's start and end is its last word's end.
    """
    segments: list[Segment] = []
    cur: list[Any] = []
    sid = 0
    for w in words:
        cur.append(w)
        token = getattr(w, "word", "") or ""
        if _SENT_END.search(token[-1:]):
            segments.append(_mk_segment(sid, cur))
            cur = []
            sid += 1
    if cur:
        segments.append(_mk_segment(sid, cur))
    # Fall back to a single segment if there were no word timings at all.
    if not segments and full_text.strip():
        segments = [Segment(id=0, start=0.0, end=0.0, text=full_text.strip())]
    return segments


def _mk_segment(sid: int, words: list[Any]) -> Segment:
    text = " ".join((getattr(w, "word", "") or "").strip() for w in words).strip()
    # Collapse the space the join inserts before punctuation.
    text = re.sub(r"\s+([.!?,;:。！？])", r"\1", text)
    return Segment(
        id=sid,
        start=float(getattr(words[0], "start", 0.0) or 0.0),
        end=float(getattr(words[-1], "end", 0.0) or 0.0),
        text=text,
    )


def transcribe(
    audio_path: str | Path,
    *,
    cache_path: str | Path | None = None,
    model: str = "universal-2",
) -> tuple[Transcript, Any]:
    """Transcribe `audio_path` into timed segments. Returns (Transcript, PipelineResult).

    The PipelineResult is returned so callers can pass it as `parent` to downstream
    steps and get provenance lineage. On a cache hit there's no live run, so the
    result is None and the Transcript still carries the original run_id.
    """
    audio_path = Path(audio_path)
    cache = Path(cache_path) if cache_path else None

    if cache and cache.exists():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if cached.get("_audio_hash") == _content_hash(audio_path):
            return Transcript.from_dict(cached), None

    from genblaze_assemblyai import AssemblyAIProvider

    result = (
        Pipeline("transcribe")
        .step(
            AssemblyAIProvider(),
            model=model,
            # AssemblyAI's connector requires empty/localhost netloc, i.e. the
            # standard file:///C:/... form from as_uri(). Note this is the OPPOSITE
            # of what the 0.3.4 B2 sink accepts on Windows (file://C:/...,
            # docs/upstream-findings.md #9) — two genblaze components, two
            # incompatible Windows file:// conventions. Input uses as_uri().
            prompt=audio_path.resolve().as_uri(),
            modality=Modality.TEXT,
            language_detection=True,
        )
        .run(raise_on_failure=False)
    )
    step = result.run.steps[0]
    if step.status != StepStatus.SUCCEEDED:
        raise RuntimeError(f"transcription failed: {step.error_code}: {step.error}")

    asset = step.assets[0]
    text = text_of(step)
    words = getattr(asset.audio, "word_timings", None) or []
    duration = float(step.provider_payload.get("audio_duration") or 0.0)

    transcript = Transcript(
        text=text,
        segments=_segments_from_words(words, text),
        duration=duration,
        run_id=result.run.run_id,
    )

    if cache:
        payload = transcript.to_dict()
        payload["_audio_hash"] = _content_hash(audio_path)
        cache.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return transcript, result
