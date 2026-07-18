"""Failover behaviour, including the SDK limitations that forced us to build it.

The `test_sdk_*` cases at the bottom are characterization tests. They don't test our
code — they pin Genblaze's actual behaviour so that (a) the claims in failover.py's
docstring stay honest, and (b) if a future genblaze release fixes either limitation,
these go red and tell us to delete our loop rather than carry it forever.
"""

from __future__ import annotations

import pytest
from genblaze_core import Modality, Pipeline, ProviderErrorCode, StepStatus
from genblaze_core.testing import MockAudioProvider

from cast.failover import (
    AllProvidersFailed,
    Attempt,
    Candidate,
    run_with_failover,
)


def _speaker(name: str, *, fails_with: ProviderErrorCode | None = None) -> MockAudioProvider:
    if fails_with is None:
        return MockAudioProvider(name=name)
    return MockAudioProvider(name=name, should_fail=True, error_code=fails_with)


def _chain(*providers) -> list[Candidate]:
    return [Candidate(provider=p, model=f"{p.name}-model") for p in providers]


def _run(chain, **kw):
    return run_with_failover(
        chain, prompt="hola", modality=Modality.AUDIO, name="tts-es", **kw
    )


# --- our failover loop -------------------------------------------------------


def test_first_provider_wins_without_touching_the_backup():
    primary = _speaker("elevenlabs")
    backup = _speaker("lmnt")

    result = _run(_chain(primary, backup))

    assert result.ok
    assert result.winner.provider is primary
    assert not result.failed_over
    assert backup.call_count == 0, "backup was called despite the primary succeeding"


def test_falls_over_to_a_different_provider():
    primary = _speaker("elevenlabs", fails_with=ProviderErrorCode.SERVER_ERROR)
    backup = _speaker("lmnt")

    result = _run(_chain(primary, backup))

    assert result.ok
    assert result.winner.provider is backup
    assert result.failed_over
    assert backup.call_count == 1, "the backup provider object was never actually invoked"
    assert [a.label for a in result.attempts] == [
        "elevenlabs:elevenlabs-model",
        "lmnt:lmnt-model",
    ]


@pytest.mark.parametrize(
    "code",
    [
        # The demo pulls an API key on camera. That produces AUTH_FAILURE, which
        # genblaze's own fallback_models would ignore. Ours must not.
        ProviderErrorCode.AUTH_FAILURE,
        ProviderErrorCode.SERVER_ERROR,
        ProviderErrorCode.RATE_LIMIT,
        ProviderErrorCode.TIMEOUT,
        ProviderErrorCode.MODEL_ERROR,
        ProviderErrorCode.CONTENT_POLICY,
        ProviderErrorCode.UNKNOWN,
    ],
)
def test_fails_over_on_every_error_code(code):
    primary = _speaker("elevenlabs", fails_with=code)
    backup = _speaker("lmnt")

    result = _run(_chain(primary, backup))

    assert result.ok, f"{code.value} did not trigger failover"
    assert result.winner.provider is backup
    assert result.attempts[0].error_code is code


def test_walks_the_whole_chain():
    first = _speaker("elevenlabs", fails_with=ProviderErrorCode.RATE_LIMIT)
    second = _speaker("lmnt", fails_with=ProviderErrorCode.SERVER_ERROR)
    third = _speaker("openai")

    result = _run(_chain(first, second, third))

    assert result.winner.provider is third
    assert len(result.attempts) == 3


def test_raises_when_every_provider_fails():
    chain = _chain(
        _speaker("elevenlabs", fails_with=ProviderErrorCode.SERVER_ERROR),
        _speaker("lmnt", fails_with=ProviderErrorCode.AUTH_FAILURE),
    )

    with pytest.raises(AllProvidersFailed) as excinfo:
        _run(chain)

    assert "elevenlabs" in str(excinfo.value)
    assert "lmnt" in str(excinfo.value)
    assert len(excinfo.value.attempts) == 2


def test_can_report_exhaustion_without_raising():
    chain = _chain(_speaker("elevenlabs", fails_with=ProviderErrorCode.SERVER_ERROR))

    result = _run(chain, raise_on_exhausted=False)

    assert not result.ok
    assert result.winner is None
    assert result.assets == []


def test_progress_callback_narrates_every_attempt():
    seen: list[Attempt] = []
    chain = _chain(
        _speaker("elevenlabs", fails_with=ProviderErrorCode.TIMEOUT),
        _speaker("lmnt"),
    )

    _run(chain, on_attempt=seen.append)

    assert [(a.label, a.ok) for a in seen] == [
        ("elevenlabs:elevenlabs-model", False),
        ("lmnt:lmnt-model", True),
    ]


