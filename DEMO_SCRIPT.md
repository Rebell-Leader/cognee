# STALE-Guard demo recording script

**Tool:** `stale_guard/app.py` — run `cd cognee && python stale_guard/app.py`, open the printed localhost URL, maximize the browser. Three tabs: 1. The Problem, 2. Live Demo, 3. Graph & Proof.

**Hard requirement: ≤ 3:00 total**, covering About the project, Tech stack & architecture, Demo, and (optional) Learning & growth. Budget below targets **2:50** to leave a margin — LLM call latency varies run to run, and a rigid script that assumes exact timing will blow the limit on a slow call.

**The one cut that buys you the most margin:** don't run the live baseline button. Tab 1's intro already gives the concrete Prague/Berlin example in words, so the failure mode is established before you ever open Tab 2 — you don't need to re-demonstrate it live. Running it live costs ~30-40s of screen time (2 sequential `add`+`cognify` calls plus a search) for something the viewer has already understood from the narration. Skip it and go straight to STALE-Guard's remember → remember → recall. If you want it anyway, see the "if you have extra margin" note at the end.

**Wait-time discipline:** every live click below triggers a real LLM call, roughly 15-30 seconds. The narration for each is written long enough to cover a slow response — if the result renders while you're still mid-sentence, just finish the clause naturally and move on to reading it. Don't stop and wait in silence; keep talking.

---

## 0:00–0:30 — About the project (Tab 1, top of page)

**Action:** Tab 1 is already open. Scroll slowly through the intro as you talk — don't rush ahead of your own narration.

**Voiceover (~75 words, aim for 28-32s):**
> "Every memory framework, Cognee included, retrieves facts really well. None of them check whether a stored fact has quietly stopped being true. Tell an agent the user lives in Prague and bikes to work daily, then tell it they just moved to Berlin — standard memory keeps both facts, happy to recommend a Prague bike shop months later, simply because that memory still matches the query best. The STALE benchmark measured this: the best frontier LLM only catches 55% of these conflicts, and every memory framework tested scores under 18%."

---

## 0:30–1:00 — Tech stack and architecture (Tab 1, "What we built" section)

**Action:** [SCROLL to the "What we built" bullets — don't switch tabs yet]

**Voiceover (~85 words, aim for 28-32s):**
> "STALE-Guard fixes this by extending Cognee directly, not wrapping it. A State Adjudicator runs at write time, checking new facts against the graph two ways: vector similarity, and real graph traversal through shared entities — which is what catches conflicts that share zero vocabulary with the trigger sentence at all. Before anything is marked invalid, a second, adversarial LLM call tries to argue the first judge is wrong, since a hallucinated verdict would silently hide a true memory forever. It all writes through a new accessor pair I added to Cognee's own graph interface."

---

## 1:00–2:20 — Demo (Tab 2, then the graph link on Tab 3) — 80 seconds

**Action:** [SWITCH TO TAB 2 NOW]

**Voiceover (start immediately on switching, ~15 words):**
> "Let's see it live — nothing you're about to watch is pre-baked."

**Action:** [CLICK "1. Remember: lives in Prague, bikes daily" NOW]

**Voiceover while it loads (~30 words, covers ~12-15s):**
> "First fact goes in. Nothing to compare against yet, since this is the only thing in memory so far — that's expected, and the result will say so."

*(let the "Remembered..." text render, don't read it aloud, it just confirms the above)*

**Action:** [CLICK "2. Remember: just moved to Berlin" NOW]

**Voiceover while it loads (~45 words, covers ~18-22s):**
> "Now the Berlin fact. This is where the real check happens — the judge is comparing it against everything already stored, using graph traversal, not keyword matching, so it catches conflicts even when the wording doesn't overlap at all."

**Action:** [let the verdict render, then read the key part aloud]

**Voiceover reading the result (~25 words):**
> "STALE. Moving to Berlin directly contradicts living in Prague. Nothing gets deleted — Cognee's graph is append-only — it's just marked, with a reason and what replaced it."

**Action:** [CLICK "Ask: recommend a bike shop near where I live" NOW]

**Voiceover while it loads (~30 words, covers ~12-15s):**
> "Same exact question as the broken baseline case. Watch what it grounds in this time."

*(let the answer and premise warning render)*

**Voiceover reading the result (~30 words):**
> "It correctly starts from Berlin, and it surfaces what I call a premise warning — telling me explicitly that my question's own assumption was outdated, and why."

**Action:** [SWITCH TO TAB 3 NOW, click "Open the graph visualization →" — opens in a new tab, switch to it on screen]

**Voiceover (~35 words, covers the click + tab switch + a few seconds looking at the graph):**
> "And you can watch this happen inside Cognee's own graph visualizer — three lines of code color invalidated nodes red. That's the Prague fact, flagged, right in the graph."

*(This section runs ~1:00–2:20, roughly 80s — the exact split between LLM wait time and talking time will vary by run; the total word budget above is calibrated to that window, not each individual gap.)*

---

## 2:20–2:45 — Learning and growth (optional; Tab 3, "We didn't stop at the demo")

**Action:** [SWITCH BACK to the STALE-Guard tab, scroll to "We didn't stop at the demo"]

**Voiceover (~90 words, aim for 22-25s — talk fast or trim if you're already near 2:45):**
> "One thing I learned building this: a small demo makes vector search look sufficient by accident, because there's nothing else competing for the top results. I proved that wasn't real by burying a conflict under fifteen irrelevant facts that read more similar to the trigger than the real one — vector search missed it completely, graph traversal found it anyway. I also stress-tested cost: grew the graph to nearly 300 nodes with a heavily-connected hub entity, and the cost of checking each new fact stayed flat."

**If you're already past 2:45, cut this section entirely** — it's explicitly optional, and the demo payoff in the section above is the part that has to land.

---

## 2:45–2:55 — Close

**Voiceover (~20 words):**
> "That's STALE-Guard — memory that knows when to stop believing itself. Full repo and writeup are linked below."

---

## If you have extra margin: adding the live baseline run

Only do this if a practice run comes in under 2:30 without it. Insert right after 1:00 (before clicking "1. Remember..."):

**Action:** [Stay on Tab 2, click "Run baseline (plain Cognee)" first]

**Voiceover while it loads (~40 words, covers ~30-40s since this call is slower — 2 sequential add+cognify calls plus a search):**
> "First, plain Cognee, so you can see the actual failure, not just hear about it. I'm giving it the exact same two facts. This call takes a bit longer — it's genuinely running two full ingestion passes plus a search underneath."

**Voiceover reading the result (~20 words):**
> "Notice it's still leaning on Prague, even though I told it otherwise in the same conversation."

This adds ~50-60s total — budget for it by trimming the "Learning and growth" section or speaking faster in "Tech stack and architecture."

---

## Recording checklist

- [ ] `.env` has a working `LLM_API_KEY` (nano model — fast, but terser prose than gpt-5-mini; that's fine, the mechanism is what's on trial).
- [ ] Run `python stale_guard/app.py` from inside `cognee/`, open the printed URL, maximize the browser window.
- [ ] Do at least one full practice run before recording — time yourself, and know whether you're naturally landing near 2:50 or need to cut the "Learning and growth" section.
- [ ] The graph link opens in a new tab — switch to it on screen when you click, don't just narrate over a blank tab.
- [ ] If a call runs unusually slow (LLM provider hiccup), keep talking — restate the point in different words rather than going silent.
