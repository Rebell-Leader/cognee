"""High-level STALE-Guard API: drop-in ``remember`` / ``recall`` pair.

``remember`` wraps Cognee's add+cognify and then runs the State Adjudicator
against the new fact's semantic neighborhood (write-time invalidation).

``recall`` wraps a constrained-context completion: it fetches the chunks a
plain vector/graph search would surface, filters out anything the State
Adjudicator has since marked stale, and answers strictly from the
remaining current facts — surfacing a ``premise_warning`` whenever the
query's own premise leaned on a fact that turned out to be stale.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

import cognee
from cognee.infrastructure.databases.graph.get_graph_engine import get_graph_engine
from cognee.infrastructure.databases.vector import get_vector_engine
from cognee.infrastructure.llm import LLMGateway
from cognee.modules.pipelines.tasks.task import Task
from cognee.shared.logging_utils import get_logger

from stale_guard.adjudicator import (
    DOCUMENT_CHUNK_COLLECTION,
    adjudicate_new_fact_task,
    passthrough_extraction,
)

logger = get_logger("stale_guard.guard")


class _Answer(BaseModel):
    answer: str = Field(description="Final answer text, premise-corrected if needed.")

ANSWER_SYSTEM_PROMPT = """You answer a user's question using ONLY the CURRENT_FACTS \
listed below. Some facts the agent previously believed have since been marked \
OUTDATED — they are listed separately, with what superseded them. Never treat an \
OUTDATED fact as true, even if the user's question assumes it. If the question's \
premise relies on an OUTDATED fact, briefly correct the premise before answering.
If CURRENT_FACTS is empty, say you don't have enough information."""


async def remember(text: str, dataset: str = "main_dataset") -> Dict[str, Any]:
    """Write-time hook: ingest ``text``, then run the State Adjudicator as a
    real ``cognee.memify()`` enrichment pipeline (not a bespoke side-call) to
    adjudicate it against the graph's existing semantic + graph-traversal
    neighborhood, marking anything it implicitly invalidates."""
    await cognee.add(text, dataset_name=dataset)
    await cognee.cognify(datasets=[dataset])

    judgements_sink: list = []
    await cognee.memify(
        extraction_tasks=[Task(passthrough_extraction)],
        enrichment_tasks=[Task(adjudicate_new_fact_task, judgements_sink=judgements_sink)],
        data=text,
        dataset=dataset,
    )
    return {"text": text, "judgements": judgements_sink}


async def _fetch_context_chunks(query_text: str, top_k: int) -> List[Dict[str, Any]]:
    vector_engine = get_vector_engine()
    try:
        results = await vector_engine.search(
            DOCUMENT_CHUNK_COLLECTION, query_text, limit=top_k, include_payload=True
        )
    except Exception as error:
        logger.warning("stale_guard: recall context search failed open: %s", error)
        return []

    chunks = []
    for result in results:
        payload = result.payload or {}
        node_id = payload.get("id")
        text = str(payload.get("text") or "").strip()
        if not node_id or not text:
            continue
        chunks.append({"id": node_id, "text": text})
    return chunks


async def recall(
    query_text: str, dataset: str = "main_dataset", top_k: int = 8
) -> Dict[str, Any]:
    """Read-time hook: constrained-recall completion that downranks/excludes
    stale nodes and raises a premise_warning when the query itself presumes a
    now-stale fact."""
    chunks = await _fetch_context_chunks(query_text, top_k=top_k)
    if not chunks:
        return {"answer": "I don't have enough information.", "premise_warnings": [], "chunks": []}

    graph_engine = await get_graph_engine()
    stale_map = await graph_engine.get_node_stale_state([c["id"] for c in chunks])

    current_facts: List[str] = []
    stale_facts: List[Dict[str, Any]] = []
    for chunk in chunks:
        state = stale_map.get(chunk["id"], {})
        if state.get("stale"):
            stale_facts.append(
                {
                    "text": chunk["text"],
                    "reason": state.get("reason", ""),
                    "superseded_by": state.get("superseded_by"),
                }
            )
        else:
            current_facts.append(chunk["text"])

    premise_warnings = [
        f'"{sf["text"]}" is OUTDATED ({sf["reason"]}). '
        f'Superseded by: {sf["superseded_by"]}'
        for sf in stale_facts
    ]

    context_block = "CURRENT_FACTS:\n" + (
        "\n".join(f"- {fact}" for fact in current_facts) if current_facts else "(none)"
    )
    if stale_facts:
        context_block += "\n\nOUTDATED (do not use, listed only for context):\n" + "\n".join(
            f'- "{sf["text"]}" -> superseded by: {sf["superseded_by"]} ({sf["reason"]})'
            for sf in stale_facts
        )

    user_prompt = f"{context_block}\n\nQUESTION: {query_text}"
    try:
        answer = await LLMGateway.acreate_structured_output(
            text_input=user_prompt,
            system_prompt=ANSWER_SYSTEM_PROMPT,
            response_model=_Answer,
        )
        answer_text = answer.answer
    except Exception as error:
        logger.warning("stale_guard: recall completion failed open: %s", error)
        answer_text = "(error generating answer)"

    return {
        "answer": answer_text,
        "premise_warnings": premise_warnings,
        "chunks": chunks,
        "current_facts": current_facts,
        "stale_facts": stale_facts,
    }
