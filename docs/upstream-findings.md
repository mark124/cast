# Upstream findings — genblaze

Things we hit building Polyglot against `genblaze-core==0.3.4` (the version PyPI ships).
Each is reproducible; several have a test pinning the behaviour in `tests/test_failover.py`.

Written to be filed as issues. Tone matters: these are notes from someone who read the SDK
closely enough to hit its edges, not complaints. Several are already fixed on `main` and are
really *release* problems, which is a different and easier conversation.

---

## 1. `fallback_models` cannot cross providers

**Severity:** docs/expectation mismatch · **Status:** by design, but the docs don't say so

`_try_fallback_models` (`pipeline/pipeline.py:1224`) swaps the model string and re-invokes the
same provider object:

```python
for fb_model in ps.fallback_models:
    fb_step = self._build_step(ps, step.inputs or None)
    fb_step.model = fb_model            # only the model string changes
    result = invoke_fn(fb_step, config)  # invoke_fn is bound to ps.provider
```

`_build_step` (`:1189`) takes `provider` from the step, so there is no provider swap on either
the sync or async path (`:1393-1418`).

**Why it surprises:** the README frames fallback chains next to multi-provider orchestration
("swap Sora → Runway → Veo by changing one line"), which reads as provider failover. Writing
`.step(elevenlabs, model="eleven_flash_v2_5", fallback_models=["tts-1"])` sends *OpenAI's*
model slug to ElevenLabs, which 404s into `INVALID_INPUT` — no further fallback, step dies.

**Repro:** `tests/test_failover.py::test_sdk_fallback_models_cannot_cross_providers`

**Suggested fix:** a doc line stating fallback_models is same-provider-only. Optionally reject
slugs that don't validate against the bound provider's registry, so the failure is loud at
build time rather than silent at 3am.

---

## 2. `fallback_models` is inert on ElevenLabs

**Severity:** bug · **Status:** believed unreported

Fallback fires only on `ProviderErrorCode.MODEL_ERROR` (`:1240`). But
`genblaze_elevenlabs/_errors.py` has no `MODEL_ERROR` branch at all — its mapper covers rate
limit, auth, invalid input, timeout, and 5xx, then falls through to `UNKNOWN`. Since
`generate()` raises `ProviderError(error_code=map_elevenlabs_error(exc))`, **an ElevenLabs step
can never emit the one code that triggers fallback.** Configuring `fallback_models` on
ElevenLabs is silently dead code.

Of the shipped connectors, only `nvidia` and `replicate` appear to emit `MODEL_ERROR`, so this
likely affects more than one adapter.

**Repro:** `tests/test_failover.py::test_sdk_fallback_models_ignores_every_code_except_model_error`

**Suggested fix:** map ElevenLabs' unknown/unsupported-model responses (404 on `model_id`,
`model_not_found`) to `MODEL_ERROR`. A provider-contract test asserting every adapter can emit
`MODEL_ERROR` would catch the whole class.

---

## 3. `metadata=` on `step()` silently drifts the canonical hash

**Severity:** correctness, cross-version · **Status:** fixed on main, live on PyPI

