"""Clean, narratable walkthrough for screen-recording the STALE-Guard demo.

Suppresses Cognee's verbose structlog output (fine for development, unusable
in a recording) and pauses on "press Enter" between beats so narration isn't
rushed to match a fixed timer. Run it, and read the matching voiceover line
(see DEMO_SCRIPT.md) at each pause before hitting Enter.

Two live sections (baseline confusion, then STALE-Guard resolving it) really
call the LLM in real time — not faked — because that's the whole point of
the demo. The harder Type II case and the propagation/scalability findings
are shown from already-captured results (re-running those live would cost
several more minutes of dead air for no extra credibility).
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Must be set before the first `import cognee` — Cognee auto-configures
# structlog at import time reading this same env var, and setup_logging()
# has an early-return guard once configured, so calling it afterward is a
# no-op. Setting the env var first is the only reliable way to suppress the
# verbose pipeline-step logging for a clean recording.
os.environ.setdefault("LOG_LEVEL", "ERROR")

import cognee
from stale_guard.guard import remember, recall

REPO_ROOT = Path(__file__).resolve().parent


def beat(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def pause():
    input("\n  [press Enter to continue]")


async def main():
    beat("1/5 — BASELINE: plain Cognee gets confused")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    await cognee.add("The user lives in Prague and commutes to work by bicycle every day.")
    await cognee.cognify()
    await cognee.add("The user just moved to Berlin last week.")
    await cognee.cognify()
    baseline_answer = await cognee.search("Recommend me a good bike shop near where I live.")
    print("\n  query: 'Recommend me a good bike shop near where I live.'")
    print(f"  baseline answer:\n  > {baseline_answer[0] if baseline_answer else baseline_answer}")
    pause()

    beat("2/5 — STALE-GUARD: write-time adjudication catches the conflict")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    r1 = await remember("The user lives in Prague and commutes to work by bicycle every day.")
    print("\n  remember(\"...lives in Prague and commutes by bicycle...\")")
    print(f"  judgements: {r1['judgements']}  (nothing to compare against yet)")
    pause()

    r2 = await remember("The user just moved to Berlin last week.")
    print("\n  remember(\"...just moved to Berlin last week.\")")
    for j in r2["judgements"]:
        print(f"  -> verdict={j['verdict']}  conflict_type={j['conflict_type']}")
        print(f"     reason: {j['reason']}")
        print(f"     superseded_by: {j['superseded_by']}")
    pause()

    beat("3/5 — STALE-GUARD: constrained recall, same query")
    result = await recall("Recommend me a good bike shop near where I live.")
    print("\n  query: 'Recommend me a good bike shop near where I live.'")
    print(f"  answer:\n  > {result['answer']}")
    if result["premise_warnings"]:
        print(f"\n  premise_warning:\n  > {result['premise_warnings'][0]}")
    pause()

    beat("4/5 — VISUAL: the stale node in Cognee's own graph visualizer")
    print(f"\n  open: {REPO_ROOT / 'graph_visualization.html'}")
    print("  (the red node is the superseded Prague/bicycle-commute fact)")
    pause()

    beat("5/5 — WE WENT FURTHER: propagation crawler + scalability, proven")
    prop = json.loads((REPO_ROOT / "propagation_proof_results.json").read_text())
    print(f"\n  propagation_proof.py — {prop['outcome']}")
    scale = json.loads((REPO_ROOT / "scalability_results.json").read_text())
    print(
        f"\n  scalability_test.py — graph grew to {scale['graph_size_nodes']} nodes, "
        f"'user' hub reached degree {scale['hub_degrees_top5'][0]['degree']}"
    )
    print(
        f"  remember() cost stayed flat: {scale['t_remember_target_seconds']}s / "
        f"{scale['t_remember_trigger_seconds']}s — same as on a 3-node graph"
    )
    print("  (candidate ranking fix for the effectiveness-at-scale gap: see TODO.md)")


if __name__ == "__main__":
    asyncio.run(main())
