"""Before/after demo: for each scenario, run the SAME facts+update+query through
(a) plain Cognee (add/cognify/search) and (b) STALE-Guard (remember/recall),
then score each answer with an LLM grader (stale_guard/grader.py) against the
STALE benchmark's own dimensions (state resolution, premise resistance)
instead of brittle substring matching — a keyword check can't tell "recommends
Prague" (stale) apart from "notes the move to Berlin, so Prague doesn't apply"
(correct), since both may contain the word "Prague".

This is a demo-grade eval, not a reproduction of the STALE benchmark's full
1,200-query protocol — sized to run in minutes on a single machine for a
hackathon demo, not to produce a peer-reviewable number.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cognee
from stale_guard.grader import grade_answer
from stale_guard.guard import remember, recall
from stale_guard.scenarios import SCENARIOS

RESULTS_PATH = Path(__file__).resolve().parent / "demo_results.json"


async def _reset():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)


async def _score(answer: str, scenario: dict) -> dict:
    graded = await grade_answer(
        facts=scenario["facts"],
        update=scenario["update"],
        query=scenario["query"],
        answer=answer,
    )
    return graded.model_dump()


async def run_baseline(scenario: dict) -> str:
    await _reset()
    for fact in scenario["facts"]:
        await cognee.add(fact)
        await cognee.cognify()
    await cognee.add(scenario["update"])
    await cognee.cognify()
    results = await cognee.search(scenario["query"])
    if isinstance(results, list) and results:
        return str(results[0])
    return str(results)


async def run_guarded(scenario: dict) -> dict:
    await _reset()
    judgements = []
    for fact in scenario["facts"]:
        r = await remember(fact)
        judgements.extend(r["judgements"])
    r = await remember(scenario["update"])
    judgements.extend(r["judgements"])
    result = await recall(scenario["query"])
    result["judgements"] = judgements
    return result


async def main():
    all_results = []
    baseline_tally = {"correct": 0, "stale": 0, "unclear": 0}
    guarded_tally = {"correct": 0, "stale": 0, "unclear": 0}
    propagation_catches = 0  # STALE/REPLACE verdicts found only via graph traversal
    refuted_count = 0  # STALE/REPLACE verdicts the adversarial refuter held back

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"\n[{i}/{len(SCENARIOS)}] {scenario['id']} ({scenario['type']})", flush=True)

        baseline_answer = await run_baseline(scenario)
        baseline_graded = await _score(baseline_answer, scenario)
        baseline_tally[baseline_graded["verdict"]] += 1
        print(f"  baseline [{baseline_graded['verdict']}]: {baseline_answer[:160]}", flush=True)

        guarded = await run_guarded(scenario)
        guarded_answer = guarded["answer"]
        guarded_graded = await _score(guarded_answer, scenario)
        guarded_tally[guarded_graded["verdict"]] += 1
        print(f"  guarded  [{guarded_graded['verdict']}]: {guarded_answer[:160]}", flush=True)
        if guarded["premise_warnings"]:
            print(f"  premise_warning: {guarded['premise_warnings'][0][:160]}", flush=True)

        scenario_propagation_catches = sum(
            1
            for j in guarded["judgements"]
            if j["source"] == "propagation"
            and j["verdict"] in ("STALE", "REPLACE")
            and not j["refuted"]
        )
        propagation_catches += scenario_propagation_catches
        if scenario_propagation_catches:
            print(
                f"  propagation crawler caught {scenario_propagation_catches} "
                f"conflict(s) invisible to plain vector similarity",
                flush=True,
            )

        scenario_refuted = sum(1 for j in guarded["judgements"] if j["refuted"])
        refuted_count += scenario_refuted
        if scenario_refuted:
            print(
                f"  adversarial refuter held back {scenario_refuted} verdict(s) "
                f"(found plausible doubt, not persisted as stale)",
                flush=True,
            )

        all_results.append(
            {
                "id": scenario["id"],
                "type": scenario["type"],
                "query": scenario["query"],
                "baseline_answer": baseline_answer,
                "baseline_grade": baseline_graded,
                "guarded_answer": guarded_answer,
                "guarded_grade": guarded_graded,
                "premise_warnings": guarded["premise_warnings"],
                "judgements": guarded["judgements"],
            }
        )

    n = len(SCENARIOS)
    summary = {
        "n_scenarios": n,
        "baseline_tally": baseline_tally,
        "guarded_tally": guarded_tally,
        "baseline_correct_pct": round(100 * baseline_tally["correct"] / n, 1),
        "guarded_correct_pct": round(100 * guarded_tally["correct"] / n, 1),
        "propagation_only_catches": propagation_catches,
        "refuted_verdicts_held_back": refuted_count,
    }
    print("\n" + "=" * 60)
    print("SUMMARY")
    print(json.dumps(summary, indent=2))

    RESULTS_PATH.write_text(json.dumps({"summary": summary, "results": all_results}, indent=2))
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
