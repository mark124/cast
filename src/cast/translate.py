"""Translate a transcript into a target language with Claude, as a Genblaze step.

Runs through AnthropicChatProvider so translation is a real pipeline step, not a
side call — the manifest then covers the translation the same way it covers the
transcription and the speech.

Segment mode preserves the transcript's segmentation (one entry in, one out, ids
intact) via structured output, so caption timing survives the round trip. Plain
mode is a single blob for quick checks.
"""

from __future__ import annotations

from typing import Any

from genblaze_core import Modality, Pipeline, StepStatus

from .genblaze_anthropic import AnthropicChatProvider, json_of, text_of
from .languages import Language, get

TRANSLATOR_SYSTEM = (
    "You are a professional subtitle and dub translator. Translate faithfully and "
    "idiomatically into the target language. Preserve meaning, tone, and register. "
    "Output only the translation — no notes, no quotes, no romanization."
)

_SEGMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "text": {"type": "string"},
                },
                "required": ["id", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["segments"],
    "additionalProperties": False,
}


def translate_text(
    text: str,
    target: str | Language,
    *,
    provider: AnthropicChatProvider | None = None,
    parent: Any = None,
) -> Any:
    """Translate a blob of text into `target`. Returns the PipelineResult.

    Text comes back on the step's asset (`text_of(result.step)`); the run carries
    parent_run_id when `parent` is given, linking the translation to its source.
    """
    lang = target if isinstance(target, Language) else get(target)
    provider = provider or AnthropicChatProvider()

    pipeline = Pipeline(f"translate-{lang.code}")
    if parent is not None:
        pipeline = pipeline.from_result(parent)

    result = pipeline.step(
        provider,
        model="claude-opus-4-8",
        prompt=f"Translate into {lang.name} ({lang.code}):\n\n{text}",
        modality=Modality.TEXT,
        system=TRANSLATOR_SYSTEM,
        effort="low",
    ).run(raise_on_failure=False)

    step = result.run.steps[0]
    if step.status != StepStatus.SUCCEEDED:
        raise RuntimeError(f"translation to {lang.code} failed: {step.error_code}: {step.error}")
    return result


def translate_segments(
    segments: list[dict],
    target: str | Language,
    *,
    provider: AnthropicChatProvider | None = None,
    parent: Any = None,
) -> list[dict]:
    """Translate a list of {id, text} segments, preserving ids and count.

    Uses structured output so the response is guaranteed-parseable and the mapping
    back onto the original timings can't drift.
    """
    lang = target if isinstance(target, Language) else get(target)
    provider = provider or AnthropicChatProvider()

    import json

    pipeline = Pipeline(f"translate-seg-{lang.code}")
    if parent is not None:
        pipeline = pipeline.from_result(parent)

    result = pipeline.step(
        provider,
        model="claude-opus-4-8",
        prompt=(
            f"Translate each segment's text into {lang.name} ({lang.code}). "
            f"Return every segment with its id unchanged and only the text translated.\n\n"
            f"{json.dumps(segments, ensure_ascii=False)}"
        ),
        modality=Modality.TEXT,
        system=TRANSLATOR_SYSTEM,
        effort="low",
        output_schema=_SEGMENTS_SCHEMA,
    ).run(raise_on_failure=False)

    step = result.run.steps[0]
    if step.status != StepStatus.SUCCEEDED:
        raise RuntimeError(f"segment translation to {lang.code} failed: {step.error_code}: {step.error}")

    out = json_of(step)["segments"]
    got_ids = {s["id"] for s in out}
    want_ids = {s["id"] for s in segments}
    if got_ids != want_ids:
        raise RuntimeError(
            f"segment ids drifted translating to {lang.code}: "
            f"missing {want_ids - got_ids}, extra {got_ids - want_ids}"
        )
    return out
