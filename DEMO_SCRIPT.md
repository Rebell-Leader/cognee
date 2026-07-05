# STALE-Guard demo recording script

**Tool:** `stale_guard/app.py` — a small Gradio app, three tabs. Run it from inside the `cognee/` repo (`cd cognee && python stale_guard/app.py`) and open the printed localhost URL in a browser for recording. Click through in order while narrating; every button in Tab 2 makes a real LLM call, no fixed timer, so talk as long as you need before clicking the next one.

(A terminal-only version, `stale_guard/record_demo.py`, still exists if you'd rather record a terminal than a browser — same beats, same voiceover works for either.)

**Estimated runtime:** ~2.5-3 min at a natural talking pace, ~90s if you cut to the tight version (marked below).

---

## Tab 1 — "The Problem"

**On screen:** the intro tab, scroll down through it as you talk.

**Voiceover:**
> "Every memory framework, Cognee included, retrieves facts really well. Here's the problem: none of them check whether a stored fact has quietly stopped being true. Say the user lives in Prague and bikes to work every day, then tell it a moment later they just moved to Berlin. Standard memory keeps both facts around. Ask an ordinary question afterward, and it can confidently answer using Prague simply because that memory matches better, whether or not it's still true.
>
> This is a known problem — the STALE benchmark puts a number on it: the best frontier LLM only hits 55.2% accuracy at catching these implicit conflicts, and every memory framework it tested scores under 18%."

---

## Tab 2 — "Live Demo": baseline confusion

**On screen:** click "Run baseline (plain Cognee)."

**Voiceover:**
> "Let's see it happen. Same two facts, same question: recommend a bike shop near where I live."
>
> *(let the baseline answer render)*
>
> "Look closely — it's still treating Prague as home, even though I told it otherwise in the exact same conversation."

---

## Tab 2 — write-time adjudication

**On screen:** click "1. Remember: lives in Prague, bikes daily," then "2. Remember: just moved to Berlin."

**Voiceover:**
> "Now the same two facts through STALE-Guard. Every time something's remembered, a write-time judge checks it against what's already stored, using real graph traversal, not just keyword matching."
>
> *(click fact 1 — nothing to compare against yet, say so quickly)*
>
> "First fact, nothing to check yet. Now the Berlin fact."
>
> *(click fact 2, let the verdict render)*
>
> "STALE. Moving to Berlin directly contradicts living in Prague. Nothing gets deleted, Cognee's graph is append-only by design — it just gets marked, with a reason and what replaced it. Auditable, not a black-box flag."

---

## Tab 2 — constrained recall

**On screen:** click "Ask: recommend a bike shop near where I live."

**Voiceover:**
> "Exact same question as before. This time it correctly starts from Berlin, and it surfaces what I call a premise warning: it's telling me, explicitly, that my question's own assumption was outdated, and why."

*(Tight-cut option: if trimming for time, this is the one beat to never cut — it's the actual payoff.)*

---

## Tab 3 — "Graph & Proof": the visual

**On screen:** click "Open the graph visualization →" (opens in a new tab).

**Voiceover:**
> "You can watch this happen inside Cognee's own graph visualizer. I added three lines of code to color invalidated nodes red, reusing the exact pattern Cognee already uses for ontology-matched nodes. That's the Prague fact, flagged red, right in the graph."

---

## Tab 3 — we went further

**On screen:** scroll to the "We didn't stop at the demo" section.

**Voiceover:**
> "I didn't stop at the easy case. The harder problem is a fact invalidated without ever being mentioned again — 'I broke my leg' silently invalidating a daily bike commute that's never brought up again. Catching that needs actual graph traversal through shared entities, not text similarity. I proved it: buried the real conflict under fifteen irrelevant facts that read more similar to the trigger sentence than the real one does. Vector search missed it completely. Graph traversal found it anyway.
>
> And I stress-tested cost, not just correctness: grew the graph to nearly 300 nodes with a heavily-connected hub entity, and the cost of checking each new fact stayed flat, same as on a 3-node graph."

---

## Close

**Voiceover:**
> "That's STALE-Guard — memory that knows when to stop believing itself. Full repo, writeup, and every result file mentioned here are linked below."

---

## Recording checklist

- [ ] `.env` has a working `LLM_API_KEY` (nano model — fast, but responses will be terser than gpt-5-mini; that's fine, the mechanism is what's on trial, not prose quality).
- [ ] Run `python stale_guard/app.py` from inside `cognee/`, open the printed URL, maximize the browser window.
- [ ] Do one practice click-through before recording so you know roughly how long each LLM call takes (~15-30s) — narrate through the wait, don't stare at a spinner in silence.
- [ ] The graph link opens in a new tab — that's fine, just switch to it on screen when you click.
