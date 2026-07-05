# STALE-Guard backlog

Ranked by leverage against the original concept, real AI-engineer pain, and the
hackathon's judging criteria (impact, creativity, technical excellence, best
use of Cognee, UX, presentation). Top of list = doing now.

## Done

- [x] **#1 — LLM-graded eval (replace substring heuristic).** Old `demo.py`
  scored answers by keyword match (`stale_signal`/`current_signal`), which
  was provably wrong: scenario 3 (`relationship_status`) scored "stale" even
  though the guarded answer *correctly* said "since you divorced Sarah,
  only list her if you intentionally want her" — the string "sarah" alone
  triggered a false negative. Replaced with an LLM auto-grader
  (`stale_guard/grader.py`) scored against the STALE paper's own dimensions
  (`reflects_current_state`, `corrected_stale_premise`), wired into
  `demo.py`.

- [x] **#2 — Real Propagation Crawler (graph traversal, not just vector
  similarity).** `stale_guard/adjudicator.py` now pulls candidates from two
  sources: vector-similarity search (`find_self_and_semantic_candidates`,
  catches Type I / lexically-close Type II) and graph traversal via
  Cognee's existing `GraphDBInterface.get_neighborhood(node_ids, depth=2)`
  (`find_propagation_candidates`, catches Type II chains that are
  semantically distant from the trigger sentence but connected through
  shared entities). Each judgement is tagged `source: "semantic"` or
  `"propagation"` so the demo can report how many conflicts were only
  catchable via graph traversal. Verified end-to-end on the broken-leg
  scenario; full 12-scenario run in progress to see where propagation
  earns its keep beyond vector similarity's reach.

- [x] **#3 — Confidence / guardrails against false-positive STALE marking.**
  Added `RefutationCheck` (`stale_guard/models.py`) and `refute_verdict()`
  (`stale_guard/adjudicator.py`): every STALE/REPLACE verdict now gets one
  adversarial second opinion — a skeptical reviewer prompt whose job is to
  actively look for a reason the old memory could still be valid — before
  it's persisted. If the refuter finds real doubt, the verdict is held back
  (not written to the graph) but kept in the returned judgement for audit
  (`refuted: true`, `refutation_reason`). Fails safe: a refuter error doesn't
  block the original verdict, since refutation is a check, not the source of
  truth. `demo.py` now reports `refuted_verdicts_held_back` in the summary.

  Switched `LLM_MODEL` to `openai/gpt-5.4-nano` for faster/cheaper eval runs.

**Full 12-scenario run with #1+#2+#3 and nano: baseline 50.0% correct (6/12)
→ STALE-Guard 91.7% correct (11/12).** The one guarded miss
(`layoff_daily_schedule`) is a defensible edge case, not a bug: the judge
marked "wakes at 6am to catch the train" STALE after a layoff, the
adversarial refuter pushed back ("habits often persist despite losing the
commute"), and the resulting answer was transparent about the uncertainty
rather than confidently wrong — the strict grader just didn't credit that as
"correct." `propagation_only_catches` was 0 in this run — an honest artifact
of small scenario size (2-3 facts each), where vector top-k=6 trivially
returns everything; see the dedicated proof below. `refuted_verdicts_held_back:
4` confirms the refuter was active throughout, not just on the one miss.
Full results: `stale_guard/demo_results.json`.

- [x] **Propagation Crawler proof (dedicated test).** Built
  `stale_guard/propagation_proof.py`: 15 filler facts deliberately crowded
  with ski/leg/injury vocabulary, competing for vector top-k against a target
  fact ("commutes by bicycle every day") that shares zero vocabulary with the
  trigger ("broke my leg... skiing accident"). Result: **PROVEN** — the
  target fact was invisible to vector-similarity search (pushed out of the
  top-k by noise) and was only found via `get_neighborhood(depth=2)` graph
  traversal through the shared "user" entity. Separately, the adversarial
  refuter held this specific catch back on this run (a similarly-defensible
  "a habit might outlast a one-time event" objection) — so the *reach* of
  the propagation mechanism is proven, even though whether it ends up
  persisted also depends on the refuter's deliberately conservative bar.
  Full detail: `stale_guard/propagation_proof_results.json`.

- [x] **#4 — Deepen Cognee-native integration (partial: memify wiring
  done).** `guard.remember()` now runs the State Adjudicator through a real
  `cognee.memify()` call (`extraction_tasks=[Task(passthrough_extraction)]`,
  `enrichment_tasks=[Task(adjudicate_new_fact_task, judgements_sink=...)]`)
  instead of calling `adjudicate_new_fact()` directly — genuine use of
  Cognee's enrichment pipeline API, not a side-call. Since `memify()` itself
  only returns pipeline run status (not task output), judgements are
  collected via a mutable `judgements_sink` list bound as a default kwarg on
  the `Task`, the same binding pattern `memify_default_tasks.py` already
  uses for `get_triplet_datapoints(triplets_batch_size=100)`. Verified
  end-to-end: judgements, refutation, and premise warnings all still flow
  correctly through the new path.

  **Not done (stretch, see below):** hooking stale-state filtering into
  Cognee's actual retriever chain (GRAPH_COMPLETION/hybrid ranking) instead
  of `recall()`'s bespoke vector-search + LLM call — bigger, riskier surgery
  on core retrieval code, out of scope for the remaining time.

