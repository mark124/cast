"""Speak one language's text, with cross-provider failover.

The TTS chain is ElevenLabs (primary) -> LMNT (backup). Both can carry a cloned
voice, so the localized cut keeps the speaker's identity even when the primary
provider stalls and we fail over on camera.

This is where the pipeline's headline reliability beat lives, and it's built on
cast.failover.run_with_failover rather than genblaze's fallback_models,
because that primitive can't cross providers and is inert on ElevenLabs anyway
(docs/upstream-findings.md #1, #2).

Voice note: pass a voice you have the right to use. The product is for creators
re-voicing their *own* content — a podcaster, an audiobook narrator, a YouTuber
localizing their own channel — so the cloned voice is consented by construction.
Don't wire in a clone of a third party who didn't agree to it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from genblaze_core import Modality

from .failover import Candidate, FailoverResult, run_with_failover
from .genblaze_lmnt2 import LmntTTSProvider

# eleven_flash_v2_5, not multilingual_v2: flash actually honors language_code (the
# multilingual_v2 model ignores it) and costs half the credits. See languages.py.
ELEVEN_MODEL = "eleven_flash_v2_5"
LMNT_MODEL = "blizzard"

# Voice settings for the ElevenLabs leg. similarity_boost is pushed high so a cloned
# voice hews tightly to the source sample (the demo's hero is a real person's clone,
# and the default ~0.75 smooths toward a generic-clean voice); stability slightly
# below the 0.5 default keeps natural expressiveness without introducing artifacts.
ELEVEN_SIMILARITY_BOOST = 0.9
ELEVEN_STABILITY = 0.4

# Per-language speaking pace (1.0 = provider default; <1 slows without changing pitch,
# via ffmpeg atempo in assemble.apply_tempo). Translations into the wordier languages
# expand ~20-30% over English and the TTS crams them into the same air, so those dubs
# sound rushed; easing them to 0.9 lets them breathe. English is the source and is
# never re-spoken, so it stays at 1.0. Confirmed by ear against Spanish at 0.90.
PACE_BY_LANG: dict[str, float] = {
    "es": 0.90, "fr": 0.90, "pt": 0.90, "it": 0.90, "de": 0.90, "ro": 0.90,
}
DEFAULT_PACE = 1.0


def pace_for(code: str) -> float:
    """The speaking-pace factor for a language code (1.0 if not eased)."""
    return PACE_BY_LANG.get(code, DEFAULT_PACE)


@dataclass(frozen=True)
class Voice:
    """The speaker to reproduce, addressed per provider.

    ElevenLabs and LMNT use different voice-id namespaces, so a single cloned
    speaker needs both ids. For the demo we use built-in voices we have the right
    to use; for a real creator these are the ids of their own cloned voice.
    """

    elevenlabs_id: str
    lmnt_id: str
    label: str = ""


def tts_chain(
    voice: Voice,
    *,
    output_dir: Path | None = None,
    elevenlabs_key: str | None = None,
    lmnt_key: str | None = None,
) -> list[Candidate]:
    """Build the ElevenLabs -> LMNT failover chain for one voice.

    Providers are constructed here (not shared) so a per-call output_dir works and
    so pulling one provider's key on camera fails only that leg.
    """
    from genblaze_elevenlabs import ElevenLabsTTSProvider

    from ._fileurl import NormalizeFileUrls

    eleven_kwargs: dict[str, Any] = {}
    if output_dir is not None:
        eleven_kwargs["output_dir"] = str(output_dir)
    if elevenlabs_key is not None:
        eleven_kwargs["api_key"] = elevenlabs_key

    return [
        Candidate(
            # Wrapped so its Windows-malformed file:// asset URLs are canonicalized
            # before the B2 sink reads them (docs/upstream-findings.md #9).
            provider=NormalizeFileUrls(ElevenLabsTTSProvider(**eleven_kwargs)),
            model=ELEVEN_MODEL,
            params={
                "voice_id": voice.elevenlabs_id,
                "output_format": "mp3_44100_128",
                # Hug the source sample so a cloned voice sounds like the real person.
                "similarity_boost": ELEVEN_SIMILARITY_BOOST,
                "stability": ELEVEN_STABILITY,
                # with_timestamps is intentionally OFF: the shipped connector's
                # timestamp path is broken against elevenlabs SDK 2.x — it reads
                # the AudioWithTimestampsResponse object as a dict, and the field
                # is audio_base_64 not audio_base64 (docs/upstream-findings.md #8).
                # We don't need it: word timings come from AssemblyAI on the source
                # side, which is what dub sync aligns to.
            },
        ),
        Candidate(
            provider=LmntTTSProvider(api_key=lmnt_key, output_dir=output_dir),
            model=LMNT_MODEL,
            params={"voice": voice.lmnt_id, "format": "mp3"},
        ),
    ]


def speak(
    text: str,
    *,
    language: str,
    voice: Voice,
    output_dir: Path | None = None,
    parent: Any | None = None,
    sink: Any | None = None,
    on_attempt=None,
    elevenlabs_key: str | None = None,
    lmnt_key: str | None = None,
) -> FailoverResult:
    """Synthesize `text` in `language`, trying ElevenLabs then LMNT.

    `language` is the ISO code the text is already in (es, fr, ja, ...). It's
    attached per provider in the shape each one expects: ElevenLabs takes
    language_code, LMNT takes language, so the chain sets both up front.
    """
    chain = tts_chain(
        voice, output_dir=output_dir, elevenlabs_key=elevenlabs_key, lmnt_key=lmnt_key
    )
    # Thread the language into each candidate's params in its own dialect.
    localized: list[Candidate] = []
    for cand in chain:
        params = dict(cand.params)
        if cand.provider.name == "elevenlabs":
            params["language_code"] = language
        else:
            params["language"] = language
        localized.append(Candidate(provider=cand.provider, model=cand.model, params=params))

    return run_with_failover(
        localized,
        prompt=text,
        modality=Modality.AUDIO,
        name=f"tts-{language}",
        parent=parent,
        sink=sink,
        on_attempt=on_attempt,
    )


# Selectable voices. Each pairs an ElevenLabs voice (primary) with a same-gender
# LMNT voice (backup). ElevenLabs IDs are verified against the live /v1/voices list.
# Note: within a preset the two are different providers' built-in voices, so a
# failover keeps the gender and register but not the exact timbre — true
# identical-across-providers voice needs one cloned sample uploaded to both, which
# is what a real creator does with their own voice.
VOICES: dict[str, Voice] = {
    "sarah":  Voice("EXAVITQu4vr4xnSDxMaL", "amy",     "Sarah (warm, female)"),
    "lily":   Voice("pFZP5JQG7iQjIQuC4Bku", "lily",    "Lily (British, female)"),
    "bella":  Voice("hpp4J3VqNfWAUOO0d1Us", "bella",   "Bella (bright, female)"),
    "george": Voice("JBFqnCBsd6RMkjVDRZzb", "james",   "George (storyteller, male)"),
    "daniel": Voice("onwK4e9ZLuTAKqWW03F9", "daniel",  "Daniel (broadcaster, male)"),
    "brian":  Voice("nPczCjzI2devNBz1zQrb", "brandon", "Brian (deep, male)"),
}
DEFAULT_VOICE = "daniel"


def _load_custom_voices() -> None:
    """Merge in any cloned voices from custom_voices.json at the project root.

    scripts/clone_my_voice.py writes that file after cloning a real voice to both
    ElevenLabs and LMNT, so a creator's own voice shows up in the picker with no code
    edit. Kept out of the source tree (gitignored) since it points at a specific
    person's cloned voice.
    """
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "custom_voices.json"
    if not path.exists():
        return
    try:
        for key, v in json.loads(path.read_text(encoding="utf-8")).items():
            VOICES[key] = Voice(v["elevenlabs_id"], v["lmnt_id"], v.get("label", key))
    except Exception:
        pass  # a malformed custom file shouldn't break the built-in voices


_load_custom_voices()

# Back-compat aliases used elsewhere in the code/scripts.
DEMO_VOICE_FEMALE = VOICES["sarah"]
DEMO_VOICE_MALE = VOICES["george"]
