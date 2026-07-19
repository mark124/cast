# Cast demo video script (about 3 minutes)

A read-from-the-page voiceover script for the submission video. Left column is what
you show on screen; right column is what you say. Written first person, in a founder's
voice. Target run time is about 2:50, which leaves room to breathe.

Recording tips: talk like you are showing a friend, not presenting. Pause at the line
breaks. If you fumble a line, pause and take it again; it is easy to trim. Screen
capture at 1080p, and if you want to be on camera, a small webcam box in a corner is
plenty.

---

## Hook (0:00 to 0:15)

**On screen:** the Cast homepage at cast.rowset.co, clean dashboard, the `Cast()` header.

**You say:**
> This is Cast. It takes one recording, in one voice, and turns it into every language,
> keeping that same voice the whole way through. Let me show you.

## Who it's for (0:15 to 0:45)

**On screen:** select a few language chips one at a time; the reach counter ticks up.

**You say:**
> If you make a podcast, an audiobook, or a YouTube channel, your audience stops at the
> edge of your language. The tools that fix that are single-vendor black boxes. Cast is
> built for creators who want to re-voice their own content, reliably, at the scale of a
> whole catalog. As I pick languages, watch this counter. The languages Cast supports are
> the native tongue of over half the world.

## Fan-out and backpressure (0:45 to 1:30)

**On screen:** set the concurrency lower than the number of languages, hit Localize, let
the queue drain from queued to active to done.

**You say:**
> I'll localize into ten languages at once. Notice I set the concurrency lower than the
> number of languages, on purpose. Watch the queue drain as slots free up. That is real
> backpressure, the same way a production pipeline absorbs a burst of work. Under the
> hood, every language runs the same steps: AssemblyAI transcribes the original, Claude
> translates it, and ElevenLabs speaks it in the voice I chose. Genblaze orchestrates all
> of it, across providers and across steps.

## The failover moment (1:30 to 2:05)

**On screen:** flip the "break ElevenLabs" toggle, run again, show rows failing over to
LMNT live.

**You say:**
> Here is what makes it production-ready. I am going to pull the plug on ElevenLabs
> mid-run. In most tools, that kills your batch. In Cast, watch: every segment fails over
> to a second provider, LMNT, and keeps the same voice. No lost work, no restart. And
> that failover crosses providers, which the underlying SDK cannot do on its own, so we
> built it.

## Read-along and Backblaze B2 (2:05 to 2:35)

**On screen:** expand a language's caption panel, words highlight as it plays; then show
the B2 bucket with the content-addressed files and a manifest.

**You say:**
> Every localized cut comes with a read-along transcript, and every file lands in
> Backblaze B2 as the system of record. B2 stores each result content-addressed, with a
> manifest that traces it back to the master it came from, so you always know exactly
> what was generated, and from what.

**Optional beat (only if B2 Event Notifications is live):**
> I can even drop a new file straight into the bucket, and B2 notifies Cast to localize
> it automatically. No dashboard, no upload step.

## Close (2:35 to 3:00)

**On screen:** back to the dashboard, the finished languages, the reach counter.

**You say:**
> So that is Cast. One recording in, your whole audience out, in a voice you choose, or
> clone as your own. Reliable across providers, auditable end to end, and built on
> Genblaze and Backblaze B2. It is live right now, at cast dot rowset dot co.

---

## Beats to hit (the rubric, without naming it)

- **Real-world utility:** named audience (podcasters, audiobook publishers, creators),
  their real problem, would actually use it.
- **Production readiness:** the failover moment, backpressure, "no lost work."
- **B2, meaningfully:** system of record, content-addressed, manifest lineage back to the
  master (and event notifications if shown).
- **Genblaze, meaningfully:** orchestration across providers and steps, the cross-provider
  failover the native primitive can't do.

## Do / don't

- Do run a real job on camera; the video must show the app actually working.
- Do let the failover moment land; it is the most memorable beat.
- Don't claim lip-sync or native fluency; the pitch is one voice identity across
  languages, which is what Cast delivers.
- Don't rush the reach counter or the queue drain; those two visuals do a lot of work.
