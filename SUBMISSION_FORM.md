# Submission form text

## Project description

STALE-Guard is a write-time memory-integrity layer for Cognee that catches implicit conflicts: facts that quietly stop being true without ever being contradicted. Tell an agent "I live in Prague and bike to work daily," then later "I just moved to Berlin," and standard memory keeps both facts around, happy to recommend a Prague bike shop months later because that memory still matches the query best. The [STALE benchmark](https://arxiv.org/abs/2605.06527) measured this directly: the best frontier LLM catches only 55.2% of these implicit conflicts, and every memory framework it evaluated (Mem0, Zep, LightMem, A-mem, LiCoMemory) scores under 18%.

STALE-Guard adds a State Adjudicator that runs whenever a new fact is remembered, checking it against the existing graph two ways: vector similarity, and actual graph traversal through shared entities, which catches conflicts that share no vocabulary with the trigger sentence at all (a "broke my leg" fact silently invalidating a "commutes by bicycle" fact that's never mentioned again). Before anything is marked invalid, an adversarial second LLM call tries to argue the judge is wrong, since a hallucinated verdict would silently hide a true memory forever. At read time, a Constrained Recall step answers only from current facts and raises a premise warning when a question itself assumes something now stale.

Across 13 hand-crafted conflict scenarios, plain Cognee answered 53.8% correctly; STALE-Guard answered 100%. We also stress-tested the mechanism itself, not just the demo: proved the graph-traversal catch with a dedicated adversarial test (deliberately crowding a real conflict out of vector search entirely), and found and fixed a real scalability gap where propagation candidates were being silently discarded by arbitrary truncation instead of ranked selection.

## Describe how you have used Cognee in your project

We extended Cognee rather than wrapping it. Three additions, all self-contained and upstream-mergeable:

1. A new `stale_state` accessor pair (`get_node_stale_state`/`set_node_stale_state`) on `GraphDBInterface`, implemented on the default Ladybug/Kuzu adapter, mirroring the `feedback_weight`/`truth_state` pattern already in Cognee's codebase.
2. The State Adjudicator runs as a real `cognee.memify()` enrichment pipeline, not a side-call, and its Propagation Crawler reuses Cognee's own `get_neighborhood()` k-hop graph traversal primitive to walk out from a new fact's chunk node through shared entities.
3. A 3-line patch to Cognee's own graph visualizer (`preprocessor.py`) colors invalidated nodes red, reusing the exact color-override pattern Cognee already uses for ontology-matched nodes, so staleness is visible in Cognee's own frontend with no bespoke UI needed.

Beyond that, we built directly on Cognee's core primitives throughout: `add()`/`cognify()` for ingestion, `search()` for the baseline comparison, and direct `get_graph_engine()`/`get_vector_engine()` access for the candidate-finding logic. Nothing required forking Cognee's core or standing up a parallel database.

Repo: https://github.com/Rebell-Leader/cognee (see `STALE_GUARD.md` for the full writeup, `TODO.md` for the build log and findings)
