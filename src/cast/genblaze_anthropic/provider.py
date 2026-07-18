"""AnthropicChatProvider — Claude as a Genblaze Pipeline step.

Genblaze ships no Anthropic connector, so Claude can't be composed into a
Pipeline out of the box. This adapter closes that: it wraps the Messages API as
a SyncProvider so a translation step orchestrates through Genblaze alongside the
transcription and speech steps, rather than sitting outside the pipeline as a
bare SDK call.

Shape follows genblaze_nvidia.NvidiaChatProvider — currently the only
chat-as-Pipeline-step provider in the SDK. Its own docstring anticipates this:

    Why a direct SyncProvider subclass and not a generic ChatProvider base:
    there's only one concrete chat-as-Pipeline-step provider today (NVIDIA).
    When a second one ships (Whisper, Gemini chat), extracting a base class is
    cheap; building one for a single consumer is premature.

This is that second one. The layout mirrors genblaze_nvidia/ so upstreaming is a
directory move, not a rewrite.

Opus 4.8 API notes worth not relearning:
  * temperature / top_p / top_k are removed — sending any of them is a 400.
  * thinking={"type": "enabled", "budget_tokens": N} is removed — also a 400.
    Depth is controlled by output_config.effort instead.
  * Omitting `thinking` runs WITHOUT thinking on Opus 4.8, so adaptive must be
    set explicitly.
  * thinking.display defaults to "omitted" — thinking blocks arrive with empty
    text unless you ask for "summarized".
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import anthropic
from genblaze_core.exceptions import ProviderError
from genblaze_core.models.asset import Asset
from genblaze_core.models.enums import Modality, ProviderErrorCode
from genblaze_core.models.step import Step
from genblaze_core.providers.base import ProviderCapabilities, SyncProvider
from genblaze_core.providers.model_registry import ModelRegistry
from genblaze_core.providers.retry import RetryPolicy
from genblaze_core.runnable.config import RunnableConfig

from ._errors import map_anthropic_error, retry_after_seconds

DEFAULT_MODEL = "claude-opus-4-8"

# Non-streaming default. Above roughly this the SDK starts risking HTTP timeouts
# and wants streaming instead; a segment-list translation lands far below it.
DEFAULT_MAX_TOKENS = 16000

KNOWN_MODELS = (
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-5",
    "claude-haiku-4-5",
)


class AnthropicChatProvider(SyncProvider):
    """Adapter for the Anthropic Messages API as a Modality.TEXT pipeline step.

    Args:
        api_key: Anthropic API key. Falls back to the SDK's own resolution
            (ANTHROPIC_API_KEY, then ANTHROPIC_AUTH_TOKEN, then an `ant auth
            login` profile), so a bare constructor works on a configured host.
        client: Pre-built anthropic.Anthropic — escape hatch for tests and
            shared clients. When set, api_key and timeout are ignored.
        default_effort: output_config.effort when a step doesn't name one.
            "medium" rather than the API default of "high" because this
            connector's caller fans out many concurrent translations and streams
            them live; per-step `effort` overrides it for harder work.
        thinking: Adaptive thinking on by default. Opus 4.8 runs *without*
            thinking when the field is omitted, so this is set explicitly.

    Step params (via `.step(..., key=value)`):
        system: system prompt string
        max_tokens: int
        effort: "low" | "medium" | "high" | "xhigh" | "max"
        thinking: bool — False sends {"type": "disabled"}
        output_schema: dict — a JSON Schema; turns on structured outputs so the
            response text is guaranteed-parseable JSON
    """

    name = "anthropic-chat"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any = None,
        default_model: str = DEFAULT_MODEL,
        default_effort: str = "medium",
        thinking: bool = True,
        timeout: float | None = None,
        models: ModelRegistry | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        super().__init__(models=models, retry_policy=retry_policy)
        self._api_key = api_key
        self._injected_client = client
        self._client = client
        self._default_model = default_model
        self._default_effort = default_effort
        self._thinking = thinking
        self._timeout = timeout

    # --- SyncProvider contract ---------------------------------------------

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_modalities=[Modality.TEXT],
            supported_inputs=["text"],
            accepts_chain_input=True,
            models=list(KNOWN_MODELS),
            output_formats=["text/plain"],
        )

    def generate(self, step: Step, config: RunnableConfig | None = None) -> Step:
        client = self._resolve_client()
        payload = self._build_payload(step)

        try:
            response = client.messages.create(**payload)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                f"Anthropic chat failed: {exc}",
                error_code=map_anthropic_error(exc),
                retry_after=retry_after_seconds(exc),
            ) from exc

        # Check stop_reason before reading content: on a refusal the content list
        # is empty (or partial), so indexing it blind raises IndexError instead of
        # surfacing a real, classifiable failure.
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) or "unspecified"
            raise ProviderError(
                f"Anthropic declined the request (category: {category})",
                error_code=ProviderErrorCode.CONTENT_POLICY,
            )

        text = "".join(b.text for b in response.content if b.type == "text")

        # Mirrors NvidiaChatProvider: Asset has no text field yet (it's a planned
        # wave), so the payload rides in metadata['text'] and the sha256 is taken
        # over the text bytes. That hash is what makes Manifest.verify() pass — an
        # asset with no declared sha256 fails verification.
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        step.assets = [
            Asset(
                url=f"text:{digest}",  # synthetic; there is no URL to dereference
                media_type="text/plain",
                sha256=digest,
                size_bytes=len(text.encode("utf-8")),
                metadata={"text": text},
            )
        ]

        usage = response.usage
        step.provider_payload["usage"] = {
            "tokens_in": usage.input_tokens,
            "tokens_out": usage.output_tokens,
            "tokens_cached": getattr(usage, "cache_read_input_tokens", None),
        }
        step.provider_payload["finish_reason"] = response.stop_reason
        # Pricing is caller-registered in Genblaze (the SDK ships zero rates and
        # pricing-recipes.md is stamped "Not maintained"), so report tokens and
        # let the caller price them rather than hard-coding a rate that rots.
        step.cost_usd = None
        return step

    # --- internals ----------------------------------------------------------

    def _resolve_client(self) -> Any:
        if self._client is None:
            kwargs: dict[str, Any] = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._timeout is not None:
                kwargs["timeout"] = self._timeout
            # Bare constructor when nothing is passed: the SDK resolves
            # ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / an `ant auth login`
            # profile itself. Don't pre-empt that with our own env lookup.
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def _build_payload(self, step: Step) -> dict[str, Any]:
        params = dict(step.params or {})

        payload: dict[str, Any] = {
            "model": step.model or self._default_model,
            "max_tokens": params.pop("max_tokens", DEFAULT_MAX_TOKENS),
            "messages": self._build_messages(step),
        }

        system = params.pop("system", None)
        if system:
            payload["system"] = system

        # Explicit: Opus 4.8 runs without thinking when the field is omitted.
        thinking_on = params.pop("thinking", self._thinking)
        payload["thinking"] = (
            {"type": "adaptive"} if thinking_on else {"type": "disabled"}
        )

        output_config: dict[str, Any] = {"effort": params.pop("effort", self._default_effort)}
        schema = params.pop("output_schema", None)
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        payload["output_config"] = output_config

        # Genblaze folds unknown step kwargs into params as model params. Anything
        # left is a caller mistake we shouldn't silently forward — temperature and
        # friends are a hard 400 on Opus 4.8, and a typo'd kwarg would otherwise
        # vanish into the request.
        rejected = {"temperature", "top_p", "top_k", "budget_tokens"}
        for key in list(params):
            if key in rejected:
                raise ProviderError(
                    f"{key!r} is not supported on {payload['model']} and returns a 400. "
                    "Steer with the prompt, or use output_config.effort for depth.",
                    error_code=ProviderErrorCode.INVALID_INPUT,
                )
        return payload

    def _build_messages(self, step: Step) -> list[dict[str, Any]]:
        parts: list[str] = []

        # Chain input: upstream TEXT steps carry their payload in metadata['text'].
        for asset in step.inputs or []:
            upstream = (asset.metadata or {}).get("text")
            if upstream:
                parts.append(str(upstream))

        if step.prompt:
            parts.append(str(step.prompt))

        if not parts:
            raise ProviderError(
                "anthropic-chat step has no prompt and no text input to chain from",
                error_code=ProviderErrorCode.INVALID_INPUT,
            )
        return [{"role": "user", "content": "\n\n".join(parts)}]


def text_of(step_or_asset: Any) -> str:
    """Pull the text payload back out of a step or asset produced by this provider."""
    assets = getattr(step_or_asset, "assets", None)
    asset = assets[0] if assets else step_or_asset
    return str((getattr(asset, "metadata", None) or {}).get("text", ""))


def json_of(step_or_asset: Any) -> Any:
    """text_of(), parsed. Only safe when the step declared an output_schema."""
    return json.loads(text_of(step_or_asset))