- [x] **#5 — Visual demo via Cognee's own graph visualizer.** One 3-line
  patch to `cognee/modules/visualization/preprocessor.py`: nodes with
  `stale: True` now render in red (`#E11D48`), mirroring the exact pattern
  already used there for `ontology_valid` nodes (`_ONTOLOGY_VALID_COLOR`).
  Since `preprocess()` is the single shared enrichment point for every view
  (Story/Graph/Schema/Memory), this makes stale nodes visible everywhere in
  Cognee's existing frontend for free — no bespoke UI built. Verified: the
  Prague→Berlin scenario's stale node renders with the new color in the
  generated HTML (`cognee.visualize_graph()`).

- [x] **#6 — One dev-tool / coding-agent scenario.** Added
  `stale_coding_convention` to `stale_guard/scenarios.py`: "uses Redux" →
  migrated to Zustand, invalidating a stored coding convention for a new
  component. Directly relatable to the AI-engineer judges; covers the one
  adjacent hackathon submission found in research (DevBrain, code-memory
  focused) on its own turf.

## Final numbers (13-scenario run, memify-wired, nano)

**Baseline 53.8% (7/13) correct — STALE-Guard 100% (13/13) correct.**
`refuted_verdicts_held_back: 5`, `propagation_only_catches: 0` (see the
dedicated propagation-proof entry above for why 0 here is expected, not a
failure). Full detail: `stale_guard/demo_results.json`.

## Submission mechanism (checked against the live hackathon page + the
`topoteretes/cognee-hackathons` repo)

- Submission is a **Google Form** (`Submit Project` link on the hackathon
  page), not a PR. Registration and submission are two separate forms.
- No Cognee plugin registry/marketplace exists — "ship as a community
  plugin" isn't an available track. The deliverable is a public repo link
  (+ demo) submitted through the form, same as any "new project built with
  Cognee" entry.
