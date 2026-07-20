# Cast demo video script (under 3 minutes)

Three parts. **Part 2 is the one you record from**: a step-by-step sequence that says
exactly which voiceover clip to play and when to trigger a sound. Part 1 is the spoken
text for reference; Part 3 is what should be on screen.

The voiceover is generated in Daniel's voice as clips in `work/voice/`:
`vo_1_hook`, `vo_2a_source`, `vo_2b_audience`, `vo_3_fanout`, `vo_4_failover`,
`vo_5a_readalong`, `vo_5b_b2`, `vo_6_close` (plus `vo_full` = all of them stitched with
gaps where the sounds go).

Keep the final cut under 3:00 (strict). No copyrighted music.

---

## Setup (before you record)

- Open **cast.rowset.co** and hard-refresh. Voice is already **Daniel**.
- In a second tab, open the **Backblaze B2 console**, Browse Files in
  **polyglot-mark-trans-lator** into `cast/`, and pre-open a recent `cast/manifests/`
  JSON so it is one click away.
- Do one throwaway run first (pick one language, Localize) so the providers are warm.
- **Audio:** capture **system/desktop audio** (OBS "Desktop Audio", or Game Bar), not a
  mic pointed at speakers. Keep the browser/app volume moderate (not maxed) and steady.
  Mute notifications. You can normalize loudness afterward.
- Screen-record at 1080p, browser zoomed to about 110 percent.

---

## Part 2: Recording sequence (record from this)

Each step is either **[VO]** play a voiceover clip, **[SOUND]** trigger an app sound, or
**[DO]** an on-screen action. Let each clip finish before the next step unless it says
"while it plays."

1. **[VO] vo_1_hook**: page sitting at rest, do not touch anything.
2. **[VO] vo_2a_source** ("Here is the original. One English speaker.")
3. **[SOUND] [DO]** Click **hear the original**. Let about two seconds of the astronaut's
   voice play, then click it again to stop.
4. **[VO] vo_2b_audience**: *while it plays*, click four or five language chips one at a
   time, slowly (Spanish, Mandarin, Arabic, Hindi, French). The counter climbs.
5. **[VO] vo_3_fanout**: *while it plays*: click **all**, drag **Languages at once** to
   **3**, click **Localize**. Let the queue drain (rows go live, finish green, waiting
   ones start). The fan-out's own audio can murmur under the narration; that's fine.
6. **[VO] vo_4_failover**: first let the run finish or click **Stop**, click **none**,
   pick **Spanish and French**, check **Simulate the main voice service failing**, then
   click **Localize**. Let the rows show "via backup voice" and finish green.
7. **[VO] vo_5a_readalong** ("...in the same voice you heard a moment ago.")
8. **[SOUND] [DO]** On the Spanish row, click **play & follow**. Let a few seconds play so
   the words highlight in time with the voice. Optionally click **full text**.
9. **[VO] vo_5b_b2**: *while it plays*, switch to the B2 tab and open a file under
   `cast/assets/` and a `cast/manifests/` JSON (show the `parent_run_id`, provider, sha).
10. **[VO] vo_6_close**: switch back to the Cast dashboard (finished green rows, counter).

The two sounds that matter are step 3 (hear the original) and step 8 (the read-along).
Everything else is narration over silent or lightly-murmuring screen action.

---

## Part 1: Voiceover text (for reference)

- **vo_1_hook:** This is Cast. It takes one recording, in one voice, and turns it into
  every language, keeping that same voice the whole way through. Let me show you.
- **vo_2a_source:** Here is the original. One English speaker.
- **vo_2b_audience:** If you make a podcast, an audiobook, or a YouTube channel, your
  audience stops at the edge of your language. Cast is built for creators who want to
  re-voice their own content, reliably, at the scale of a whole catalog. As I pick
  languages, watch this counter. The languages Cast supports are the native tongue of
  over half the world.
- **vo_3_fanout:** I'll localize into ten languages at once. Notice I set the concurrency
  lower than the number of languages, on purpose. Watch the queue drain as slots free up.
  That is real backpressure, the same way a production pipeline absorbs a burst of work.
  Under the hood, every language runs the same steps. AssemblyAI transcribes the original,
  Claude translates it, and ElevenLabs speaks it in the voice I chose. Genblaze
  orchestrates all of it, across providers and across steps.
- **vo_4_failover:** Here is what makes it production ready. I am going to pull the plug on
  ElevenLabs mid run. In most tools, that kills your batch. In Cast, watch. Every segment
  fails over to a second provider, LMNT, and keeps the same voice. No lost work, no
  restart. And that failover crosses providers, which the underlying SDK cannot do on its
  own, so we built it.
- **vo_5a_readalong:** Every localized cut comes with a read-along transcript, in the same
  voice you heard a moment ago.
- **vo_5b_b2:** And every file lands in Backblaze B2 as the system of record. B2 stores
  each result content addressed, with a manifest that traces it back to the master it came
  from, so you always know exactly what was generated, and from what.
- **vo_6_close:** So that is Cast. One recording in, your whole audience out, in a voice
  you choose, or clone as your own. Reliable across providers, auditable end to end, and
  built on Genblaze and Backblaze B2. It is live right now, at cast dot rowset dot co.

---

## Part 3: What the screen shows (by step)

1. The dashboard at rest: the `Cast()` header, the source quote, the empty picker.
2-3. The original (astronaut) voice plays from the source.
4. Each chip lights amber as you click; the counter climbs and animates.
5. All chips amber, counter at full reach, three lit slots. On Localize: rows queue,
   three go live while seven wait, statuses cycle to "track ready," rows turn green and
   show "stored N in B2," waiting rows take their place. The queue drains.
6. Two rows run; each status reads "via backup voice" with a purple "switched" badge; both
   finish green; the meter shows "2 used the backup voice."
7-8. The caption panel expands; the translated line highlights word by word in time with
   the voice; the full transcript is listed.
9. The B2 view: content-addressed files under `cast/assets/` and a `manifests/<run_id>.json`
   showing `parent_run_id` back to the master, plus provider, model, and sha256.
10. The finished green rows and the reach counter, back on the main view.

---

## Beats to hit (the rubric, without naming it)

- **Real-world utility:** named audience, real problem, would actually use it.
- **Production readiness:** the failover moment, backpressure, "no lost work."
- **B2, meaningfully:** system of record, content-addressed, manifest lineage, the
  "stored in B2" tag on every row.
- **Genblaze, meaningfully:** orchestration across providers and steps, the cross-provider
  failover the native primitive cannot do.

## Do and don't

- Do run real jobs on camera; the video must show the app actually working.
- Do let the failover moment land; it is the most memorable beat.
- Do keep the failover run small (two languages) so the "switched" badges are easy to see.
- Don't claim lip-sync or native fluency; the pitch is one voice identity across languages.
- Don't rush the reach counter or the queue drain.
