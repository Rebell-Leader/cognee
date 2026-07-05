# STALE-Guard

**Memory that knows when to stop believing itself.**

A write-time implicit-conflict adjudication layer for [Cognee](https://github.com/topoteretes/cognee), built for the WeMakeDevs × Cognee "Hangover Part AI" hackathon.

## The problem

Cognee, like every other agent-memory framework, retrieves facts extremely well. None of them check whether a stored fact has quietly stopped being true. If a user says "I just moved to Berlin" three months after their agent stored "user lives in Prague," standard memory keeps **both** facts around. Ask "recommend me a bike shop near where I live" afterward, and the agent can confidently answer using Prague simply because that memory matches the query more strongly, whether or not it's still true.

That's **implicit conflict**: a new observation invalidates a prior belief without ever explicitly negating it. It comes in two flavors.

- **Type I (co-referential):** same attribute, new value. "Lives in Prague" becomes "just moved to Berlin."
- **Type II (propagated):** the new fact invalidates a *downstream* fact that's never mentioned again. "Broke my leg yesterday" quietly invalidates "commutes by bicycle every day," and nobody says the word "bicycle" ever again.

The [STALE benchmark](https://arxiv.org/abs/2605.06527) (May 2026) puts a number on this: the best frontier LLM only hits 55.2% accuracy at catching implicit conflicts, and the memory frameworks it evaluated (Mem0, Zep, LightMem, A-mem, LiCoMemory) all score under 18%.

## What we built

Three additions on top of Cognee's existing extension points. No forked core, no new database.

1. **`stale_state` node accessors** (`get_node_stale_state` / `set_node_stale_state`), added to `GraphDBInterface` and implemented on the default Ladybug/Kuzu adapter. These mirror the `feedback_weight` / `truth_state` accessor pattern already sitting in Cognee's codebase, so it's a self-contained, upstream-mergeable addition rather than a new parallel system (`cognee/infrastructure/databases/graph/graph_db_interface.py`, `.../ladybug/adapter.py`).

2. **`stale_guard`**, a standalone package (`stale_guard/`) with two hooks:
   - **State Adjudicator** (write-time, `stale_guard/adjudicator.py`), run as a real `cognee.memify()` enrichment pipeline rather than a bespoke side-call. It looks for candidate conflicts two ways: *vector similarity* against the new fact's raw text (handles Type I and any lexically-close Type II), and *graph traversal* through `GraphDBInterface.get_neighborhood(depth=2)`, walking out from the new fact's own chunk node through shared entities like "the user" to reach Type II conflicts that share no vocabulary with the trigger sentence at all (proof below).

     An LLM judge classifies each candidate as `KEEP` / `STALE` / `REPLACE` / `UNKNOWN`. Marking something invalid is destructive, since it hides a memory from every future answer, so before anything gets persisted, a second adversarial LLM call (`refute_verdict`) tries to find a reason the old memory could still be true. Verdicts get written through the accessors from (1). Nothing is deleted, which matches how Cognee's graph is append-only by design.
   - **Constrained Recall** (read-time, `stale_guard/guard.py`): fetches the relevant chunks for a query, splits them into current vs. stale using the persisted state, and answers strictly from current facts. When the question itself assumes something now stale, it surfaces a `premise_warning` instead of silently going along with it — the "Prague bike shop" failure mode from above.

3. Stale nodes render red in Cognee's own graph visualizer. A 3-line patch to `cognee/modules/visualization/preprocessor.py`, reusing the existing `ontology_valid` color-override, so `cognee.visualize_graph()` shows staleness without any bespoke UI.

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

`stale_guard/demo.py` runs 13 hand-crafted conflict scenarios (6 Type I, 7 Type II, including one coding-agent scenario, see `stale_guard/scenarios.py`) through plain Cognee (`add`/`cognify`/`search`) and through STALE-Guard (`remember`/`recall`). Each answer is scored by an LLM grader (`stale_guard/grader.py`) that reads the full context instead of matching keywords. Keyword matching gave us false readings during development: a correct answer saying "since you divorced Sarah, only list her if you intentionally want her" still contains the string "Sarah." Results: `stale_guard/demo_results.json`.

**Baseline (plain Cognee): 53.8% correct (7/13). STALE-Guard: 100% correct (13/13).** Across 13 scenarios spanning location, job, relationship, diet, platform, health, life-event, and coding-convention changes. `refuted_verdicts_held_back: 5` in the results file shows the adversarial guardrail was actually active on this run, not just theoretical.

Take the 100% with a grain of salt. It's an n=13, single-run, LLM-graded demo, not evidence of a solved problem, just evidence the mechanism holds up across a varied scenario set rather than being tuned to one example. What matters more than the topline number is that it isn't a clean win by construction. The propagation-proof section below has a case where the adversarial refuter did hold back a real catch, and a legitimate precision/recall trade-off shows up in the results, not hidden. `layoff_daily_schedule` in an earlier run has a similarly defensible near-miss.

This is a demo-grade eval sized for a short build, not a reproduction of the STALE paper's full 1,200-query, expert-validated protocol. The goal is showing the mechanism works end-to-end and generalizes across both conflict types, not producing a peer-reviewable number.

### Propagation Crawler: proven, not just claimed

A small demo corpus (2-3 facts per scenario) makes vector top-k search trivially return everything in the graph, so the first full run reported zero conflicts caught only via graph traversal. That's an artifact of scenario size, not evidence the mechanism is unneeded. `stale_guard/propagation_proof.py` tests this properly: 15 filler facts, deliberately loaded with ski and injury vocabulary, compete for the vector top-k slots against a target fact ("commutes by bicycle every day") that shares zero vocabulary with the trigger ("broke my leg... skiing accident"). Result: the target fact was invisible to vector similarity, pushed out of the top-k by the noise, and was only found via `get_neighborhood` graph traversal through the shared "user" entity. Full detail in `stale_guard/propagation_proof_results.json`.

### Scalability: what holds up, what doesn't

`stale_guard/scalability_test.py` bulk-builds a bigger graph (60 unrelated facts, 282 nodes/402 edges) and measures the mechanism on top of it (`stale_guard/scalability_results.json`). Cost and effectiveness turned out to scale independently.

Cost holds up fine. LLM calls per `remember()` are bounded by fixed caps (`CANDIDATE_TOP_K` + `MAX_PROPAGATION_CANDIDATES`), not by graph size. Both `remember()` calls took roughly 21-23 seconds on the 282-node graph, same as on a 3-node one. The raw `get_neighborhood(depth=2)` traversal also stayed fast (0.012s) even once the "user" entity hub reached degree 99.

Effectiveness didn't hold up at first. That same 2-hop traversal returned 108-110 nodes before the cap, of which only 8 (the cap) actually got judged, in arbitrary database-return order, not ranked by relevance. Already at 60 filler facts, about 93% of the propagation candidate pool was being silently discarded, which means the constant LLM cost was bought by blind truncation rather than smart selection. We checked the actual edge types in a real 2-hop neighborhood before reaching for the obvious-looking fix of excluding "structural" edges, and found that `contains` is precisely the chunk-to-entity link the whole mechanism depends on. Filtering it out would have broken propagation instead of fixing it. So `_rank_propagation_candidates()` (`stale_guard/adjudicator.py`) instead ranks candidates by the degree of the lowest-degree entity connecting each one to the new fact. A rare shared entity like "Prague" is a much stronger relevance signal than a generic hub shared by every fact, like "the user," the same intuition behind IDF down-weighting common terms, with recency as a tie-break when everything only shares the generic hub. A deterministic test confirmed it: one candidate sharing a rare 2-degree connector correctly ranked #1 over 22 candidates sharing only a 24-degree generic hub. `TODO.md` has the full detail, including a related Cognee-side entity-resolution gap ("user" vs. "the user" resolving to two separate nodes) that would still cause coverage gaps for our crawler.

## Why this fits Cognee specifically

- Extends `GraphDBInterface`'s existing per-node state pattern (`feedback_weight`, `truth_state`) rather than inventing a parallel metadata system.
- Sits naturally alongside Cognee's own `truth_subspace` module (session-learning-based retrieval re-ranking) and `temporal_awareness`/`temporal_graph` tasks. Cognee's team is already investing in "when is a memory still valid," and this pushes one step further, from time-tagging to actual implicit-invalidation reasoning.
- Runs as a real `cognee.memify()` enrichment pipeline (`adjudicate_new_fact_task` in `adjudicator.py`), not a bolt-on side-channel.
- Reuses Cognee's own graph traversal primitive (`get_neighborhood`) for the Propagation Crawler, and its own visualization pipeline (`preprocess()`) for showing staleness. No new infrastructure invented where Cognee already had the right shape.

## Running it

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[anthropic]" -e "."
cp .env.template .env   # set LLM_API_KEY
python stale_guard/demo.py
python stale_guard/propagation_proof.py
python stale_guard/scalability_test.py
```

## Known limitations

- The adversarial refuter is deliberately conservative: it errs toward not suppressing a memory it isn't sure about. Some genuinely arguable Type II cases (does losing a job invalidate a 6am wake-up habit, or just its original reason?) get held back rather than marked stale as a result. That's a real precision/recall trade-off, not a bug — see the `layoff_daily_schedule` scenario and the propagation-proof run for two worked examples.
- `recall()` still bypasses Cognee's actual retrieval stack (GRAPH_COMPLETION, hybrid ranking) with its own vector-search-plus-LLM-call, instead of hooking stale-state filtering into Cognee's existing retriever chain, the same place `truth_subspace`'s `use_truth_weight` hooks into `rank_chunk_summary_pairs`. Doing that would make every search type stale-aware for free instead of just this one path. That's the natural next step.
- Reproducing the STALE benchmark's full protocol (400 expert-validated scenarios, 1,200 queries) would turn this from a demo-grade number into a citable one.

`TODO.md` has the full backlog: what's done and what's next.
