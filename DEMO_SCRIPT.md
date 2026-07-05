# STALE-Guard demo recording script

**Tool:** `stale_guard/record_demo.py` — run it from inside the `cognee/` repo (`cd cognee && python stale_guard/record_demo.py`). It suppresses Cognee's verbose pipeline logging, prints each beat cleanly, and pauses on `[press Enter to continue]` between beats so you can talk as long as you need before advancing — no fixed timer to race.

Beats 1-3 are **live** — real LLM calls, real graph writes, nothing pre-baked. That matters for credibility: the whole pitch is "the mechanism works," so it should visibly work in real time. Beats 4-5 pull from already-captured results (`graph_visualization.html`, `propagation_proof_results.json`, `scalability_results.json`) because re-running the propagation/scale proofs live would cost several more minutes of dead air for no extra credibility — the numbers are already real, just not generated on-camera.

**Ignore/trim in post:** three lines right at the very start (`principal_configuration table already exists...` etc.) — harmless session-cache init noise, not part of the demo.

**Estimated runtime:** ~2.5-3 min at a natural talking pace, ~90s if you cut to the tight version (marked below).

---

## Beat 1/5 — Baseline: plain Cognee gets confused

**On screen:** terminal running `record_demo.py`, output through the first pause.

**Voiceover:**
> "Every memory framework — Cognee included — retrieves facts really well. Here's the problem: I tell it two things. First, the user lives in Prague and bikes to work every day. Then, a moment later: the user just moved to Berlin. Now I ask a completely ordinary question — recommend a bike shop near where I live."
>
> *(let the baseline answer print)*
>
> "Look closely — it asks for 'your location in Prague.' It's still treating Prague as home, even though I told it otherwise in the exact same conversation. Nothing here is technically wrong per se — it's just never checked whether the fact it retrieved is still true."

---

## Beat 2/5 — STALE-Guard: write-time adjudication catches the conflict

**On screen:** the two `remember()` calls and their printed verdicts.

**Voiceover:**
> "Now the same two facts, through STALE-Guard. Every time something's remembered, a write-time judge checks it against what's already stored — using real graph traversal, not just keyword matching, which matters for cases we'll get to in a second."
>
> *(first remember — nothing to compare against yet, say so quickly)*
>
> "First fact, nothing to check yet. Now the Berlin fact —"
>
> *(let the verdict print)*
>
> "— STALE. Moving to Berlin directly contradicts living in Prague. Nothing gets deleted — Cognee's graph is append-only by design — it just gets marked, with a reason and what replaced it, auditable, not just a black-box flag."

---

## Beat 3/5 — Constrained recall: same query, correct answer

**On screen:** the `recall()` call, answer, and premise warning.

**Voiceover:**
> "Exact same question as before: recommend a bike shop near where I live. This time it correctly starts from Berlin — and it surfaces what I call a premise warning: it's telling me, explicitly, that my question's own assumption was outdated, and why."

*(Tight-cut option: if trimming for time, this is the one beat to never cut — it's the actual payoff.)*

---

## Beat 4/5 — Visual: the stale node in Cognee's own graph visualizer

**On screen:** switch to the browser tab with `graph_visualization.html` already open (open it before recording starts, don't wait for it to load on camera).

**Voiceover:**
> "You can watch this happen inside Cognee's own graph visualizer — I added three lines of code to color invalidated nodes red, reusing the exact pattern Cognee already uses for ontology-matched nodes. That's the Prague fact, flagged red, right in the graph."

---

## Beat 5/5 — We went further: propagation crawler + scalability, proven

**On screen:** the printed propagation-proof and scalability summary lines.

**Voiceover:**
> "I didn't stop at the easy case. The harder problem is a fact that's invalidated without ever being mentioned again — 'I broke my leg' silently invalidating a daily bike commute that's never brought up again. Catching that needs actual graph traversal through shared entities, not text similarity. I proved it: I deliberately buried the real conflict under fifteen irrelevant facts that read *more* similar to the trigger sentence. Vector search missed it completely. Graph traversal found it anyway.
>
> And I stress-tested cost, not just correctness: grew the graph to nearly 300 nodes with a heavily-connected hub entity, and the cost of checking each new fact stayed flat — same as on a 3-node graph. It doesn't get slower as memory grows."

---

## Close

**Voiceover:**
> "That's STALE-Guard — memory that knows when to stop believing itself. Full repo, writeup, and every result file mentioned here are linked below."

---

## Recording checklist

- [ ] `.env` has a working `LLM_API_KEY` (nano model — fast, but responses will be terser than gpt-5-mini; that's fine, the mechanism is what's on trial, not prose quality).
- [ ] Open `graph_visualization.html` in a browser tab *before* hitting record (don't wait for page load on camera).
- [ ] Terminal font large enough to read on a recording (14-16pt+).
- [ ] Run `python stale_guard/record_demo.py` from inside `cognee/`.
- [ ] Read each voiceover block *while the corresponding beat is on screen*, then press Enter to advance — don't rush to match a timer.
