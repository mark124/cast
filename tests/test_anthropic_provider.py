"""AnthropicChatProvider unit tests — no network, no spend.

A stub client stands in for anthropic.Anthropic so payload construction and error
mapping are pinned without hitting the API. The provider is separately verified
against the live API; these guard the wiring.
"""

from __future__ import annotations

import anthropic
import httpx
import pytest
from genblaze_core import Modality, Pipeline, ProviderErrorCode, StepStatus

from cast.genblaze_anthropic import (
    AnthropicChatProvider,
    json_of,
    map_anthropic_error,
    text_of,
)


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Usage:
    input_tokens = 42
    output_tokens = 7
    cache_read_input_tokens = 0


class _Response:
    def __init__(self, text: str = "hola", stop_reason: str = "end_turn") -> None:
        self.content = [_Block(text)]
        self.stop_reason = stop_reason
        self.stop_details = None
        self.usage = _Usage()


class _Messages:
    def __init__(self, outer: "_StubClient") -> None:
        self._outer = outer

    def create(self, **payload):
        self._outer.payloads.append(payload)
        if self._outer.raises is not None:
            raise self._outer.raises
        return self._outer.response


class _StubClient:
    """Captures the payload the provider builds, or raises on demand."""

    def __init__(self, response=None, raises: Exception | None = None) -> None:
        self.response = response or _Response()
        self.raises = raises
        self.payloads: list[dict] = []
        self.messages = _Messages(self)


def _run(provider: AnthropicChatProvider, **step_kwargs):
    kwargs = {"model": "claude-opus-4-8", "prompt": "hi", "modality": Modality.TEXT}
    kwargs.update(step_kwargs)
    result = Pipeline("t").step(provider, **kwargs).run(raise_on_failure=False)
    return result.run.steps[0]


def _http_error(cls, status: int, headers: dict | None = None):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, headers=headers or {}, request=request)
    return cls("boom", response=response, body=None)


# --- payload construction ----------------------------------------------------


def test_adaptive_thinking_is_set_explicitly():
    # Opus 4.8 runs WITHOUT thinking when the field is omitted, so the provider
    # must send it rather than relying on a default.
    stub = _StubClient()
    _run(AnthropicChatProvider(client=stub))

    assert stub.payloads[0]["thinking"] == {"type": "adaptive"}


def test_thinking_can_be_disabled_per_step():
    stub = _StubClient()
    _run(AnthropicChatProvider(client=stub), thinking=False)

    assert stub.payloads[0]["thinking"] == {"type": "disabled"}


def test_effort_defaults_and_overrides():
    stub = _StubClient()
    _run(AnthropicChatProvider(client=stub))
    assert stub.payloads[0]["output_config"]["effort"] == "medium"

    _run(AnthropicChatProvider(client=stub), effort="xhigh")
    assert stub.payloads[1]["output_config"]["effort"] == "xhigh"


def test_output_schema_turns_on_structured_outputs():
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    stub = _StubClient()

    _run(AnthropicChatProvider(client=stub), output_schema=schema)

    assert stub.payloads[0]["output_config"]["format"] == {
        "type": "json_schema",
        "schema": schema,
    }


def test_system_prompt_is_forwarded():
    stub = _StubClient()
    _run(AnthropicChatProvider(client=stub), system="You are a translator.")

    assert stub.payloads[0]["system"] == "You are a translator."


@pytest.mark.parametrize("param", ["temperature", "top_p", "top_k", "budget_tokens"])
def test_removed_params_fail_loudly_instead_of_reaching_the_api(param):
    # These are a hard 400 on Opus 4.8. Genblaze folds unknown step kwargs into
    # model params, so without this guard a stray temperature= would silently ride
    # along inside Step.params — which is *inside the manifest's canonical hash*.
    stub = _StubClient()

    step = _run(AnthropicChatProvider(client=stub), **{param: 0.7})

    assert step.status == StepStatus.FAILED
    assert step.error_code is ProviderErrorCode.INVALID_INPUT
    assert stub.payloads == [], "the bad request was sent to the API anyway"


def test_step_without_prompt_or_input_is_rejected():
    stub = _StubClient()
    step = _run(AnthropicChatProvider(client=stub), prompt=None)

    assert step.status == StepStatus.FAILED
    assert step.error_code is ProviderErrorCode.INVALID_INPUT


# --- output shape ------------------------------------------------------------


