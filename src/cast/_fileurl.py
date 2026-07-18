r"""Emit file:// URLs the installed B2 sink can actually read on Windows.

genblaze-core 0.3.4's sink resolves a local asset URL with
`Path(unquote(urlparse(url).path)).resolve()`. On Windows that mishandles both the
shipped connectors' `file://{quote(winpath)}` (the drive gets encoded into the URL
host, path parses empty -> resolves to cwd) AND the standard `Path.as_uri()` form
`file:///C:/...` (the leading slash before the drive resolves to `C:Users\...`,
missing the separator). The one form 0.3.4 round-trips correctly is
`file://C:/Users/...` — drive in the authority, forward slashes. See
docs/upstream-findings.md #9.

`sink_file_url` builds that form; `NormalizeFileUrls` rewrites a provider's output
assets into it inside generate(), before run() hands them to the sink.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from genblaze_core.models.step import Step
from genblaze_core.providers.base import ProviderCapabilities, SyncProvider
from genblaze_core.runnable.config import RunnableConfig

_WIN_DRIVE = re.compile(r"^/?([A-Za-z]:.*)$")


def file_url_to_path(url: str) -> Path:
    """Recover a filesystem Path from any of the file:// shapes we might see."""
    if not url.startswith("file:"):
        return Path(url).resolve()
    parsed = urlparse(url)
    raw = parsed.path if parsed.path not in ("", "/") else parsed.netloc
    raw = unquote(raw).replace("\\", "/")
    m = _WIN_DRIVE.match(raw)  # /C:/... or C:/... -> C:/...
    if m:
        raw = m.group(1)
    return Path(raw).resolve()


def sink_file_url(path: str | Path) -> str:
    """A file:// URL the installed 0.3.4 sink reads correctly on Windows and POSIX."""
    resolved = str(Path(path).resolve()).replace("\\", "/")
    return "file://" + resolved


def to_canonical_file_uri(url: str) -> str:
    """Normalize any file:// URL (incl. the malformed shipped-connector form)."""
    if not url.startswith("file:"):
        return url
    return sink_file_url(file_url_to_path(url))


class NormalizeFileUrls(SyncProvider):
    """Delegates to an inner provider, then rewrites file:// asset URLs to the
    sink-readable form. Transparent to orchestration: forwards name + capabilities."""

    def __init__(self, inner: Any) -> None:
        super().__init__()
        self._inner = inner
        self.name = inner.name  # type: ignore[assignment]

    def get_capabilities(self) -> ProviderCapabilities:
        return self._inner.get_capabilities()

    def generate(self, step: Step, config: RunnableConfig | None = None) -> Step:
        step = self._inner.generate(step, config)
        for asset in step.assets:
            if asset.url and asset.url.startswith("file:"):
                asset.url = to_canonical_file_uri(asset.url)
        return step
