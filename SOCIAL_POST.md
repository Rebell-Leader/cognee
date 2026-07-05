Built for #CogneeHackathon: STALE-Guard.

Every memory framework retrieves the right fact. None of them know when that fact stopped being true.

STALE-Guard adds a write-time judge to Cognee: it catches "user moved to Berlin" silently invalidating "user lives in Prague" — and the harder case, "broke my leg yesterday" silently invalidating "commutes by bike daily," even though cycling is never mentioned again.

Ask a question that assumes the old fact, and instead of confidently answering wrong, it flags the premise and corrects itself.

The catch finds conflicts two ways: vector similarity, and actual graph traversal through shared entities — the second one catches Type II conflicts that share zero vocabulary with the trigger. Proved it with an adversarial test: 15 filler facts crowded out the real target from vector search entirely; graph traversal found it anyway.

Nothing gets marked invalid without a second, adversarial LLM opinion first — marking something stale is destructive, so a hallucinated verdict gets challenged before it's persisted.

Built on @cognee_'s own extension points — a new stale_state accessor mirroring their existing feedback_weight/truth_state pattern, a real memify() enrichment pipeline (not a side-call), and stale nodes now render red in Cognee's own graph visualizer. Nothing forked, nothing bolted on.

Benchmark behind this: STALE (arxiv 2605.06527) — best frontier LLM hits 55.2% on implicit-conflict detection; every memory framework tested scores under 18%.

repo: <link>
