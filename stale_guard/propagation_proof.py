"""Controlled proof that the Propagation Crawler (graph traversal) catches
Type II conflicts that vector-similarity search alone would miss.

The main demo (demo.py) reported propagation_only_catches: 0 —
an honest artifact of its own small size: each scenario holds only 2-3 total
facts, so a vector top-k=6 search trivially returns every chunk in the graph
regardless of true semantic distance. That doesn't mean propagation is
unneeded; it means the demo corpus was too small to need it.

This script builds a bigger, adversarial memory graph on purpose: ~15 filler
facts thematically crowded around the trigger's vocabulary (skiing, injury,
leg) compete for the vector top-k slots, while the true Type II target fact
("commutes by bicycle every day") shares zero vocabulary with the trigger and
gets pushed out of similarity search entirely. Graph traversal
(get_neighborhood, depth=2) should still reach it via the shared "user"
entity node, because that's a structural link, not a lexical one.

Uses the exact same production code path as guard.remember() (no
duplicated logic) so this is a real test of shipped behavior, not a
hand-rolled demonstration.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cognee
from stale_guard.guard import remember

RESULTS_PATH = Path(__file__).resolve().parent / "propagation_proof_results.json"

# Deliberately crowded with ski/leg/injury vocabulary to out-rank the real
# target in a vector-similarity search against the trigger fact below.
NOISE_FACTS = [
    "The user went on a skiing trip to the Alps last winter.",
    "The user is already planning another ski vacation for next season.",
    "The user sprained their ankle while skiing two years ago.",
    "The user's friend broke an arm snowboarding last month.",
    "The user saw a physical therapist after a previous skiing injury.",
    "The user bought new ski boots and poles this year.",
    "The user watched a documentary about extreme skiing accidents.",
    "The user's doctor recommended rest after a leg injury last winter.",
    "The user has an old scar on their leg from a skiing fall years ago.",
    "The user researched ski resorts known for good injury insurance.",
    "The user's cousin also broke a leg skiing two winters ago.",
    "The user packed a first-aid kit before this year's ski trip.",
    "The user has been nervous about leg injuries since a childhood skiing fall.",
    "The user asked their insurance provider about ski-accident coverage.",
    "The user's ski instructor warned about icy slopes this season.",
]

TARGET_FACT = "The user commutes to work by bicycle every day."
TRIGGER_FACT = "The user broke their leg yesterday in a skiing accident."


async def main():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    for i, fact in enumerate(NOISE_FACTS, 1):
        print(f"remembering noise fact {i}/{len(NOISE_FACTS)}", flush=True)
        await remember(fact)

    print("remembering TARGET_FACT", flush=True)
    await remember(TARGET_FACT)

    print("remembering TRIGGER_FACT (this is where adjudication happens)", flush=True)
    result = await remember(TRIGGER_FACT)

    target_norm = TARGET_FACT.strip().casefold()
    target_judgements = [
        j for j in result["judgements"] if j["old_text"].strip().casefold() == target_norm
    ]
    semantic_judgements = [j for j in result["judgements"] if j["source"] == "semantic"]
    propagation_judgements = [j for j in result["judgements"] if j["source"] == "propagation"]

    print("\n" + "=" * 60)
    print(f"Total candidates judged: {len(result['judgements'])}")
    print(f"  via vector similarity (semantic): {len(semantic_judgements)}")
    for j in semantic_judgements:
        print(f"    - {j['old_text'][:70]!r} -> {j['verdict']}")
    print(f"  via graph traversal (propagation): {len(propagation_judgements)}")
    for j in propagation_judgements:
        print(f"    - {j['old_text'][:70]!r} -> {j['verdict']}")

    if not target_judgements:
        outcome = "TARGET_FACT was not found by either method (inconclusive)"
    else:
        sources = {j["source"] for j in target_judgements}
        if sources == {"propagation"}:
            outcome = (
                "PROVEN: TARGET_FACT was invisible to vector similarity (crowded out "
                "by noise) and was only found via graph traversal."
            )
        elif "semantic" in sources:
            outcome = (
                "NOT PROVEN THIS RUN: TARGET_FACT still ranked in the vector-similarity "
                "top-k despite the noise facts."
            )
        else:
            outcome = "inconclusive"

    print("\n" + outcome)

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "target_fact": TARGET_FACT,
                "trigger_fact": TRIGGER_FACT,
                "n_noise_facts": len(NOISE_FACTS),
                "semantic_judgements": semantic_judgements,
                "propagation_judgements": propagation_judgements,
                "target_judgements": target_judgements,
                "outcome": outcome,
            },
            indent=2,
        )
    )
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
