"""LmntTTSProvider — LMNT text-to-speech as a Genblaze Pipeline step, on the 2.x SDK.

Genblaze ships an LMNT connector, but it imports `from lmnt.api import Speech` — the
pre-2.0 SDK layout. Against the current `lmnt` package (2.13) that's a hard
ModuleNotFoundError inside generate() (see docs/upstream-findings.md #7). This provider
targets the 2.x client (`from lmnt import Lmnt`) so LMNT works as the failover TTS leg
without pinning the whole project back to a dead SDK line.

Same shape as the ElevenLabs connector's output path: synth bytes -> file:// asset, with
audio metadata from the format. Unlike the ElevenLabs connector it also sets `sha256`
over the audio bytes, so the asset passes Manifest.verify() before the B2 sink runs
rather than only after — cheap, and it makes a locally-produced clip self-verifying.

Kept minimal on purpose. LMNT is the *backup* voice; ElevenLabs is primary. This exists
so cross-provider failover is genuinely cross-provider.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

from genblaze_core.exceptions import ProviderError
from genblaze_core.models.asset import Asset, AudioMetadata
from genblaze_core.models.enums import Modality, ProviderErrorCode
from genblaze_core.models.step import Step
from genblaze_core.providers.base import ProviderCapabilities, SyncProvider
from genblaze_core.providers.model_registry import ModelRegistry
from genblaze_core.providers.retry import RetryPolicy
from genblaze_core.runnable.config import RunnableConfig

DEFAULT_MODEL = "blizzard"  # LMNT's multilingual model
DEFAULT_VOICE = "lily"
DEFAULT_FORMAT = "mp3"


def _map_error(exc: Exception) -> ProviderErrorCode:
    """Classify an lmnt SDK exception into Genblaze's taxonomy."""
    try:
        import lmnt
    except Exception:  # pragma: no cover - lmnt is a hard dep here
        return ProviderErrorCode.UNKNOWN
    if isinstance(exc, getattr(lmnt, "NotFoundError", ())):
        return ProviderErrorCode.MODEL_ERROR
    if isinstance(exc, getattr(lmnt, "RateLimitError", ())):
        return ProviderErrorCode.RATE_LIMIT
    if isinstance(exc, (getattr(lmnt, "AuthenticationError", ()), getattr(lmnt, "PermissionDeniedError", ()))):
        return ProviderErrorCode.AUTH_FAILURE
    if isinstance(exc, getattr(lmnt, "BadRequestError", ())):
        return ProviderErrorCode.INVALID_INPUT
    if isinstance(exc, getattr(lmnt, "APITimeoutError", ())):
        return ProviderErrorCode.TIMEOUT
    if isinstance(exc, getattr(lmnt, "APIConnectionError", ())):
        return ProviderErrorCode.SERVER_ERROR
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return ProviderErrorCode.SERVER_ERROR if status >= 500 else ProviderErrorCode.INVALID_INPUT
    return ProviderErrorCode.UNKNOWN


class LmntTTSProvider(SyncProvider):
    """Adapter for LMNT text-to-speech (lmnt>=2) as a Modality.AUDIO pipeline step.

    Args:
        api_key: LMNT API key. Falls back to LMNT_API_KEY.
        client: Pre-built lmnt.Lmnt — escape hatch for tests/shared clients.
        output_dir: Where to write the mp3. A tempfile is used if unset.

    Step params (via `.step(..., key=value)`):
        voice / voice_id: LMNT voice id (default "lily"). Pass a cloned voice's id
            here to speak in that voice.
        language: ISO code the target text is in (es, fr, ja, ...). LMNT's `language`
            enforces the target rather than guessing from the text.
        format: mp3 | wav | aac | ... (default mp3)
    """

    name = "lmnt"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any = None,
        output_dir: str | Path | None = None,
        default_voice: str = DEFAULT_VOICE,
        models: ModelRegistry | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        super().__init__(models=models, retry_policy=retry_policy)
        self._api_key = api_key
        self._client = client
        self._output_dir = Path(output_dir) if output_dir else None
        self._default_voice = default_voice

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_modalities=[Modality.AUDIO],
            supported_inputs=["text"],
            accepts_chain_input=True,
            models=[DEFAULT_MODEL],
            output_formats=["audio/mpeg", "audio/wav"],
        )

    def _resolve_client(self) -> Any:
        if self._client is None:
            from lmnt import Lmnt

            kwargs: dict[str, Any] = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            self._client = Lmnt(**kwargs)
        return self._client

    def generate(self, step: Step, config: RunnableConfig | None = None) -> Step:
        params = dict(step.params or {})
        text = step.prompt or ""
        # Chain input: an upstream TEXT step carries its payload on metadata["text"].
        if not text and step.inputs:
            text = (step.inputs[0].metadata or {}).get("text", "")
        if not text:
            raise ProviderError(
                "lmnt TTS step has no text (prompt or chained input)",
                error_code=ProviderErrorCode.INVALID_INPUT,
            )

        voice = params.get("voice") or params.get("voice_id") or self._default_voice
        fmt = params.get("format", DEFAULT_FORMAT)
        call: dict[str, Any] = {
            "text": text,
            "voice": voice,
            "model": step.model or DEFAULT_MODEL,
            "format": fmt,
        }
        if params.get("language"):
            call["language"] = params["language"]

        client = self._resolve_client()
        try:
            response = client.speech.generate(**call)
            audio_bytes = response.read()
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                f"LMNT TTS failed: {exc}",
                error_code=_map_error(exc),
            ) from exc

        ext = f".{fmt}" if not fmt.startswith(".") else fmt
        if self._output_dir:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            out_path = self._output_dir / f"{step.step_id}{ext}"
        else:
            fd, tmp = tempfile.mkstemp(suffix=ext)
            os.close(fd)
            out_path = Path(tmp)
        out_path.write_bytes(audio_bytes)

        from .._fileurl import sink_file_url

        asset = Asset(
            # Not as_uri() and not f"file://{quote(path)}": both are misread by the
            # installed 0.3.4 B2 sink on Windows. sink_file_url emits the one form it
            # round-trips (docs/upstream-findings.md #9).
            url=sink_file_url(out_path),
            media_type="audio/mpeg" if fmt == "mp3" else "audio/wav",
            sha256=hashlib.sha256(audio_bytes).hexdigest(),
            size_bytes=len(audio_bytes),
        )
        asset.metadata["audio_type"] = "speech"
        asset.metadata["voice"] = voice
        asset.audio = AudioMetadata(codec=fmt, channels=1)
        step.assets.append(asset)
        step.cost_usd = None
        return step
