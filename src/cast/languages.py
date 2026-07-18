"""Language catalogue with provider depth, RTL, and speaker counts.

Two things live here:

1. **Provider depth** — how many TTS providers can voice a language. This decides
   whether failover is survivable: a language no backup speaks fails open the
   moment the primary stalls. `voices` is the failover order.

2. **Reach** — L1 (native) and total (L1+L2) speaker counts, so the "you can talk
   to most of the world" claim is computed from data, not asserted. Native-speaker
   coverage is the honest headline metric: native languages don't double-count the
   way total (L1+L2) does, because a person has essentially one native language,
   whereas the same multilingual person is counted under every language they speak
   as a second language.

Speaker figures: Ethnologue 2026 via Wikipedia "languages by total number of
speakers" (L1+L2), captured 2026-07-17. Arabic is modelled as its spoken varieties
(~270M L1) rather than Modern Standard Arabic (0 L1, a written standard) — a TTS
tool serving Arabic output reaches those native speakers.

Provider notes: AssemblyAI universal-2 transcribes 99 languages, so transcription
is not the constraint. Translation is Claude (effectively any language). The
constraint is TTS: cloning-capable providers are ElevenLabs and LMNT. LMNT's model
covers 31 languages incl. Mandarin and the major Indian languages (Hindi, Bengali,
Tamil, Telugu, Marathi, Urdu); ElevenLabs eleven_v3 covers 74. OpenAI (57) can say
the words but not in a cloned voice, so it never counts as a voice backup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

# World population, 2026 (~8.2B). Used only for the coverage fraction.
WORLD_POPULATION_M = 8_200


class Tier(IntEnum):
    """How deep the voice-cloning bench is for a language."""

    QUAD = 4  # ElevenLabs + LMNT + Hume + OpenAI
    TRIPLE = 3  # ElevenLabs + LMNT + OpenAI  (voice-preserving backup intact)
    PAIR = 2  # ElevenLabs + OpenAI          (no voice-preserving backup)
    SOLO = 1  # single provider


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1 (or common code)
    name: str
    tier: Tier
    voices: tuple[str, ...] = field(default_factory=tuple)  # failover order, best-first
    rtl: bool = False
    l1_speakers_m: float = 0.0  # native speakers, millions
    total_speakers_m: float = 0.0  # L1 + L2, millions
    notes: str = ""

    @property
    def depth(self) -> int:
        return len(self.voices)

    @property
    def has_voice_backup(self) -> bool:
        """True if a second provider can preserve the cloned voice (EL + LMNT)."""
        return len([p for p in self.voices if p in _CLONING_PROVIDERS]) >= 2


_CLONING_PROVIDERS = frozenset({"elevenlabs", "lmnt"})

_QUAD = ("elevenlabs", "lmnt", "hume", "openai")
_TRIPLE = ("elevenlabs", "lmnt", "openai")
_EL_LMNT = ("elevenlabs", "lmnt")
_PAIR = ("elevenlabs", "openai")
_LMNT_ONLY = ("lmnt", "openai")  # LMNT clones; OpenAI can only echo

SOURCE = Language("en", "English", Tier.QUAD, _QUAD, l1_speakers_m=450, total_speakers_m=1530)

# Tier 1 — four cloning providers deep. Safest to demo failover in.
TIER_1: tuple[Language, ...] = (
    Language("es", "Spanish", Tier.QUAD, _QUAD, l1_speakers_m=487, total_speakers_m=561),
    Language("fr", "French", Tier.QUAD, _QUAD, l1_speakers_m=75, total_speakers_m=334),
    Language("de", "German", Tier.QUAD, _QUAD, l1_speakers_m=76, total_speakers_m=133),
    Language("it", "Italian", Tier.QUAD, _QUAD, l1_speakers_m=65, total_speakers_m=68),
    Language("ja", "Japanese", Tier.QUAD, _QUAD, l1_speakers_m=124, total_speakers_m=126),
    Language("hi", "Hindi", Tier.QUAD, _QUAD, l1_speakers_m=347, total_speakers_m=611,
             notes="India; higher TTS-quality risk"),
    Language("pt", "Portuguese", Tier.QUAD, _QUAD, l1_speakers_m=252, total_speakers_m=269),
    Language("ko", "Korean", Tier.QUAD, _QUAD, l1_speakers_m=80, total_speakers_m=82),
    Language("ru", "Russian", Tier.QUAD, _QUAD, l1_speakers_m=133, total_speakers_m=210),
    Language("ar", "Arabic", Tier.QUAD, _QUAD, rtl=True, l1_speakers_m=270, total_speakers_m=400,
             notes="spoken varieties as L1; RTL — verify caption shaping"),
)

# Tier 2 — voice backup intact (EL + LMNT), Hume absent. Includes Mandarin and the
# major Indian languages, which is what makes the world-reach claim land.
TIER_2: tuple[Language, ...] = (
    Language("zh", "Mandarin Chinese", Tier.TRIPLE, _TRIPLE, l1_speakers_m=988, total_speakers_m=1183),
    Language("bn", "Bengali", Tier.TRIPLE, _EL_LMNT, l1_speakers_m=234, total_speakers_m=274,
             notes="India/Bangladesh"),
    Language("ur", "Urdu", Tier.TRIPLE, _EL_LMNT, rtl=True, l1_speakers_m=78, total_speakers_m=246,
             notes="Pakistan/India; RTL"),
    Language("ta", "Tamil", Tier.TRIPLE, _TRIPLE, l1_speakers_m=79, total_speakers_m=86, notes="India"),
    Language("te", "Telugu", Tier.TRIPLE, _EL_LMNT, l1_speakers_m=83, total_speakers_m=96, notes="India"),
    Language("mr", "Marathi", Tier.TRIPLE, _EL_LMNT, l1_speakers_m=83, total_speakers_m=99, notes="India"),
    Language("id", "Indonesian", Tier.TRIPLE, _TRIPLE, l1_speakers_m=78, total_speakers_m=255),
    Language("vi", "Vietnamese", Tier.TRIPLE, _TRIPLE, l1_speakers_m=86, total_speakers_m=97),
    Language("tr", "Turkish", Tier.TRIPLE, _TRIPLE, l1_speakers_m=86, total_speakers_m=94),
    Language("nl", "Dutch", Tier.TRIPLE, _TRIPLE, l1_speakers_m=25, total_speakers_m=30),
    Language("pl", "Polish", Tier.TRIPLE, _TRIPLE, l1_speakers_m=40, total_speakers_m=41),
    Language("uk", "Ukrainian", Tier.TRIPLE, _TRIPLE, l1_speakers_m=27, total_speakers_m=39),
)

# Tier 3 — reachable, but no voice-preserving backup. Offer them; don't demo failover.
TIER_3: tuple[Language, ...] = (
    Language("sv", "Swedish", Tier.PAIR, _PAIR, l1_speakers_m=10, total_speakers_m=13),
    Language("cs", "Czech", Tier.PAIR, _PAIR, l1_speakers_m=11, total_speakers_m=11),
    Language("da", "Danish", Tier.PAIR, _PAIR, l1_speakers_m=6, total_speakers_m=6),
    Language("fi", "Finnish", Tier.PAIR, _PAIR, l1_speakers_m=5, total_speakers_m=5),
    Language("el", "Greek", Tier.PAIR, _PAIR, l1_speakers_m=13, total_speakers_m=13),
    Language("ro", "Romanian", Tier.PAIR, _PAIR, l1_speakers_m=24, total_speakers_m=25),
)

ALL: tuple[Language, ...] = TIER_1 + TIER_2 + TIER_3
BY_CODE: dict[str, Language] = {lang.code: lang for lang in (SOURCE,) + ALL}

# The world-reach demo: English source + the highest-population languages we can
# voice, spanning the biggest speaker bases (Mandarin, Hindi, Spanish, Arabic,
# Bengali, Portuguese, Russian, Japanese, French, Indonesian). This is the set the
# demo fans out to — it's what makes "talk to most of the world" visible.
DEMO_WORLD: tuple[str, ...] = (
    "zh", "hi", "es", "ar", "bn", "pt", "ru", "ja", "fr", "id",
)

# The original 4-provider-deep set, for showing failover safely on camera.
DEMO_SET: tuple[str, ...] = tuple(lang.code for lang in TIER_1)


def get(code: str) -> Language:
    try:
        return BY_CODE[code]
    except KeyError:
        raise ValueError(
            f"unknown language {code!r}; known: {', '.join(sorted(BY_CODE))}"
        ) from None


def resolve(codes: object) -> tuple[Language, ...]:
    if isinstance(codes, str):
        raise TypeError("pass a sequence of codes, not a bare string")
    return tuple(get(c) for c in codes)  # type: ignore[union-attr]


@dataclass(frozen=True)
class Coverage:
    languages: int
    native_speakers_m: float  # summed L1 — safe to sum, ~no double count
    native_fraction: float  # of world population
    total_speakers_m: float  # summed L1+L2 — double-counts multilinguals; upper bound

    @property
    def native_billions(self) -> float:
        return round(self.native_speakers_m / 1000, 2)

    @property
    def native_percent(self) -> int:
        return round(self.native_fraction * 100)


def coverage(codes: object = None) -> Coverage:
    """Compute reach across a set of languages (default: the whole catalogue + English).

    `native_fraction` is the honest headline: the share of the world whose *native*
    language is one we support. `total_speakers_m` is reported too but is an upper
    bound — it double-counts anyone who speaks more than one supported language.
    """
    langs = (SOURCE,) + ALL if codes is None else resolve(codes)
    seen = {lang.code: lang for lang in langs}.values()  # dedupe
    l1 = sum(lang.l1_speakers_m for lang in seen)
    total = sum(lang.total_speakers_m for lang in seen)
    return Coverage(
        languages=len(list(seen)),
        native_speakers_m=l1,
        native_fraction=l1 / WORLD_POPULATION_M,
        total_speakers_m=total,
    )