- `cognee-hackathons` (topoteretes' archive of past events) has no folder
  for this specific hackathon — it's not the submission channel here.
- The **$100/PR track is separate and additive**: real PRs against
  `topoteretes/cognee` for verified issues, capped at 5/person, judged
  independently of the main submission. Our `stale_state` accessor pair and
  the 3-line visualization patch are both self-contained and
  upstream-mergeable (see stretch item below) — worth opening as real PRs
  for extra prize eligibility, but they are not required for the main
  submission to count.

## Scalability & effectiveness at growing knowledge-base size (empirical)

Ran `stale_guard/scalability_test.py`: bulk-added 60 unrelated filler facts
(cheap — bypasses per-fact adjudication), then ran the real Prague→Berlin
`remember()` pair on top of that larger graph. Full data:
`stale_guard/scalability_results.json`.

**What scales fine:**
- LLM cost per `remember()` call stays **constant regardless of graph
  size** — bounded by `CANDIDATE_TOP_K` (6) + `MAX_PROPAGATION_CANDIDATES`
  (8), so ~13-14 judge calls whether the graph has 10 facts or 280 nodes.
  Confirmed: both `remember()` calls on the 282-node graph took ~21-23s,
  matching the small-scale runs.
- Raw `get_neighborhood(depth=2)` graph-traversal query stayed fast
  (0.012s) even once the "user" entity hub reached degree 99 (from just 60
  unrelated facts) — no query-latency blowup observed at this scale.

**What doesn't scale — the real finding:** the 2-hop traversal returned
**108-110 nodes** before our Python-side cap, of which only **8** (per
`MAX_PROPAGATION_CANDIDATES`) actually get judged, in whatever order
`get_neighborhood` happens to return them — **not ranked by relevance**.
That's already ~93% of the propagation candidate pool silently discarded
at just 60 filler facts. This means the constant-cost property above is
bought by **arbitrary truncation, not smart selection** — so *recall*
(the mechanism's ability to actually catch a real propagated conflict)
likely **degrades as the graph grows**, even though *cost* stays flat.
Precisely the wrong direction: this problem gets worse exactly as a
long-running agent's memory gets bigger, which is when the whole feature
matters most.

Two other findings from the same run, lower-priority but real: (1) Cognee
extracted **two separate entity nodes** for "user" and "the user" (degree
99 vs 12) rather than resolving them to one — an entity-resolution gap in
Cognee itself that would cause our crawler to silently miss facts anchored
to whichever variant isn't traversed. (2) The read-side (`recall()`) has a
symmetric, untested risk: as the corpus grows, a genuinely-relevant stale
fact could similarly get crowded out of the query's vector top-k and never
trigger a `premise_warning` — only the write-side crowding was empirically
tested here (see the propagation-proof entry).

- [x] **Fix implemented and validated: rank before capping instead of
  arbitrary truncation.** Before implementing, inspected the actual edge
  types in a real 2-hop neighborhood (`DocumentChunk --contains--> Entity`,
  `Entity --is_a--> EntityType`, plus extracted semantic relations like
  `moved_to`) — this ruled out the originally-proposed `edge_types` filter:
  `contains` is precisely the chunk↔entity link the whole mechanism depends
  on, not structural noise; excluding it would have broken propagation
  entirely, not fixed it.

  Instead, `_rank_propagation_candidates()` (`stale_guard/adjudicator.py`)
  ranks every 2-hop candidate by the degree, within the already-fetched
  subgraph, of the *lowest-degree entity connecting it to the new fact* —
  a shared entity connecting only a few facts (e.g. "Prague") is a much
  stronger relevance signal than a generic hub shared by everything (e.g.
  "the user" on a long-running memory), the same intuition as IDF
  down-weighting common terms. Ties (the common case when everything only
  shares the generic hub) fall back to preferring more recently created
  chunks. No extra DB round-trips — computed from the nodes/edges
  `get_neighborhood` already returns.

  Validated with a deterministic unit test (`stale_guard/adjudicator.py`'s
  `_rank_propagation_candidates` called directly, not through the LLM
  pipeline — a real-graph test failed to isolate this cleanly because a
  7-fact corpus let vector similarity trivially cover every candidate,
  leaving nothing for propagation to differentiate): one candidate sharing
  a rare 2-degree connector ("Switzerland") against 22 candidates sharing
  only a 24-degree generic hub ("the user") — the rare-connector candidate
  correctly ranked #1, and recency correctly broke ties among the 22
  generic ones. Confirmed no regression on the original Prague→Berlin case.

## Stretch / if time allows

- [ ] Scale scenario count past 13 (STALE paper's own synthetic-scenario
  construction protocol, ~50 scenarios, was flagged as a fallback in the
  original pitch if the public STALE dataset isn't released).
- [ ] Versioned stale-state history (multiple supersessions over time,
  "un-stale" if a fact becomes true again) using Cognee's existing
  `DataPoint.version`/`update_version()` machinery instead of overwrite-only.
- [ ] Upstream PR: `stale_state` accessor pair on `GraphDBInterface` +
  Ladybug adapter, and the 3-line visualization color patch, are both
  self-contained and mirror existing patterns — worth submitting as real
  PRs to `topoteretes/cognee` (branch from `dev`, per their CONTRIBUTING.md)
  for the $100/PR track, independent of and additional to the main
  submission.
