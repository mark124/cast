"""Cross-provider failover for Genblaze steps.

Why this exists
---------------
Genblaze ships `fallback_models=[...]`, which looks like failover but isn't. It swaps
the model *string* and re-invokes the *same provider object*:

    # genblaze_core/pipeline/pipeline.py:1224, _try_fallback_models
    for fb_model in ps.fallback_models:
        fb_step = self._build_step(ps, step.inputs or None)
        fb_step.model = fb_model            # only the model string changes
        result = invoke_fn(fb_step, config)  # invoke_fn is bound to ps.provider

So `Pipeline().step(elevenlabs, model="eleven_flash_v2_5", fallback_models=["tts-1"])`
sends OpenAI's model slug to ElevenLabs, which 404s. Two further limits make it unusable
for our case:

  * It fires only on ProviderErrorCode.MODEL_ERROR (pipeline.py:1240). An auth failure,
    a 503, a rate limit, or a timeout will not trigger it.
  * genblaze_elevenlabs/_errors.py has no MODEL_ERROR branch at all, so an ElevenLabs
    step can never emit the one code that would trigger it. On our primary provider the
    feature is inert.

This module does what the name promised: try providers in order, on any failure, and
report which one actually spoke. Every attempt still runs through a Genblaze Pipeline —
we orchestrate across providers, we don't route around the SDK.

Lineage rides on Pipeline.from_result(), which sets parent_run_id on the resulting run
without touching the canonical hash. That is what lets a Spanish cut point back at the
master it came from.

Note on step metadata: 0.3.4's Pipeline.step() takes no `metadata=` kwarg (the GitHub
README documents one because main is ahead of PyPI). Passing it anyway is actively
harmful — it falls through **params, is normalized into a *model* param, and lands in
Step.params, which IS inside the manifest's canonical hash. The SDK guards `inputs=`
and `input=` against exactly this and warns about hash drift in the comment; `metadata=`
has no such guard. So we keep attempt tagging in FailoverResult rather than smuggling it
into the manifest. See docs/upstream-findings.md.

All limitations here are worth reporting upstream; see docs/upstream-findings.md.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from genblaze_core import (
    Modality,
    Pipeline,
    ProviderErrorCode,
    Step,
    StepStatus,
)
from genblaze_core.providers.base import BaseProvider

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Candidate:
    """One rung of a failover chain: a provider, a model, and its per-call params.

    `params` exists because the adapters disagree about how to say "speak Spanish".
    ElevenLabs takes `language_code`, LMNT takes `language`, OpenAI TTS takes no
    language parameter at all and infers it from the text. The chain owns that
    difference so callers don't have to.
    """

    provider: BaseProvider
    model: str
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.provider.name}:{self.model}"


@dataclass(frozen=True)
class Attempt:
    """A single try against one provider. Kept whether it worked or not."""

    candidate: Candidate
    ok: bool
    error_code: ProviderErrorCode | None = None
    error: str | None = None

    @property
    def label(self) -> str:
        return self.candidate.label


@dataclass(frozen=True)
class FailoverResult:
    """The outcome, plus the paper trail of everything tried on the way.

    Carries the winning PipelineResult rather than just the Step, because callers
    need its manifest (for the B2 sink) and its run (for parent_run_id lineage).
    """

    step: Step | None
    attempts: tuple[Attempt, ...]
    result: Any | None = None  # PipelineResult of the winning attempt

    @property
    def ok(self) -> bool:
        return self.step is not None

    @property
    def run(self) -> Any | None:
        return self.result.run if self.result else None

    @property
    def manifest(self) -> Any | None:
        return self.result.manifest if self.result else None

    @property
    def winner(self) -> Candidate | None:
        for attempt in self.attempts:
            if attempt.ok:
                return attempt.candidate
        return None

    @property
    def failed_over(self) -> bool:
        """True if anything had to be survived to get here.

        This is what the UI puts on screen, and what the demo turns on.
        """
        return self.ok and len(self.attempts) > 1

    @property
    def assets(self) -> list[Any]:
        return list(self.step.assets) if self.step else []


class AllProvidersFailed(RuntimeError):
    """Every rung of the chain failed. Carries the trail for diagnosis."""

    def __init__(self, name: str, attempts: Sequence[Attempt]) -> None:
        self.attempts = tuple(attempts)
        trail = " -> ".join(
            f"{a.label}({a.error_code.value if a.error_code else 'unknown'})"
            for a in attempts
        )
        super().__init__(f"all providers failed for {name}: {trail}")


ProgressFn = Callable[[Attempt], None]


def run_with_failover(
    chain: Iterable[Candidate],
    *,
    prompt: str,
    modality: Modality,
    name: str,
    parent: Any | None = None,
    sink: Any | None = None,
    on_attempt: ProgressFn | None = None,
    raise_on_exhausted: bool = True,
) -> FailoverResult:
    """Run `prompt` against each candidate in turn until one succeeds.

    Unlike `fallback_models`, this survives *any* failure code — including the auth
    failure you get by pulling an API key, which is how a provider outage is staged.

    `parent` is a PipelineResult (typically the transcription run). When given, every
    attempt's run carries parent_run_id back to it, so the manifest of a localized cut
    points at the master it was derived from.

    `sink` is passed to the *winning* attempt's run so its asset + manifest transfer to
    storage (e.g. B2). Only the winner uploads — failed attempts produced nothing worth
    keeping.

    `on_attempt` is called after every attempt, win or lose, so a UI can narrate the
    failover as it happens rather than after the fact.
    """
    candidates = tuple(chain)
    if not candidates:
        raise ValueError(f"empty failover chain for {name!r}")

    attempts: list[Attempt] = []

    for candidate in candidates:
        result = _invoke(candidate, prompt=prompt, modality=modality, name=name,
                         parent=parent, sink=sink)
        step = result.run.steps[0] if (result and result.run.steps) else None

        if step is not None and step.status == StepStatus.SUCCEEDED:
            attempt = Attempt(candidate=candidate, ok=True)
            attempts.append(attempt)
            if on_attempt:
                on_attempt(attempt)
            if len(attempts) > 1:
                log.info(
                    "%s: recovered on %s after %d failure(s)",
                    name, candidate.label, len(attempts) - 1,
                )
            return FailoverResult(step=step, attempts=tuple(attempts), result=result)

        code = step.error_code if step is not None else None
        attempt = Attempt(
            candidate=candidate,
            ok=False,
            error_code=code,
            error=step.error if step is not None else "pipeline returned no step",
        )
        attempts.append(attempt)
        if on_attempt:
            on_attempt(attempt)
        log.warning(
            "%s: %s failed (%s) — failing over",
            name, candidate.label, code.value if code else "unknown",
        )

    if raise_on_exhausted:
        raise AllProvidersFailed(name, attempts)
    return FailoverResult(step=None, attempts=tuple(attempts), result=None)


def _invoke(
    candidate: Candidate,
    *,
    prompt: str,
    modality: Modality,
    name: str,
    parent: Any | None,
    sink: Any | None = None,
) -> Any | None:
    """Run one candidate through a real Genblaze Pipeline, swallowing failure.

    `raise_on_failure=False` is passed explicitly: run() currently warns that 0.4.0
    will start raising on step failure, and we depend on getting the failed Step back
    so we can read its error_code and move on.
    """
    pipeline = Pipeline(name)
    if parent is not None:
        # Sets parent_run_id without touching the canonical hash.
        pipeline = pipeline.from_result(parent)

    pipeline = pipeline.step(
        candidate.provider,
        model=candidate.model,
        prompt=prompt,
        modality=modality,
        **candidate.params,
    )

    try:
        return pipeline.run(raise_on_failure=False, sink=sink)
    except Exception as exc:  # provider construction/transport blew up outside a Step
        log.warning("%s: %s raised outside the step: %s", name, candidate.label, exc)
        return None
