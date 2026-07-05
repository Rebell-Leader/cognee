"""Scalability probe: does the mechanism still work, and how expensive does
it get, as the memory graph grows well past the 2-3-fact toy scenarios in
demo.py?

Two things scale independently and need separate answers:
  1. LLM cost per remember() call — bounded by CANDIDATE_TOP_K +
     MAX_PROPAGATION_CANDIDATES regardless of total graph size (a fixed
     number of judge/refuter calls per new fact). Cheap to confirm.
  2. Graph-traversal cost for the Propagation Crawler — NOT obviously
     bounded. get_neighborhood(depth=2) runs an unbounded variable-length
     Cypher path query (MATCH (seed)-[r*1..2]-(neighbor), no LIMIT) before
     our Python-side candidate cap ever applies. If a central entity (e.g.
     "the user") accumulates many edges over a long-running agent's
     lifetime, this traversal has to materialize every 2-hop path through
     that hub *before* truncation — a classic super-node problem. This
     script builds a bigger, more connected graph cheaply (bulk add+cognify,
     skipping per-fact adjudication for filler) and measures both the raw
     get_neighborhood cost and the full remember() cost at that size.
"""

import asyncio
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cognee
from cognee.infrastructure.databases.graph.get_graph_engine import get_graph_engine
from stale_guard.adjudicator import find_self_and_semantic_candidates, find_propagation_candidates
from stale_guard.guard import remember

RESULTS_PATH = Path(__file__).resolve().parent / "scalability_results.json"

N_FILLER_FACTS = 60

FILLER_TOPICS = [
    "reads science fiction novels", "plays chess on weekends", "collects vinyl records",
    "enjoys cooking Thai food", "practices yoga every morning", "learns Spanish on an app",
    "watches documentaries about space", "grows tomatoes in a garden", "plays the guitar",
    "follows a local football team", "does woodworking as a hobby", "enjoys hiking trails",
    "paints watercolor landscapes", "brews their own coffee", "volunteers at an animal shelter",
    "runs a small book club", "collects vintage cameras", "practices calligraphy",
    "enjoys board game nights", "goes birdwatching on weekends", "knits scarves in winter",
    "follows tech news podcasts", "plays video games in the evening", "bakes sourdough bread",
    "studies astronomy as a hobby", "does pottery classes on Tuesdays", "enjoys stand-up comedy shows",
    "collects rare stamps", "practices meditation daily", "restores old furniture",
    "follows a fantasy football league", "enjoys rock climbing", "writes short stories",
    "keeps a succulent garden", "plays in a local trivia league", "enjoys jazz music",
    "does home brewing as a hobby", "practices photography on weekends", "collects comic books",
    "enjoys sailing on the lake", "does crossword puzzles daily", "follows Formula 1 racing",
    "practices archery at a local range", "enjoys pottery painting", "collects fountain pens",
    "does long-distance swimming", "enjoys escape rooms with friends", "grows herbs on a balcony",
    "practices salsa dancing", "follows a fantasy book series", "enjoys geocaching on weekends",
    "does amateur astronomy photography", "collects antique maps", "practices juggling",
    "enjoys kayaking in summer", "follows a local theater group", "does beekeeping as a hobby",
    "collects mechanical keyboards", "practices origami", "enjoys wine and cheese pairings",
    "follows international news closely",
]


def _filler_fact(i: int) -> str:
    topic = FILLER_TOPICS[i % len(FILLER_TOPICS)]
    return f"The user {topic}."


async def main():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    print(f"Adding {N_FILLER_FACTS} filler facts (bulk add, no per-fact adjudication)...", flush=True)
    t0 = time.monotonic()
    for i in range(N_FILLER_FACTS):
        await cognee.add(_filler_fact(i))
    t_add = time.monotonic() - t0
    print(f"  add() x{N_FILLER_FACTS}: {t_add:.1f}s", flush=True)

    t0 = time.monotonic()
    await cognee.cognify()
    t_cognify = time.monotonic() - t0
    print(f"  bulk cognify(): {t_cognify:.1f}s", flush=True)

    graph_engine = await get_graph_engine()
    nodes, edges = await graph_engine.get_graph_data()
    print(f"Graph size after filler: {len(nodes)} nodes, {len(edges)} edges", flush=True)

    # Find "the user" entity node(s) and their degree, to see how connected
    # the natural hub has become.
    user_like_nodes = [
        (nid, ndata) for nid, ndata in nodes
        if isinstance(ndata, dict) and ndata.get("type") == "Entity"
        and "user" in str(ndata.get("name", "")).lower()
    ]
    hub_degrees = []
    for nid, ndata in user_like_nodes:
        node_edges = await graph_engine.get_edges(nid)
        hub_degrees.append({"id": nid, "name": ndata.get("name"), "degree": len(node_edges)})
    hub_degrees.sort(key=lambda h: -h["degree"])
    print(f"'user'-like entity nodes and degree: {hub_degrees[:5]}", flush=True)

    # Now remember() the real conflict pair on top of this bigger graph.
    print("\nremembering target fact (Prague/bicycle)...", flush=True)
    t0 = time.monotonic()
    r1 = await remember("The user lives in Prague and commutes to work by bicycle every day.")
    t_remember_target = time.monotonic() - t0
    print(f"  remember(): {t_remember_target:.1f}s, judgements={len(r1['judgements'])}", flush=True)

    print("\nremembering trigger fact (moved to Berlin)...", flush=True)
    t0 = time.monotonic()
    r2 = await remember("The user just moved to Berlin last week.")
    t_remember_trigger = time.monotonic() - t0
    print(f"  remember(): {t_remember_trigger:.1f}s, judgements={len(r2['judgements'])}", flush=True)

    # Isolate raw graph-traversal cost from LLM judging cost: find the
    # trigger's own chunk id and time get_neighborhood directly.
    self_id, semantic = await find_self_and_semantic_candidates(
        "The user just moved to Berlin last week."
    )
    t0 = time.monotonic()
    propagation = await find_propagation_candidates(self_id, exclude_ids={c["id"] for c in semantic})
    t_propagation_lookup = time.monotonic() - t0
    print(
        f"\nIsolated get_neighborhood(depth=2) call: {t_propagation_lookup:.3f}s, "
        f"{len(propagation)} candidates returned (post-cap)",
        flush=True,
    )

    result = {
        "n_filler_facts": N_FILLER_FACTS,
        "graph_size_nodes": len(nodes),
        "graph_size_edges": len(edges),
        "hub_degrees_top5": hub_degrees[:5],
        "t_bulk_add_seconds": round(t_add, 2),
        "t_bulk_cognify_seconds": round(t_cognify, 2),
        "t_remember_target_seconds": round(t_remember_target, 2),
        "t_remember_trigger_seconds": round(t_remember_trigger, 2),
        "t_isolated_propagation_lookup_seconds": round(t_propagation_lookup, 3),
        "propagation_candidates_returned": len(propagation),
    }
    RESULTS_PATH.write_text(json.dumps(result, indent=2))
    print(f"\nWrote {RESULTS_PATH}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
