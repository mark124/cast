# Cast demo video script (about 3 minutes)

Split into three parts so you can read the voiceover straight through. The beats are
numbered 1 to 6 and line up across all three parts, so action 3 and screen 3 go with
voiceover 3.

- **Part 1, Voiceover:** the lines to read. This is the whole spoken track, top to bottom.
- **Part 2, What you do:** the clicks and drags for each beat.
- **Part 3, What the screen shows:** what the viewer should see happen.

Talk like you are showing a friend, not presenting. If you fumble, pause and take the
line again; it trims cleanly.

---

## Setup (before you record)

- Open **cast.rowset.co** and hard-refresh. Voice is already set to **Daniel**.
- In a second browser tab, open the **Backblaze B2 web console** and Browse Files in the
  bucket **polyglot-mark-trans-lator**, into the `cast/` prefix. You will see
  `cast/assets/` (the generated audio, keyed by content hash) and `cast/manifests/`
  (one JSON per run). Open a recent manifest ahead of time so it is one click away.
- Do one throwaway run first (pick one language, Localize) so the providers are warm,
  then refresh before recording.
- Screen-record at 1080p, browser zoomed to about 110 percent. Optional webcam box in a
  corner.

---

## Part 1: Voiceover (read this straight through)

**1. Hook (0:00 to 0:15)**
> This is Cast. It takes one recording, in one voice, and turns it into every language,
> keeping that same voice the whole way through. Let me show you.

**2. Who it's for (0:15 to 0:45)**
> If you make a podcast, an audiobook, or a YouTube channel, your audience stops at the
> edge of your language. The tools that fix that are single-vendor black boxes. Cast is
> built for creators who want to re-voice their own content, reliably, at the scale of a
> whole catalog. As I pick languages, watch this counter. The languages Cast supports are
> the native tongue of over half the world.

**3. Fan-out and backpressure (0:45 to 1:30)**
> I'll localize into ten languages at once. Notice I set the concurrency lower than the
> number of languages, on purpose. Watch the queue drain as slots free up. That is real
> backpressure, the same way a production pipeline absorbs a burst of work. Under the
> hood, every language runs the same steps: AssemblyAI transcribes the original, Claude
> translates it, and ElevenLabs speaks it in the voice I chose. Genblaze orchestrates all
> of it, across providers and across steps.

**4. The failover moment (1:30 to 2:05)**
> Here is what makes it production-ready. I am going to pull the plug on ElevenLabs
> mid-run. In most tools, that kills your batch. In Cast, watch: every segment fails over
> to a second provider, LMNT, and keeps the same voice. No lost work, no restart. And
> that failover crosses providers, which the underlying SDK cannot do on its own, so we
> built it.

**5. Read-along and Backblaze B2 (2:05 to 2:40)**
> Every localized cut comes with a read-along transcript, and every file lands in
> Backblaze B2 as the system of record. B2 stores each result content-addressed, with a
> manifest that traces it back to the master it came from, so you always know exactly
> what was generated, and from what.

**6. Close (2:40 to 3:00)**
> So that is Cast. One recording in, your whole audience out, in a voice you choose, or
> clone as your own. Reliable across providers, auditable end to end, and built on
> Genblaze and Backblaze B2. It is live right now, at cast dot rowset dot co.

Optional line for beat 5, only if B2 Event Notifications is live:
> I can even drop a new file straight into the bucket, and B2 notifies Cast to localize
> it automatically. No dashboard, no upload step.

---

## Part 2: What you do (actions, by beat)

1. Nothing yet. Start with the page loaded and untouched.
2. Click four or five language chips one at a time, slowly: Spanish, Mandarin, Arabic,
   Hindi, French. Pause a beat between each.
3. Click **all** (top right of the picker). Drag the **Languages at once** slider down to
   **3**. Leave the voice on Daniel. Click **Localize**.
4. Let the run finish, or click **◼ Stop**. Click **none**, then pick just Spanish and
   French. Check the toggle **Simulate the main voice service failing**. Click
   **Localize** again.
5. On a finished language (Spanish), click **play & follow**. Let a sentence play, then
   click **full text**. After a few seconds, switch to your B2 console tab and open a file
   under `cast/` and one `manifests/` JSON.
6. Switch back to the Cast dashboard showing the finished languages.

Optional for beat 5: drop a file into the watched bucket folder, then switch back to Cast.

---

## Part 3: What the screen shows (by beat)

1. The dashboard at rest: the `Cast()` header, the Catherine Coleman source quote, the
   empty picker, and the line "pick languages to see who you can reach."
2. Each chip lights up amber as you click it, and the counter climbs and animates: "your
   pick reaches 2.1B people in their own language, 26% of the world," rising with each pick.
3. All chips go amber and the counter jumps to full reach; the slider reads 3 and the slot
   meter shows three lit slots. On Localize the button becomes "◼ Stop," ten rows appear
   as "queued," three go live (amber, spinner) while seven wait. Each live row cycles
   "translating with Claude..." to "speaking sentence 1..." to "stitching to the timing..."
   to "track ready," turns green, and a waiting row takes its place. The queue visibly
   drains and the working / waiting / done numbers move.
4. The two rows run, but each "spoke sentence" status now reads "via backup voice" with a
   purple "switched" badge, and the rows still finish green. The meter shows "2 used the
   backup voice," and the note reads "every language finished, even the ones whose main
   voice failed."
5. The caption panel expands: the source line in italics, the translated line below with
   each word lighting amber in time with the voice, a moving scrubber, and the full
   transcript list. Then the B2 view: content-addressed audio files under `cast/assets/...`
   and a `manifests/<run_id>.json` showing the run and its `parent_run_id` back to the
   original master.
6. The completed green rows and the reach counter, back on the main view.

Optional for beat 5: a new job starts on its own, with no clicks.

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