def test_empty_chain_is_a_programming_error():
    with pytest.raises(ValueError, match="empty failover chain"):
        _run([])


def test_per_candidate_params_reach_the_provider():
    # The adapters disagree about how to say "speak Spanish": ElevenLabs takes
    # language_code, LMNT takes language, OpenAI takes nothing. The chain owns that.
    provider = _speaker("lmnt")
    chain = [Candidate(provider=provider, model="blizzard", params={"language": "es"})]

    _run(chain)

    assert provider.received_steps[0].params.get("language") == "es"


def test_lineage_links_variants_back_to_the_master():
    # "Which master did this Spanish cut come from?" is the whole point.
    master = (
        Pipeline("master")
        .step(_speaker("assemblyai"), model="universal-2", prompt="hi", modality=Modality.AUDIO)
        .run(raise_on_failure=False)
    )

    result = _run(_chain(_speaker("lmnt")), parent=master)

    assert result.run.parent_run_id == master.run.run_id
    assert result.run.run_id != master.run.run_id


def test_lineage_survives_a_failover():
    # The cut that had to fail over must still name its master.
    master = (
        Pipeline("master")
        .step(_speaker("assemblyai"), model="universal-2", prompt="hi", modality=Modality.AUDIO)
        .run(raise_on_failure=False)
    )
    chain = _chain(
        _speaker("elevenlabs", fails_with=ProviderErrorCode.AUTH_FAILURE),
        _speaker("lmnt"),
    )

    result = _run(chain, parent=master)

    assert result.failed_over
    assert result.run.parent_run_id == master.run.run_id


def test_result_exposes_a_verifiable_manifest():
    # The B2 sink needs the manifest, so the winner's PipelineResult must survive.
    result = _run(_chain(_speaker("lmnt")))

    assert result.manifest is not None
    assert result.manifest.verify_hash()


def test_we_never_pass_metadata_into_step_params():
    """Guard against reintroducing a manifest-hash bug.

    On 0.3.4 Pipeline.step() has no metadata= kwarg, so `metadata={...}` falls through
    **params and is normalized into a *model* param, landing in Step.params — which is
    inside the manifest's canonical hash. Two runs that differ only in a tagging dict
    would then produce different hashes for identical media.
    """
    provider = _speaker("lmnt")

    _run(_chain(provider))

    assert "metadata" not in provider.received_steps[0].params


# --- characterization: why we can't just use fallback_models ------------------


def test_sdk_fallback_models_cannot_cross_providers():
    """Genblaze's fallback_models swaps the model string, not the provider.

    If this ever goes red, genblaze learned to cross providers and cast.failover
    should be deleted in favour of the built-in.
    """
    elevenlabs = MockAudioProvider(
        name="elevenlabs", should_fail=True, error_code=ProviderErrorCode.MODEL_ERROR
    )
    openai = MockAudioProvider(name="openai")

    result = (
        Pipeline("cross-provider-attempt")
        .step(
            elevenlabs,
            model="eleven_flash_v2_5",
            prompt="hola",
            modality=Modality.AUDIO,
            fallback_models=["tts-1"],  # an OpenAI model...
        )
        .run(raise_on_failure=False)
    )

    assert openai.call_count == 0, "fallback_models reached another provider — update failover.py"
    # It sent OpenAI's model slug to ElevenLabs instead, and then gave up.
    assert [s.model for s in elevenlabs.received_steps] == ["eleven_flash_v2_5", "tts-1"]
    assert result.run.steps[0].status == StepStatus.FAILED


@pytest.mark.parametrize(
    "code",
    [
        ProviderErrorCode.AUTH_FAILURE,
        ProviderErrorCode.SERVER_ERROR,
        ProviderErrorCode.RATE_LIMIT,
        ProviderErrorCode.TIMEOUT,
    ],
)
def test_sdk_fallback_models_ignores_every_code_except_model_error(code):
    """Pulling an API key yields AUTH_FAILURE, which fallback_models will not catch.

    This is the reason the on-camera outage trick needs our loop: the natural way to
    stage a provider failure produces exactly the codes the SDK's fallback ignores.
    """
    provider = MockAudioProvider(name="elevenlabs", should_fail=True, error_code=code)

    (
        Pipeline("code-sensitivity")
        .step(
            provider,
            model="eleven_flash_v2_5",
            prompt="hola",
            modality=Modality.AUDIO,
            fallback_models=["eleven_multilingual_v2"],
        )
        .run(raise_on_failure=False)
    )

    assert provider.call_count == 1, f"{code.value} unexpectedly triggered a fallback"