def test_text_lands_on_the_asset_with_a_verifiable_hash():
    stub = _StubClient(_Response("hola mundo"))
    provider = AnthropicChatProvider(client=stub)

    result = (
        Pipeline("t")
        .step(provider, model="claude-opus-4-8", prompt="hi", modality=Modality.TEXT)
        .run(raise_on_failure=False)
    )
    step = result.run.steps[0]
    asset = step.assets[0]

    assert text_of(step) == "hola mundo"
    assert asset.media_type == "text/plain"
    # An asset with no declared sha256 fails Manifest.verify(); hashing the text
    # bytes is what keeps a TEXT step verifiable.
    assert asset.sha256 and len(asset.sha256) == 64
    assert result.manifest.verify()


def test_usage_is_reported_and_cost_left_to_the_caller():
    stub = _StubClient()
    step = _run(AnthropicChatProvider(client=stub))

    assert step.provider_payload["usage"] == {
        "tokens_in": 42,
        "tokens_out": 7,
        "tokens_cached": 0,
    }
    # Genblaze ships zero pricing on purpose; don't hard-code a rate that rots.
    assert step.cost_usd is None


def test_json_of_parses_structured_output():
    stub = _StubClient(_Response('{"segments": [{"id": 0, "text": "hola"}]}'))
    step = _run(AnthropicChatProvider(client=stub))

    assert json_of(step) == {"segments": [{"id": 0, "text": "hola"}]}


def test_chain_input_from_an_upstream_text_step():
    upstream = _StubClient(_Response("transcribed words"))
    downstream = _StubClient(_Response("translated words"))

    result = (
        Pipeline("chain", chain=True)
        .step(AnthropicChatProvider(client=upstream), model="claude-opus-4-8",
              prompt="transcribe", modality=Modality.TEXT)
        .step(AnthropicChatProvider(client=downstream), model="claude-opus-4-8",
              prompt="translate the above", modality=Modality.TEXT, input_from=0)
        .run(raise_on_failure=False)
    )

    assert result.run.steps[1].status == StepStatus.SUCCEEDED
    # The upstream text must reach the downstream prompt, not vanish.
    assert "transcribed words" in downstream.payloads[0]["messages"][0]["content"]


# --- error mapping -----------------------------------------------------------


def test_refusal_is_content_policy_not_an_indexerror():
    # On a refusal the content list is empty; reading content[0] blind would raise
    # IndexError and hide a classifiable failure.
    response = _Response(stop_reason="refusal")
    response.content = []
    step = _run(AnthropicChatProvider(client=_StubClient(response)))

    assert step.status == StepStatus.FAILED
    assert step.error_code is ProviderErrorCode.CONTENT_POLICY


def test_bad_model_maps_to_model_error():
    """The one code Pipeline._try_fallback_models acts on.

    ElevenLabs' shipped mapper has no MODEL_ERROR branch, which makes
    fallback_models inert there. This connector does not repeat that.
    """
    stub = _StubClient(raises=_http_error(anthropic.NotFoundError, 404))
    step = _run(AnthropicChatProvider(client=stub))

    assert step.error_code is ProviderErrorCode.MODEL_ERROR


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (_http_error(anthropic.RateLimitError, 429), ProviderErrorCode.RATE_LIMIT),
        (_http_error(anthropic.AuthenticationError, 401), ProviderErrorCode.AUTH_FAILURE),
        (_http_error(anthropic.PermissionDeniedError, 403), ProviderErrorCode.AUTH_FAILURE),
        (_http_error(anthropic.BadRequestError, 400), ProviderErrorCode.INVALID_INPUT),
        (_http_error(anthropic.NotFoundError, 404), ProviderErrorCode.MODEL_ERROR),
    ],
)
def test_error_mapping(exc, expected):
    assert map_anthropic_error(exc) is expected


def test_server_error_maps_to_server_error():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(503, request=request)
    exc = anthropic.APIStatusError("boom", response=response, body=None)

    assert map_anthropic_error(exc) is ProviderErrorCode.SERVER_ERROR


def test_unknown_exception_maps_to_unknown():
    assert map_anthropic_error(ValueError("???")) is ProviderErrorCode.UNKNOWN


def test_retry_after_is_read_from_the_response_header():
    stub = _StubClient(
        raises=_http_error(anthropic.RateLimitError, 429, {"retry-after": "30"})
    )
    step = _run(AnthropicChatProvider(client=stub))

    assert step.error_code is ProviderErrorCode.RATE_LIMIT
