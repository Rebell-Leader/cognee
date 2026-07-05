# STALE-Guard

**Memory that knows when to stop believing itself.**

A write-time implicit-conflict adjudication layer for [Cognee](https://github.com/topoteretes/cognee), built for the WeMakeDevs × Cognee "Hangover Part AI" hackathon.

## The problem

Cognee (and every other agent-memory framework) retrieves facts extremely well. None of them know when a stored fact has quietly stopped being true. If a user says "I just moved to Berlin" three months after their agent stored "user lives in Prague," standard memory stores **both** facts. Ask "recommend me a bike shop near where I live" and the agent may confidently answer using Prague — because the query happens to match that memory more strongly, not because it's still true.

This is **implicit conflict**: a new observation invalidates a prior belief without ever explicitly negating it.

- **Type I (co-referential):** same attribute, new value — "lives in Prague" → "just moved to Berlin."
- **Type II (propagated):** the new fact invalidates a *downstream* fact that's never mentioned again — "broke my leg yesterday" silently invalidates "commutes by bicycle every day."

The [STALE benchmark](https://arxiv.org/abs/2605.06527) (May 2026) puts a number on this: even the best frontier LLM hits only 55.2% accuracy at catching implicit conflicts, and the memory frameworks it evaluated (Mem0, Zep, LightMem, A-mem, LiCoMemory) all score under 18%.

## What we built

Three additions on top of Cognee's existing extension points — no forked core, no new database:

1. **`stale_state` node accessors** (`get_node_stale_state` / `set_node_stale_state`), added to `GraphDBInterface` and implemented on the default Ladybug/Kuzu adapter, mirroring the existing `feedback_weight` / `truth_state` accessor pattern already in Cognee's codebase. Self-contained, upstream-mergeable (`cognee/infrastructure/databases/graph/graph_db_interface.py`, `.../ladybug/adapter.py`).

2. **`stale_guard`**, a standalone package (`stale_guard/`) with two write/read hooks:
   - **State Adjudicator** (write-time, `stale_guard/adjudicator.py`), run as a real `cognee.memify()` enrichment pipeline (not a bespoke side-call). It finds candidate conflicts two ways:
     - *vector similarity* against the new fact's raw text (catches Type I and lexically-close Type II), and
     - *graph traversal* — `GraphDBInterface.get_neighborhood(depth=2)` from the new fact's own chunk node, out through shared entities (e.g. "the user") — which catches Type II conflicts that share no vocabulary with the trigger sentence at all. See the dedicated proof below.

     An LLM judge classifies each candidate as `KEEP` / `STALE` / `REPLACE` / `UNKNOWN`. Before anything destructive is persisted, a second, adversarial LLM call (`refute_verdict`) actively tries to find a reason the old memory could still be valid — a hallucinated STALE verdict silently hides a true memory forever, so it gets one skeptical review first. Verdicts are written via the accessors from (1) — nothing is deleted, matching Cognee's append-only graph philosophy.
   - **Constrained Recall** (read-time, `stale_guard/guard.py`): before answering a query, fetches the relevant chunks, splits them into current vs. stale using the persisted state, and answers strictly from current facts — surfacing a `premise_warning` whenever the question itself presupposed something now stale (the "Prague bike shop" failure mode).

3. **Stale nodes render in red in Cognee's own graph visualizer** — a 3-line patch to `cognee/modules/visualization/preprocessor.py` (mirrors the existing `ontology_valid` color-override), so `cognee.visualize_graph()` shows staleness with no bespoke UI needed.

```
remember("The user lives in Prague and commutes by bicycle every day.")
remember("The user just moved to Berlin last week.")
    -> State Adjudicator marks the Prague/bicycle fact REPLACE,
       superseded_by="The user lives in Berlin."

recall("Recommend me a good bike shop near where I live.")
    -> answer references Berlin, not Prague
    -> premise_warning: '"...lives in Prague..." is OUTDATED ... superseded by: lives in Berlin.'
```

## Demo / eval

`stale_guard/demo.py` runs 13 hand-crafted conflict scenarios (6 Type I, 7 Type II, including one coding-agent scenario — see `stale_guard/scenarios.py`) through plain Cognee (`add`/`cognify`/`search`) and through STALE-Guard (`remember`/`recall`). Each answer is scored by an LLM grader (`stale_guard/grader.py`) reading the full context — not by keyword matching, which we found gives false readings (a correct answer that says "since you divorced Sarah, only list her if you intentionally want her" still contains the string "Sarah"). Results: `stale_guard/demo_results.json`.

**Baseline (plain Cognee): 53.8% correct (7/13) — STALE-Guard: 100% correct (13/13)**, across 13 scenarios spanning location, job, relationship, diet, platform, health, life-event, and coding-convention changes. `refuted_verdicts_held_back: 5` in the results file shows the adversarial guardrail is actually active, not just theoretical, on this run.

Take the 100% with the grain of salt a n=13, single-run, LLM-graded demo deserves — it isn't evidence of a solved problem, just evidence the mechanism holds up across a deliberately varied scenario set rather than being tuned to one example. The more informative signal than the topline number is that it isn't a clean win by construction: see the propagation-proof section below for a case where the adversarial refuter *did* hold back a real catch (a legitimate precision/recall trade-off, not hand-waved away), and `layoff_daily_schedule` in an earlier run for a similarly-defensible near-miss.

This is a demo-grade eval sized for a short build — not a reproduction of the STALE paper's full 1,200-query, expert-validated protocol. It's meant to show the mechanism works end-to-end and generalizes across both conflict types, not to produce a peer-reviewable number.

### Propagation Crawler: proven, not just claimed

A small demo corpus (2-3 facts per scenario) makes vector top-k search trivially return everything in the graph, so the first full run reported zero conflicts caught *only* via graph traversal — an honest artifact of scenario size, not evidence the mechanism is unneeded. `stale_guard/propagation_proof.py` tests this properly: 15 filler facts deliberately crowded with ski/injury vocabulary compete for the vector top-k against a target fact ("commutes by bicycle every day") that shares zero vocabulary with the trigger ("broke my leg... skiing accident"). Result — **proven**: the target fact was invisible to vector similarity (pushed out of the top-k by noise), and was only found via `get_neighborhood` graph traversal through the shared "user" entity. Full detail: `stale_guard/propagation_proof_results.json`.

### Scalability: what holds up, what doesn't

`stale_guard/scalability_test.py` bulk-builds a bigger graph (60 unrelated facts, 282 nodes/402 edges) and measures the mechanism on top of it (`stale_guard/scalability_results.json`). Two different things scale independently:

- **Cost holds up.** LLM calls per `remember()` are bounded by fixed caps (`CANDIDATE_TOP_K` + `MAX_PROPAGATION_CANDIDATES`), not by graph size — both `remember()` calls took ~21-23s on the 282-node graph, same as on a 3-node one. The raw `get_neighborhood(depth=2)` traversal also stayed fast (0.012s) even once the "user" entity hub reached degree 99.
- **Effectiveness initially didn't — now fixed.** That same 2-hop traversal returned 108-110 nodes before the cap — of which only 8 (the cap) actually got judged, in arbitrary DB-return order, not ranked by relevance. Already ~93% of the propagation candidate pool was being silently discarded at just 60 filler facts, meaning the constant LLM cost was bought by blind truncation, not smart selection. Before reaching for the obvious-looking fix (excluding "structural" edges), we checked the actual edge types in a real 2-hop neighborhood — `contains` turned out to be precisely the chunk↔entity link the whole mechanism depends on, not noise, so filtering it out would have broken propagation, not fixed it. Instead, `_rank_propagation_candidates()` (`stale_guard/adjudicator.py`) ranks candidates by the degree of the *lowest-degree entity connecting each one to the new fact* — a rare shared entity (e.g. "Prague") is a much stronger relevance signal than a generic hub shared by every fact (e.g. "the user"), same intuition as IDF down-weighting common terms — with recency as a tie-break when everything only shares the generic hub. Validated with a deterministic test: one candidate sharing a rare 2-degree connector correctly ranked #1 over 22 candidates sharing only a 24-degree generic hub. See `TODO.md` for full detail, including a related Cognee-side entity-resolution gap ("user" vs "the user" resolving to two separate nodes) that would still cause silent coverage gaps for our crawler.

## Why this fits Cognee specifically

- Extends `GraphDBInterface`'s existing per-node state pattern (`feedback_weight`, `truth_state`) rather than inventing a parallel metadata system.
- Sits naturally alongside Cognee's own `truth_subspace` module (session-learning-based retrieval re-ranking) and `temporal_awareness`/`temporal_graph` tasks — Cognee's team is already investing in "when is a memory still valid," and this pushes one step further: from time-tagging to actual implicit-invalidation reasoning.
- Runs as a real `cognee.memify()` enrichment pipeline (`adjudicate_new_fact_task` in `adjudicator.py`), not a bolt-on side-channel.
- Reuses Cognee's own graph traversal primitive (`get_neighborhood`) for the Propagation Crawler and its own visualization pipeline (`preprocess()`) for showing staleness — no new infrastructure invented where Cognee already had the right shape.

## Running it

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[anthropic]" -e "."
cp .env.template .env   # set LLM_API_KEY
python stale_guard/demo.py
python stale_guard/propagation_proof.py
python stale_guard/scalability_test.py
```

## Honest scope notes

- The adversarial refuter is deliberately conservative: it errs toward *not* suppressing a memory it isn't sure about. This means some genuinely arguable Type II cases (e.g. "does losing a job invalidate a 6am wake-up habit, or just its original reason?") get held back rather than marked stale — a real precision/recall trade-off, not a bug. See the `layoff_daily_schedule` scenario and the propagation-proof run for two worked examples.
- `recall()` still bypasses Cognee's actual retrieval stack (GRAPH_COMPLETION, hybrid ranking) with its own vector-search + LLM call, rather than hooking stale-state filtering into Cognee's existing retriever chain (the same place `truth_subspace`'s `use_truth_weight` hooks into `rank_chunk_summary_pairs`). That would make every search type stale-aware for free instead of just this one path — the natural next step.
- Reproducing the STALE benchmark's full protocol (400 expert-validated scenarios, 1,200 queries) is the natural next step to get a rigorous, citable number instead of a demo-grade one.

See `TODO.md` for the full backlog and what's already done vs. next.