On `0.3.4`, `Pipeline.step()` has no `metadata` parameter — it's `(..., expected_duration_sec,
**params)`. So `metadata={"foo": "bar"}` falls through `**params`, is normalized as a *model*
param, and lands in `Step.params` — **which is inside the manifest's canonical hash.** Two runs
producing byte-identical media get different manifest hashes because of a tagging dict.

This is precisely the hazard the SDK already guards against for two other names, in its own
words (`pipeline.py`, `step()`):

> Reject reserved param names that would silently land in `**params`. […] without this guard
> they get swallowed by `**params`, normalized as a model param, and either rejected by the
> upstream provider or — **worse — embedded in the manifest as part of Step.params, drifting
> the canonical hash.**

`inputs` and `input` are rejected. `metadata` is not — and it's the natural name to reach for,
because **`main` added `metadata=` as a real kwarg and the GitHub README documents it.** Anyone
copying current docs onto the current PyPI release corrupts their hashes silently.

`Pipeline.metadata()` has the same shape: documented, present on main, absent from 0.3.4
(`AttributeError`).

**Repro:** `tests/test_failover.py::test_we_never_pass_metadata_into_step_params`

**Suggested fix:** add `metadata` to the reserved-name guard on the 0.3.x line, so a
forward-looking call fails loudly instead of quietly poisoning provenance. Longer term, see #6.

---

## 4. `hasattr(genblaze_core, "ParquetSink")` raises instead of returning False

**Severity:** bug · **Status:** believed unreported (related to #55, distinct)

The lazy module `__getattr__` raises `OptionalDependencyError` — not an `AttributeError` — when
the parquet extra isn't installed. `hasattr` only swallows `AttributeError`, so capability
probing explodes rather than returning `False`:

```python
>>> hasattr(genblaze_core, "ParquetSink")
OptionalDependencyError: ...
```

This breaks the standard feature-detection idiom, plus `inspect` and some IDE introspection.

**Suggested fix:** raise `AttributeError` subclassing `OptionalDependencyError`, or catch and
re-raise as `AttributeError` with the install hint in the message.

---

## 5. OpenAI TTS voice allowlist is stale and enforced client-side

**Severity:** minor · **Status:** believed unreported

The OpenAI adapter hard-codes a 10-voice allowlist and rejects anything else **before any HTTP
call**. OpenAI currently ships 13 — `verse`, `marin`, and `cedar` are unreachable through
Genblaze even though the API accepts them.

**Suggested fix:** let the provider arbitrate, or make the allowlist advisory (warn, don't
block). Client-side allowlists of server-side enums drift by construction.

---

## 6. PyPI is three weeks behind `main`, and the README documents `main`

**Severity:** release process · **Status:** meta-issue behind #3

| Package | PyPI | main |
|---|---|---|
| `genblaze` | 0.4.1 | 0.4.3 |
| `genblaze-core` | **0.3.4** | 0.3.6 |
| `genblaze-s3` | 0.3.4 | 0.3.5 |

The CHANGELOG has a `## [0.5.0] - 2026-07-16` wave that isn't published. Practical effects for
anyone starting from the README: `genblaze_core.mocks` doesn't exist (it's `genblaze_core.testing`
on PyPI, which imports `pytest` at module scope, so mocks need pytest installed); `step(metadata=)`
and `Pipeline.metadata()` don't exist and fail per #3.

**Suggested fix:** publish, or version the README/docs to the released line. The mocks-need-pytest
coupling is worth breaking regardless — it puts a test dependency in the path of anyone building
against fakes, which is the behaviour you *want* from people integrating a paid-provider SDK.

---

## 7. LMNT connector imports the old 1.x SDK API

**Severity:** bug, cross-version · **Status:** believed unreported

`genblaze_lmnt/provider.py` does `from lmnt.api import Speech`. The current `lmnt`
package (2.13.0) has no `lmnt.api` module — that's the pre-2.x layout. Installing
`lmnt` today and calling the LMNT provider fails at import inside `generate()`:

```
ModuleNotFoundError: No module named 'lmnt.api'
```

The 2.x SDK is a Stainless-generated client: `from lmnt import Lmnt`, then
`client.speech.generate(text=, voice=, language=, model="blizzard", format="mp3")`
and `client.voices.create(file=, name=)` for cloning. Same class of drift as #6 —
the pinned dependency and the shipped code disagree.

**Suggested fix:** pin `lmnt<2` in the connector's deps, or port the adapter to the
2.x surface. The latter is small and unlocks the current SDK's cloning + language
enums.

---

## 8. ElevenLabs `with_timestamps` path is broken on elevenlabs SDK 2.x

**Severity:** bug · **Status:** believed unreported

`genblaze_elevenlabs/provider.py` (0.3.1), timestamp branch:

```python
response = client.text_to_speech.convert_with_timestamps(**kwargs)
audio_bytes = base64.b64decode(response.get("audio_base64", ""))   # response is not a dict
alignment = response.get("alignment", {})
```

Against `elevenlabs` 2.58, `convert_with_timestamps` returns an
`AudioWithTimestampsResponse` **object**, so `.get(...)` raises
`'AudioWithTimestampsResponse' object has no attribute 'get'` and the whole TTS
step fails. Two bugs stacked: it's an object not a dict, and the field is
`audio_base_64` (underscores), not `audio_base64`.

Observed live: any ElevenLabs step with `with_timestamps=True` throws, code
`UNKNOWN`. Reproduced in `scripts/e2e_proof.py` (the failure that first fired our
failover chain). Workaround in Polyglot: leave `with_timestamps` off and take word
timings from AssemblyAI on the source side.

**Suggested fix:** read attributes off the model — `response.audio_base_64`,
`response.alignment.characters`, etc. Same class of SDK drift as #6/#7.

---

## 9. Local file:// asset URLs are unreadable by the 0.3.4 B2 sink on Windows

