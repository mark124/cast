# Cast demo video script (under 3 minutes)

Split into three parts so you can read (or play) the voiceover straight through. Beats
are numbered and line up across all three parts, so action 3 and screen 3 go with
voiceover 3. Beat 6 is split into 6a (setup) and 6b (close) with a live moment between.

- **Part 1, Voiceover:** the spoken track. It is also generated as audio in Daniel's
  voice (`work/voice/vo_*.mp3`), so you can lay it over the screen recording instead of
  reading live.
- **Part 2, What you do:** the clicks and drags for each beat.
- **Part 3, What the screen shows:** what the viewer should see happen.

Keep the final cut under 3:00 (the rules are strict). No copyrighted music.

---

## Setup (before you record)

- Open **cast.rowset.co** and hard-refresh. Voice is already **Daniel**. The favicon is
  the amber Cast mark, so the browser tab looks finished.
- In a second tab, open the **Backblaze B2 console**, Browse Files in
  **polyglot-mark-trans-lator**, into `cast/`. Pre-open a recent manifest under
  `cast/manifests/` so it is one click away.
- Do one throwaway run first (pick one language, Localize) so the providers are warm.
- Screen-record at 1080p, browser zoomed to about 110 percent.

---

## Part 1: Voiceover (read or play straight through)

**1. Hook**
> This is Cast. It takes one recording, in one voice, and turns it into every language,
> keeping that same voice the whole way through. Let me show you.

**2. The original, and who it's for**
> Here is the original. One English speaker. If you make a podcast, an audiobook, or a
> YouTube channel, your audience stops at the edge of your language. Cast is built for
> creators who want to re-voice their own content, reliably, at the scale of a whole
> catalog. As I pick languages, watch this counter. The languages Cast supports are the
> native tongue of over half the world.

**3. Fan-out and backpressure**
> I'll localize into ten languages at once. Notice I set the concurrency lower than the
> number of languages, on purpose. Watch the queue drain as slots free up. That is real
> backpressure, the same way a production pipeline absorbs a burst of work. Under the
> hood, every language runs the same steps. AssemblyAI transcribes the original, Claude
> translates it, and ElevenLabs speaks it in the voice I chose. Genblaze orchestrates all
> of it, across providers and across steps.

**4. The failover moment**
> Here is what makes it production ready. I am going to pull the plug on ElevenLabs mid
> run. In most tools, that kills your batch. In Cast, watch. Every segment fails over to a
> second provider, LMNT, and keeps the same voice. No lost work, no restart. And that
> failover crosses providers, which the underlying SDK cannot do on its own, so we built it.

**5. Read-along and Backblaze B2**
> Every localized cut comes with a read-along transcript, in the same voice you heard a
> moment ago. And every file lands in Backblaze B2 as the system of record. B2 stores each
> result content addressed, with a manifest that traces it back to the master it came
> from, so you always know exactly what was generated, and from what.

**6a. The setup (before the live moment)**
> One more thing. Cast doesn't only localize this clip. I can type any line. So let me
> type one I definitely cannot say myself.

*(Now the live moment happens on screen: you type a line, localize it, and Cast speaks it
back in the same voice. See Part 2 and Part 3, beat 6.)*

**6b. The close (after the live moment)**
> Same voice. One recording in, your whole audience out, in a voice you choose, or clone
> as your own. Reliable across providers, auditable end to end, and built on Genblaze and
> Backblaze B2. It is live right now, at cast dot rowset dot co.

---

## Part 2: What you do (actions, by beat)

1. Nothing yet. Start with the page loaded and untouched.
2. Click **hear the original** and let a second of the source voice play, then stop it.
   Then click four or five language chips one at a time, slowly (Spanish, Mandarin,
   Arabic, Hindi, French).
3. Click **all**. Drag the **Languages at once** slider down to **3**. Leave the voice on
   Daniel. Click **Localize**.
4. Let it finish, or click **Stop**. Click **none**, then pick just Spanish and French.
   Check the toggle **Simulate the main voice service failing**. Click **Localize** again.
5. On a finished language (Spanish), click **play & follow**, let a sentence play, then
   click **full text**. Switch to the B2 tab and open a file under `cast/` and a
   `manifests/` JSON.
6. Back on Cast, click into the **type your own line** box and type:
   **I don't speak a word of French.** Make sure only **French** is selected, and click
   **Localize**. When the French clip is ready, click **play & follow** so it speaks the
   line back. (This is the punchline; let it play in full before the close.)

---

## Part 3: What the screen shows (by beat)

1. The dashboard at rest: the `Cast()` header, the source quote, the empty picker, and
   "pick languages to see who you can reach."
2. The original voice plays from the source. Then each chip lights amber as you click it,
   and the counter climbs and animates ("your pick reaches 2.1B people, 26% of the world").
3. All chips go amber and the counter jumps to full reach; the slot meter shows three lit
   slots. On Localize the button becomes "Stop," ten rows queue, three go live while seven
   wait. Rows cycle "translating with Claude" to "speaking sentence 1" to "track ready,"
   turn green, and waiting rows take their place. Each finished row also shows "stored N in
   B2." The queue visibly drains.
4. The two rows run, but each status now reads "via backup voice" with a purple "switched"
   badge, and both still finish green. The meter shows "2 used the backup voice."
5. The caption panel expands: the source line, the translated line with each word lighting
   amber in time with the voice, a moving scrubber, the full transcript. Then the B2 view:
   content-addressed files under `cast/assets/` and a `manifests/<run_id>.json` showing
   `parent_run_id` back to the master, plus the provider, model, and sha256.
6. The typed line appears in the source panel as "your line." One French row runs and
   stores to B2, then plays back "Je ne parle pas un mot de français" in the same Daniel
   voice that has narrated the whole video. (Optional caption: "same voice.")

---

## Beats to hit (the rubric, without naming it)

- **Real-world utility:** named audience, their real problem, and now they can type their
  own line, so it is a tool, not a fixed demo.
- **Production readiness:** the failover moment, backpressure, "no lost work."
- **B2, meaningfully:** system of record, content-addressed, manifest lineage back to the
  master, the "stored in B2" tag on every row.
- **Genblaze, meaningfully:** orchestration across providers and steps, the cross-provider
  failover the native primitive cannot do.

## Do and don't

- Do run real jobs on camera; the video must show the app actually working.
- Do let the failover moment and the closing punchline land; those are the memorable beats.
- Do keep the failover run small (two languages) so the "switched" badges are easy to see.
- Don't claim lip-sync or native fluency; the pitch is one voice identity across languages.
- Don't rush the reach counter, the queue drain, or the final French line.
