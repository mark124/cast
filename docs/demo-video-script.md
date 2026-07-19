# Cast demo video script (about 3 minutes)

A three-track shooting script. For each beat:
- **Do** is the action you take (clicks, drags, tab switches).
- **Screen** is what the viewer should see happen as a result.
- **Say** is the voiceover line to read.

Read the Say lines in your own pace. Talk like you are showing a friend, not
presenting. If you fumble, pause and take the line again; it trims cleanly.

---

## Before you record (setup)

- Open **cast.rowset.co** and hard-refresh. Voice is already set to **Daniel**.
- In a second browser tab, open the **Backblaze B2 web console**, navigate into the
  bucket, and drill to the `cast/` prefix so the generated files and a `manifests/`
  JSON are one click away. You will switch to this tab for the storage beat.
- Do one throwaway run first (pick one language, Localize) so the providers are warm
  and the real run is snappy. Then refresh before recording.
- Screen-record at 1080p. If you want to be on camera, a small webcam box in a corner
  is plenty. Zoom the browser to about 110 percent so text reads on video.

---

## Hook (0:00 to 0:15)

**Do:** Nothing yet. Start with the page loaded and untouched.

**Screen:** The dashboard at rest: the `Cast()` header, the Catherine Coleman source
quote, the empty language picker, and the line "pick languages to see who you can reach."

**Say:**
> This is Cast. It takes one recording, in one voice, and turns it into every language,
> keeping that same voice the whole way through. Let me show you.

## Who it's for (0:15 to 0:45)

**Do:** Click four or five language chips one at a time, slowly: Spanish, Mandarin,
Arabic, Hindi, French. Pause a beat between each.

**Screen:** Each chip lights up amber as you click it, and the counter under the chips
climbs and animates: "your pick reaches 2.1B people in their own language, 26% of the
world," rising with each pick.

**Say:**
> If you make a podcast, an audiobook, or a YouTube channel, your audience stops at the
> edge of your language. The tools that fix that are single-vendor black boxes. Cast is
> built for creators who want to re-voice their own content, reliably, at the scale of a
> whole catalog. As I pick languages, watch this counter. The languages Cast supports are
> the native tongue of over half the world.

## Fan-out and backpressure (0:45 to 1:30)

**Do:** Click **all** (top right of the picker) to select every language. Drag the
**Languages at once** slider down to **3**. Leave the voice on Daniel. Then click
**Localize**.

**Screen:** All chips go amber and the counter jumps to full reach. The slider reads 3
and the slot meter shows three lit slots. On Localize the button becomes "◼ Stop," ten
rows appear as "queued," three go **live** (amber, with a spinner) while seven wait.
Each live row cycles through "translating with Claude...", "speaking sentence 1...",
"stitching to the timing...", "track ready," then turns green, and a waiting row takes
its place. The queue visibly drains, and the working / waiting / done numbers move.

**Say:**
> I'll localize into ten languages at once. Notice I set the concurrency lower than the
> number of languages, on purpose. Watch the queue drain as slots free up. That is real
> backpressure, the same way a production pipeline absorbs a burst of work. Under the
> hood, every language runs the same steps: AssemblyAI transcribes the original, Claude
> translates it, and ElevenLabs speaks it in the voice I chose. Genblaze orchestrates all
> of it, across providers and across steps.

## The failover moment (1:30 to 2:05)

**Do:** Let the run finish (or click **◼ Stop**). Click **none**, then pick just two
languages, Spanish and French. Check the toggle **Simulate the main voice service
failing**. Click **Localize** again.

**Screen:** The two rows run, but now each "spoke sentence" status reads "via **backup
voice**" with a purple **switched** badge, and the rows still finish green. The meter
shows "2 used the backup voice," and the closing note reads "every language finished,
even the ones whose main voice failed."

**Say:**
> Here is what makes it production-ready. I am going to pull the plug on ElevenLabs
> mid-run. In most tools, that kills your batch. In Cast, watch: every segment fails over
> to a second provider, LMNT, and keeps the same voice. No lost work, no restart. And
> that failover crosses providers, which the underlying SDK cannot do on its own, so we
> built it.

## Read-along and Backblaze B2 (2:05 to 2:40)

**Do:** On a finished language (Spanish), click **play & follow**. Let a sentence play,
then click **full text**. After a few seconds, switch to your B2 console tab and open a
file under `cast/` and one `manifests/` JSON.

**Screen:** The caption panel expands: the source line in italics, the translated line
below with each word lighting amber in time with the voice, a moving scrubber, and the
full transcript list. Then the B2 view: the content-addressed audio files under
`cast/assets/...` and a `manifests/<run_id>.json` showing the run and its `parent_run_id`
back to the original master.

**Say:**
> Every localized cut comes with a read-along transcript, and every file lands in
> Backblaze B2 as the system of record. B2 stores each result content-addressed, with a
> manifest that traces it back to the master it came from, so you always know exactly
> what was generated, and from what.

**Optional beat (only if B2 Event Notifications is live):**

**Do:** Drop a file into the watched bucket folder, then switch back to Cast.

**Screen:** A new job starts on its own, no clicks.

**Say:**
> I can even drop a new file straight into the bucket, and B2 notifies Cast to localize
> it automatically. No dashboard, no upload step.

## Close (2:40 to 3:00)

**Do:** Switch back to the Cast dashboard showing the finished languages.

**Screen:** The completed green rows and the reach counter, back on the main view.

**Say:**
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
  failover the native primitive cannot do.

## Do and don't

- Do run a real job on camera; the video must show the app actually working.
- Do let the failover moment land; it is the most memorable beat.
- Do keep the failover run small (two languages) so the "switched" badges are easy to see.
- Don't claim lip-sync or native fluency; the pitch is one voice identity across
  languages, which is what Cast delivers.
- Don't rush the reach counter or the queue drain; those two visuals do a lot of work.