**Severity:** bug, Windows-only · **Status:** believed unreported

Two halves compound. The connectors build asset URLs as
`f"file://{quote(str(path.resolve()))}"`. On Windows `quote` percent-encodes the
drive colon and backslashes (`file://C%3A%5CUsers%5C...`), so `urlparse` puts the
whole path in `netloc` and leaves `path` empty. Then the 0.3.4 sink
(`genblaze_core/storage/transfer._read_local_file`) resolves it with:

```python
path = unquote(parsed.path)          # ''
resolved = Path(path).resolve()      # -> the cwd
```

→ `StorageError: local file path <cwd> is outside allowed directories`, so **no
asset ever transfers to B2 from a Windows producer**. Even the standard
`Path.as_uri()` form (`file:///C:/...`) fails this sink: `Path("/C:/Users/...")`
resolves to `C:Users\...` (drive separator dropped). The only form 0.3.4 round-trips
is `file://C:/Users/...` (drive in authority, forward slashes).

Note the installed 0.3.4 sink and repo `main` disagree here — `main` uses
`url2pathname`, which handles `as_uri()` correctly. So this is partly a
release-lag bug, but 0.3.4 is what `pip install` ships and what judges will run.

Repro: any TTS/image/video step feeding an `ObjectStorageSink` on Windows.
Workaround in Polyglot: `_fileurl.sink_file_url` emits the accepted form; the LMNT
connector uses it directly and `NormalizeFileUrls` rewrites the ElevenLabs
connector's URLs before the sink reads them.

**Suggested fix:** build asset URLs with `Path.as_uri()` in the connectors, and in
the 0.3.4 sink parse local URLs with `url2pathname` (as main already does) instead
of `unquote` + `Path`.

**Related, and worse: two connectors want opposite Windows file:// forms.** The
AssemblyAI connector validates that a `file://` input URL has an empty/`localhost`
netloc — i.e. it *requires* `file:///C:/...` (as_uri) and rejects `file://C:/...`
with `file:// URL must have empty or 'localhost' netloc; got 'C:'`. The 0.3.4 sink
requires the exact opposite (`file://C:/...`). So a Windows pipeline can't use one
URL convention throughout: input to AssemblyAI must be `as_uri()`, output to the
sink must be `sink_file_url`. Fixing local file:// handling to `url2pathname`
everywhere would make both accept the standard `as_uri()` form and remove the
contradiction.

---

## Contribution: an Anthropic chat provider

**Type:** new connector · **Status:** built, tested against the live API

Genblaze ships no Anthropic connector, so Claude can't be composed into a Pipeline —
only OpenAI, Google, and NVIDIA cover the chat/LLM modality. `NvidiaChatProvider`'s own
docstring anticipates the gap:

> "there's only one concrete chat-as-Pipeline-step provider today (NVIDIA). When a second
> one ships (Whisper, Gemini chat), extracting a base class is cheap; building one for a
> single consumer is premature."

`cast.genblaze_anthropic.AnthropicChatProvider` is a second one. It's laid out to mirror
`genblaze_nvidia/` (`provider.py` + `_errors.py` + `__init__.py`), emits `Modality.TEXT` with
the text on `Asset.metadata["text"]` and a sha256 over the text bytes exactly as the NVIDIA
provider does, supports structured outputs via `output_config.format`, and maps a 404 to
`MODEL_ERROR` so `fallback_models` actually works on it (unlike ElevenLabs, finding #2). It
handles the Opus 4.8 surface correctly: adaptive thinking set explicitly, `temperature`/`top_p`/
`top_k`/`budget_tokens` rejected before egress, refusals surfaced as `CONTENT_POLICY` instead
of an `IndexError`. Offered upstream as the base for extracting the shared `ChatProvider` the
NVIDIA docstring describes.

## Not a finding: `Manifest.verify()` doesn't fetch bytes

Recorded because we chased it and it's correct.

`verify()` checks the manifest hash and requires every output asset to declare a valid sha256; it
does not dereference `asset.url`. This is **documented** (`docs/features/trust-modes.md`: "Manifest.verify()
and genblaze verify do not fetch asset.url and re-hash remote bytes"), **disclosed at runtime** on
the CLI's *success* path ("Asset bytes were not fetched or compared"), and **already hardened**
against downgrade bypasses (`docs/exec-plans/completed/issue-77-url-only-asset-integrity.md`).

The caller responsibility is stated plainly in the README, and Polyglot honours it: anything we
fetch from B2, we re-hash before trusting. Working as designed and honestly documented.
