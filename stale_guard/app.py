"""Gradio walkthrough app for recording the STALE-Guard demo.

Three tabs, meant to be clicked through in order while narrating:
  1. The Problem   — static intro, no backend calls.
  2. Live Demo      — real remember()/recall() calls against a live LLM,
                       one button per beat so you control pacing.
  3. Graph & Proof  — link to the graph visualization + the propagation
                       and scalability findings.

Run with `python stale_guard/app.py` from inside the `cognee/` repo, then
open the printed localhost URL in a browser for recording.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("LOG_LEVEL", "ERROR")

import gradio as gr

import cognee
from stale_guard.guard import remember, recall

REPO_ROOT = Path(__file__).resolve().parent
gr.set_static_paths(paths=[REPO_ROOT])

PROBLEM_MD = """
# STALE-Guard
### Memory that knows when to stop believing itself

Cognee, like every other agent-memory framework, retrieves facts extremely well.
None of them check whether a stored fact has quietly stopped being true.

If a user says *"I just moved to Berlin"* three months after their agent stored
*"user lives in Prague,"* standard memory keeps **both** facts around. Ask
*"recommend me a bike shop near where I live"* afterward, and the agent can
confidently answer using Prague, simply because that memory matches the query
more strongly, whether or not it's still true.

That's **implicit conflict**: a new observation invalidates a prior belief
without ever explicitly negating it.

| | |
|---|---|
| **Type I (co-referential)** | Same attribute, new value. "Lives in Prague" becomes "just moved to Berlin." |
| **Type II (propagated)** | A *downstream* fact is invalidated and never mentioned again. "Broke my leg yesterday" quietly invalidates "commutes by bicycle every day." |

The [STALE benchmark](https://arxiv.org/abs/2605.06527) (May 2026) puts a number
on this: the best frontier LLM only hits **55.2%** accuracy at catching implicit
conflicts, and the memory frameworks it evaluated (Mem0, Zep, LightMem, A-mem,
LiCoMemory) all score **under 18%**.

## What we built

- A **State Adjudicator** that runs at write time, judging new facts against
  the graph two ways: vector similarity, and real graph traversal through
  shared entities (catches Type II conflicts vector search alone misses).
- An **adversarial refutation guardrail** — before anything is marked stale,
  a second LLM call tries to argue it's wrong, since a hallucinated verdict
  silently hides a true memory forever.
- **Constrained Recall** at read time, which answers from current facts only
  and raises a *premise warning* when a question assumes something stale.

**Result on 13 hand-crafted scenarios: baseline Cognee 53.8% correct → STALE-Guard 100% correct.**
"""

DEMO_MD = """
## Live demo

Same two facts, same question, run twice: once through plain Cognee, once
through STALE-Guard. Every button below makes a real LLM call — nothing is
pre-scripted.
"""

GRAPH_PROOF_MD = f"""
## See it in the graph

Cognee's own graph visualizer, patched to color invalidated nodes red
(3 lines, reusing the same pattern Cognee already uses for ontology matches).

### <a href="/gradio_api/file={REPO_ROOT.name}/graph_visualization.html" target="_blank">Open the graph visualization →</a>

---

## We didn't stop at the demo

**Propagation Crawler, proven:** a small demo corpus lets vector search
trivially return every fact, so nothing *needed* graph traversal to be found.
We built an adversarial test instead — 15 filler facts loaded with vocabulary
that reads more similar to the trigger than the real conflict does. Vector
search missed the real conflict completely. Graph traversal found it anyway,
through the shared "user" entity.

**Scalability, measured, not assumed:** grew the graph to 282 nodes with a
99-degree hub entity. LLM cost per `remember()` call stayed flat (~21-23s,
same as a 3-node graph). Effectiveness didn't, at first — found and fixed a
real gap where 93% of graph-traversal candidates were being silently
discarded by arbitrary truncation instead of ranked selection.

Full detail, numbers, and code: see `TODO.md` and `STALE_GUARD.md` in the repo.
"""


# Cognee caches async primitives (e.g. connection-pool locks) tied to
# whichever event loop first touched them. asyncio.run() creates and tears
# down a fresh loop per call, so a second button click collides with a lock
# still bound to the first click's loop ("bound to a different event loop").
# One persistent loop, reused for every callback, avoids that entirely.
_loop = asyncio.new_event_loop()


def _run(coro):
    return _loop.run_until_complete(coro)


async def _run_baseline():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    await cognee.add("The user lives in Prague and commutes to work by bicycle every day.")
    await cognee.cognify()
    await cognee.add("The user just moved to Berlin last week.")
    await cognee.cognify()
    answer = await cognee.search("Recommend me a good bike shop near where I live.")
    text = str(answer[0]) if isinstance(answer, list) and answer else str(answer)
    return f"**Query:** Recommend me a good bike shop near where I live.\n\n**Baseline answer:**\n\n{text}"


def run_baseline():
    return _run(_run_baseline())


async def _remember_fact_1():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    result = await remember("The user lives in Prague and commutes to work by bicycle every day.")
    return "**Remembered:** \"The user lives in Prague and commutes to work by bicycle every day.\"\n\nNothing to compare against yet — this is the first fact."


def remember_fact_1():
    return _run(_remember_fact_1())


async def _remember_fact_2():
    result = await remember("The user just moved to Berlin last week.")
    lines = ["**Remembered:** \"The user just moved to Berlin last week.\"\n"]
    for j in result["judgements"]:
        lines.append(f"- **Verdict:** `{j['verdict']}` ({j['conflict_type']})")
        lines.append(f"  - **Reason:** {j['reason']}")
        lines.append(f"  - **Superseded by:** {j['superseded_by']}")
    return "\n".join(lines)


def remember_fact_2():
    return _run(_remember_fact_2())


async def _ask_stale_guard():
    result = await recall("Recommend me a good bike shop near where I live.")
    text = f"**Query:** Recommend me a good bike shop near where I live.\n\n**Answer:**\n\n{result['answer']}"
    if result["premise_warnings"]:
        text += f"\n\n**Premise warning:**\n\n> {result['premise_warnings'][0]}"
    return text


def ask_stale_guard():
    return _run(_ask_stale_guard())


with gr.Blocks(title="STALE-Guard") as demo:
    with gr.Tabs():
        with gr.Tab("1. The Problem"):
            gr.Markdown(PROBLEM_MD)

        with gr.Tab("2. Live Demo"):
            gr.Markdown(DEMO_MD)

            gr.Markdown("### Baseline: plain Cognee")
            baseline_btn = gr.Button("Run baseline (plain Cognee)", variant="secondary")
            baseline_out = gr.Markdown()
            baseline_btn.click(fn=run_baseline, outputs=baseline_out)

            gr.Markdown("### STALE-Guard: write-time adjudication")
            with gr.Row():
                remember1_btn = gr.Button("1. Remember: lives in Prague, bikes daily")
                remember2_btn = gr.Button("2. Remember: just moved to Berlin")
            remember_out = gr.Markdown()
            remember1_btn.click(fn=remember_fact_1, outputs=remember_out)
            remember2_btn.click(fn=remember_fact_2, outputs=remember_out)

            gr.Markdown("### STALE-Guard: constrained recall")
            ask_btn = gr.Button("Ask: recommend a bike shop near where I live", variant="primary")
            ask_out = gr.Markdown()
            ask_btn.click(fn=ask_stale_guard, outputs=ask_out)

        with gr.Tab("3. Graph & Proof"):
            gr.Markdown(GRAPH_PROOF_MD)


if __name__ == "__main__":
    demo.launch()
