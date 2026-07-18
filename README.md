# Cast — one voice, every language

**Cast turns one recording into the same voice speaking every language.** Drop in a
podcast episode, an audiobook chapter, or any talk, and Cast transcribes it,
translates it, re-speaks it in a consistent voice, times it to the original, and
stores every result — with a verifiable record of how each one was made.

Built for the [Backblaze Generative Media Hackathon](https://backblaze-generative-media.devpost.com/)
on **Genblaze** and **Backblaze B2**.

> The name is a triple pun: `CAST()` is SQL (this lives in the RowSet family), and
> it's pod**cast** / broad**cast** / voice **cast**ing — which is exactly what it does.

---

## Who it's for

Audio creators localizing a back catalogue at scale:

- **Podcast networks** spinning up per-language feeds
- **Audiobook publishers** re-recording titles for new markets
- **YouTube / video creators** running separate-language channels (the MrBeast model)

These are audio-first sources with **no lips to sync**, so segment-level timing (the
~400ms that speech-to-text gives you) is exactly right — and the reliability and
audit trail matter, because they're processing hundreds of hours, not one clip.

**Reach:** the languages Cast supports are the *native* language of **53% of the
world — about 4.3 billion people** (Ethnologue 2026; native-speaker counts, which
don't double-count multilingual people the way total-speaker counts do). Mandarin,
Hindi, Spanish, Arabic, Bengali, and the rest are all in, with a live counter that
climbs as you add languages.

---

## What it does

One source fans out to many languages, live:

```
                         ┌─ Spanish  ▶ speaking sentence 3…
  Catherine Coleman ─────┼─ Mandarin ▶ done · read along
  (96s, public domain)   ├─ Hindi    ▶ queued
                         └─ Arabic   ▶ switched to backup voice ✓
```

- **Pick languages** (one, several, or all) and a voice.
- **Watch it work** — each language streams its own progress; a concurrency limit
  makes the queue visibly drain (backpressure).
- **See a provider fail, and recover** — flip "simulate outage" and every language
  automatically fails over from the primary voice provider to the backup, mid-run,
  with no lost work.
- **Read along** — click any finished language and the words highlight as the voice
  speaks them (per-character for Mandarin/Japanese, right-to-left for Arabic/Urdu),
  with the full passage on demand.

---

## How it works

Every language is one **Genblaze pipeline**, and every step produces a
hash-verified provenance manifest:

```
  transcribe            translate           speak (with failover)      assemble        store
 ┌──────────┐         ┌──────────┐         ┌────────────────────┐    ┌─────────┐    ┌────────┐
 │AssemblyAI│  ─────▶ │  Claude  │  ─────▶ │ ElevenLabs ⇄ LMNT  │──▶ │ ffmpeg  │──▶ │   B2   │
 │universal2│ text +  │ opus-4-8 │ per-    │  cross-provider    │    │ time-   │    │  CAS + │
 └──────────┘ timings └──────────┘ segment └────────────────────┘    │ synced  │    │ manifest│
                                                                      └─────────┘    └────────┘
   each localized cut's manifest carries parent_run_id back to the source transcript
```

1. **Transcribe** the source (AssemblyAI `universal-2`) into timed sentence segments.
2. **Translate** each segment with **Claude** (`claude-opus-4-8`), preserving segment
   IDs via structured output so the timing still maps.
3. **Speak** each segment, with real **cross-provider failover** (see below).
4. **Assemble** the segments back into one track, placed at the source's timing
   (ffmpeg `adelay`+`amix`), zero-based so an audio-only cut starts promptly.
5. **Store** the assets and manifests in **Backblaze B2**.

---

## Built on Genblaze

Cast uses Genblaze as the orchestration spine — and pushes on it hard enough to have
found nine issues and written two connectors it was missing (`docs/upstream-findings.md`).

- **Multi-provider pipelines.** Transcription, translation, and speech are each a
  `Pipeline` step through a Genblaze provider, composed and run through the SDK.
- **A real Anthropic connector, built from scratch.** Genblaze ships no Anthropic
  provider, so Claude couldn't be a pipeline step. `cast/genblaze_anthropic/`
  adds one — laid out to mirror the shipped `genblaze_nvidia` chat provider, whose
  own docstring anticipates exactly this ("when a second chat-as-Pipeline-step
  provider ships, extracting a base class is cheap"). This is that second one.
- **A working LMNT connector.** The shipped LMNT connector imports the pre-2.0 SDK
  and breaks on the current package; `cast/genblaze_lmnt2/` is a 2.x-compatible
  replacement so LMNT works as the failover leg.
- **Cross-provider failover the native primitive can't do.** Genblaze's
  `fallback_models` only swaps the model string against the *same* provider and fires
  only on `MODEL_ERROR` (and is inert on ElevenLabs, which never emits that code).
  `cast/failover.py` is a ~15-line loop that fails over across *providers* on
  *any* error — so pulling an API key mid-run actually recovers, which the built-in
  can't. Characterization tests pin both SDK limitations so the claim is provable.
- **Provenance.** Manifests are SHA-256 verified; each localized cut links back to its
  source transcript via `parent_run_id`.

Pinned to `genblaze-core==0.3.4` — the version PyPI actually ships (the GitHub README
documents APIs that aren't in the released package; see findings #6).

## Built on Backblaze B2

B2 is the **system of record**, not a dumb bucket:

- **Content-addressable storage** — assets live at `assets/<sha[:2]>/<sha[:4]>/<sha>.ext`,
  so the key *is* the integrity check and byte-identical output dedupes for free.
- **Manifests become provenance-complete on upload** — the sink hashes the bytes as it
  transfers them, so a cut that couldn't be verified locally verifies once it's in B2.
- **Object Lock ready** — one flag makes the manifests immutable for a retention window
  (the tamper-evident audit anchor a publisher needs), wired via `b2_sink(lock_days=N)`.

## Providers & models

| Stage | Provider | Model |
|---|---|---|
| Transcription | AssemblyAI | `universal-2` (99 languages, word timings) |
| Translation | Anthropic (Claude) | `claude-opus-4-8` |
| Speech — primary | ElevenLabs | `eleven_flash_v2_5` |
| Speech — failover | LMNT | `blizzard` |
| Storage | Backblaze B2 | S3-compatible, content-addressable |

---

## What makes it more than a wrapper

AI dubbing is a crowded commercial category. Cast isn't competing with the consumer
dubbers on "translate a video" — it's the **reliable, auditable orchestration layer**
for doing this across a catalogue:

- **Survives a provider outage mid-batch** (cross-provider failover) — single-vendor
  tools don't.
- **Every result carries a tamper-evident record** of what generated it, from what —
  a black-box dubber gives you an output and nothing else.
- **B2 as a durable, content-addressed system of record**, with Object Lock for
  immutability.

That maps directly onto the two rubric criteria most entrants forfeit — Production
Readiness and B2 + Data Orchestration.

---

## Run it locally

Requires Python 3.11+, `ffmpeg`, and API keys (below).

```bash
cd cast
python -m venv .venv && . .venv/Scripts/activate   # or .venv/bin/activate
pip install -e . -e ".[dev]"
cp .env.example .env      # then fill in the keys

python app/server.py      # http://127.0.0.1:5050
```

Keys needed in `.env`: `ASSEMBLYAI_API_KEY`, `ELEVENLABS_API_KEY`, `LMNT_API_KEY`,
`ANTHROPIC_API_KEY`, and `B2_KEY_ID` / `B2_APP_KEY` / `B2_BUCKET` / `B2_REGION`
(the region is the middle of your bucket's S3 endpoint, e.g. `us-east-005` — it must
be set explicitly). AssemblyAI and LMNT have free tiers; ElevenLabs Starter is $6.

Run tests: `pytest`. Produce a finished localized video from the CLI:
`python scripts/make_localized.py es`.

---

## Honest limitations

- **"Same voice" across a failover is exact only for a cloned voice** uploaded to both
  providers. The built-in demo presets pair a same-gender ElevenLabs and LMNT voice, so
  a failover keeps the register but not the identical timbre. A real creator clones
  their own voice to both, and then it's truly identical.
- **Segment-level sync (~400ms), not lip-accurate** — by design, for audio-first
  sources. Overlapping segments (a long translation running past the next) are summed;
  a per-segment time-fit is the next refinement.
- Voice cloning of a third party requires their consent (and the providers' terms
  require it) — Cast is for re-voicing *your own* content.

---

*Built by RowSet. The engine is new work for this hackathon; the reliability and
provenance discipline is carried over from RowSet's data-integrity work.*
