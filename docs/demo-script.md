# Cast, 3-minute demo shot list

The video needs to show the app working and hit the four things the judges score:
real utility, production readiness, deep B2 use, deep Genblaze use. Face is **not
required**, a clean screen recording with clear voiceover is enough. If you want
presence, a small picture-in-picture webcam in a corner (Loom / OBS / Teams-style)
is standard.

Record at 1080p. Have the app open at `http://127.0.0.1:5050`, hard-refreshed, with
the tracks pre-generated once (so "play & follow" is instant on camera). Keep the
outage toggle **off** to start.

---

### 0:00 – 0:18 · Hook

**On screen:** the top of the page, the `Cast()` header, the Coleman source line, the
reach counter.
**Say:** "This is Cast. It takes one recording, a podcast, an audiobook, a talk, and
turns it into that same voice speaking every language. Here's a 96-second public-domain
clip of a NASA astronaut."

### 0:18 – 0:40 · The reach counter

**Do:** click **all** in the language picker. Let the counter animate up.
**Say:** "Pick your languages and the counter shows who you can reach, natively. All
of these together are the first language of over half the world, four-plus billion
people." *(Pause on the counter hitting its number.)*

### 0:40 – 1:20 · The fan-out (production readiness + backpressure)

**Do:** set "Languages at once" to 3, pick a voice, hit **Localize**.
**Say:** "Each language is its own pipeline. I've capped it at three at a time, so watch
the rest line up and take turns, this is the system handling a backlog without falling
over." *(Point at the slots filling, the queue draining, languages going live → done.)*
**Say:** "Behind each one: transcribe, translate with Claude, speak in the same voice,
stitch to the original timing, store in Backblaze B2, every step recorded."

### 1:20 – 2:00 · The kill shot (failover)

**Do:** tick **simulate the main voice service failing**, hit **Localize** again.
**Say:** "Now the important part. I'm pretending the main voice provider just went down.
Most tools would drop those languages." *(Watch the rows fail over.)*
**Say:** "Cast automatically fails over to a backup provider, mid-run, every language
still finishes." *(Point at "10 used the backup voice.")* "That's cross-provider failover
that Genblaze's built-in can't actually do, I had to build it."

### 2:00 – 2:40 · Read along (utility + the "same voice" payoff)

**Do:** click **▶ play & follow** on Mandarin. Let a line play with the karaoke
highlight. Open **▾ full text**. Then play Arabic to show right-to-left.
**Say:** "Click any language and read along, the words follow the voice, character by
character for Mandarin, right-to-left for Arabic. Same voice, every language. And the
whole passage is right here."

### 2:40 – 3:00 · The depth + close

**On screen:** briefly show the B2 bucket (content-addressed `assets/…` + `manifests/…`),
or the `docs/upstream-findings.md` list.
**Say:** "Everything lands in B2 as content-addressed objects with a verifiable manifest,
so you can prove how each result was made. Building this, I found nine issues in the
Genblaze SDK and wrote two connectors it was missing. Cast isn't another dubbing app.
It's the reliable, auditable way to localize a whole catalogue. Thanks for watching."

---

## Alternate hero (optional, stronger)

If you record a 30–60s clip of **your own voice** and clone it (LMNT dashboard, then
drop the voice id into `synthesize.VOICES`), open on *you* instead of the astronaut:
"I recorded this once, here's me in ten languages, in my own voice." Most authentic
version of the demo, zero consent issues.

## Do / don't

- **Do** let the counter and the queue *animate*, the motion is the point.
- **Do** trigger the outage live on camera; don't just describe it.
- **Don't** clone a celebrity/third-party voice, it undercuts the whole
  responsible-media pitch (and the providers' terms forbid it).
- **Don't** rush the read-along, the karaoke following the voice is the "wow".
