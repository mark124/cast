"""Map Anthropic SDK exceptions onto Genblaze's provider error taxonomy.

Deliberately maps NotFoundError -> MODEL_ERROR. That is the one code
`Pipeline._try_fallback_models` acts on, so a bad model slug on this provider
actually triggers the SDK's fallback chain. The shipped ElevenLabs mapper has no
MODEL_ERROR branch at all, which silently makes `fallback_models` dead code
there (see docs/upstream-findings.md #2) — this connector doesn't repeat that.
"""

from __future__ import annotations

from typing import Any

import anthropic
from genblaze_core.models.enums import ProviderErrorCode


def map_anthropic_error(exc: Exception) -> ProviderErrorCode:
    """Classify an Anthropic SDK exception.

    Ordered most-specific-first: several of these subclass APIStatusError, so a
    broad check would swallow the precise ones.
    """
    # 404 means the model slug doesn't exist. MODEL_ERROR is what lets a caller's
    # fallback_models chain retry on a different model.
    if isinstance(exc, anthropic.NotFoundError):
        return ProviderErrorCode.MODEL_ERROR
    if isinstance(exc, anthropic.RateLimitError):
        return ProviderErrorCode.RATE_LIMIT
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return ProviderErrorCode.AUTH_FAILURE
    if isinstance(exc, anthropic.BadRequestError):
        return ProviderErrorCode.INVALID_INPUT
    if isinstance(exc, anthropic.APITimeoutError):
        return ProviderErrorCode.TIMEOUT
    # Must follow APITimeoutError — in this SDK it's a sibling of APIConnectionError,
    # but ordering here keeps the intent obvious.
    if isinstance(exc, anthropic.APIConnectionError):
        return ProviderErrorCode.SERVER_ERROR
    if isinstance(exc, anthropic.APIStatusError):
        return (
            ProviderErrorCode.SERVER_ERROR
            if exc.status_code >= 500
            else ProviderErrorCode.INVALID_INPUT
        )
    return ProviderErrorCode.UNKNOWN


def retry_after_seconds(exc: Exception) -> float | None:
    """Pull a Retry-After hint off a rate-limit response, if the SDK exposed one."""
    response: Any = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None  # HTTP-date form; let the retry policy fall back to backoff
