"""State Adjudicator — the write-time half of STALE-Guard.

When new data is remembered, this module finds semantically-neighboring
DocumentChunk nodes already in the graph and asks an LLM judge whether the
new observation implicitly invalidates each of them (STALE benchmark's
Type I / Type II implicit-conflict taxonomy). Verdicts are persisted onto
the graph nodes via the ``stale_state`` accessor pair added to
``GraphDBInterface`` (see graph_db_interface.py / ladybug/adapter.py).
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cognee.infrastructure.databases.graph.get_graph_engine import get_graph_engine
from cognee.infrastructure.databases.vector import get_vector_engine
from cognee.infrastructure.llm import LLMGateway
from cognee.shared.logging_utils import get_logger

from stale_guard.models import RefutationCheck, StaleVerdict

logger = get_logger("stale_guard.adjudicator")

SYSTEM_PROMPT = """You are the State Adjudicator in STALE-Guard, a memory-integrity \
layer for AI agent memory. You compare one OLD_MEMORY statement already stored in \
an agent's knowledge graph against one NEW_OBSERVATION just told to the agent.

Decide the relationship:
- KEEP: OLD_MEMORY is unrelated to or still consistent with NEW_OBSERVATION.
- STALE: NEW_OBSERVATION implicitly invalidates OLD_MEMORY, even though it never \
explicitly negates it. This includes both:
  * Type I (co-referential): the same attribute now holds a different value \
(e.g. "lives in Prague" vs. "just moved to Berlin").
  * Type II (propagated): OLD_MEMORY depends on a precondition that \
NEW_OBSERVATION breaks, even though OLD_MEMORY is never mentioned again \
(e.g. "commutes by bicycle every day" is invalidated by "broke my leg yesterday").
- REPLACE: same as STALE, and NEW_OBSERVATION also supplies the concrete \
replacement value/fact.
- UNKNOWN: genuinely ambiguous — do not guess KEEP just to be safe.

Be decisive about Type II cases: reason about real-world causal/precondition \
links, not just topical or lexical overlap. Respond only via the structured \
schema you are given."""

USER_PROMPT_TEMPLATE = """OLD_MEMORY: "{old_text}"
NEW_OBSERVATION: "{new_text}"

Classify the relationship of OLD_MEMORY given NEW_OBSERVATION."""

REFUTER_SYSTEM_PROMPT = """You are a skeptical second reviewer in STALE-Guard. A \
first judge proposed marking OLD_MEMORY as no-longer-valid because of \
NEW_OBSERVATION. Marking something invalid is destructive — it gets hidden from all \
future answers — so before that happens, actively try to find a genuinely plausible \
reason OLD_MEMORY could still be true despite NEW_OBSERVATION and the judge's \
reasoning (e.g. the judge over-generalized, assumed a precondition that doesn't \
actually hold, or missed that OLD_MEMORY could coexist with NEW_OBSERVATION).
Default to agreeing with the judge (could_still_be_valid=False) unless you find real, \
specific doubt — do not manufacture objections just to hedge."""

REFUTER_USER_PROMPT_TEMPLATE = """OLD_MEMORY: "{old_text}"
NEW_OBSERVATION: "{new_text}"
PROPOSED_VERDICT: {verdict} ({conflict_type})
PROPOSED_REASON: {reason}

Can OLD_MEMORY still plausibly be true despite NEW_OBSERVATION?"""

CANDIDATE_TOP_K = 6
PROPAGATION_DEPTH = 2
MAX_PROPAGATION_CANDIDATES = 8
DOCUMENT_CHUNK_COLLECTION = "DocumentChunk_text"
DOCUMENT_CHUNK_TYPE = "DocumentChunk"


async def find_self_and_semantic_candidates(
    new_text: str, top_k: int = CANDIDATE_TOP_K
) -> "tuple[Optional[str], List[Dict[str, str]]]":
    """Vector-similarity lookup: existing DocumentChunk nodes textually close
    to the new observation. Also identifies the chunk node the new
    observation itself just created (matched by exact text), which is the
    seed for graph-native propagation lookup below. Returns
    ``(self_node_id_or_None, candidates)``.

    Vector similarity alone is enough for Type I (co-referential) conflicts,
    where the old and new statements share vocabulary. It is NOT enough for
    Type II (propagated) conflicts whose downstream fact can use completely
    different words than the triggering observation — see
    ``find_propagation_candidates``.
    """
    vector_engine = get_vector_engine()
    try:
        results = await vector_engine.search(
            DOCUMENT_CHUNK_COLLECTION, new_text, limit=max(top_k, 3), include_payload=True
        )
    except Exception as error:
        logger.warning("stale_guard: semantic candidate search failed open: %s", error)
        return None, []

    self_id = None
    candidates = []
    normalized_new = new_text.strip().casefold()
    for result in results:
        payload = result.payload or {}
        node_id = payload.get("id")
        text = str(payload.get("text") or "").strip()
        if not node_id or not text:
            continue
        if text.casefold() == normalized_new:
            self_id = node_id  # the chunk the new observation itself just created
            continue
        candidates.append({"id": node_id, "text": text})
    return self_id, candidates[:top_k]


def _rank_propagation_candidates(
    self_id: str,
    nodes: List[tuple],
    edges: List[tuple],
    exclude_ids: set,
) -> List[Dict[str, str]]:
    """Rank 2-hop DocumentChunk candidates instead of taking an arbitrary
    DB-return-order prefix.

    On a graph with any real history, ``get_neighborhood`` can return
    hundreds of nodes once a shared subject entity (e.g. "the user")
    accumulates enough edges to become a hub — a 60-fact test graph already
    produced 108-110 candidates for an 8-slot cap. Blindly truncating that
    list discards ~93% of it without regard to relevance.

    Ranks by the degree (within this returned subgraph) of the lowest-degree
    entity connecting self_id to each candidate: a shared entity that only
    connects a handful of facts (e.g. "Prague") is a far stronger relevance
    signal than a generic hub shared by every fact in the graph (e.g. "the
    user") — the same intuition as IDF down-weighting common terms. Ties
    (e.g. every candidate only shares the generic hub) fall back to
    preferring more recently created chunks.
    """
    adjacency: Dict[str, set] = defaultdict(set)
    degree: Dict[str, int] = defaultdict(int)
    for source, target, _relation, _edge_info in edges:
        source, target = str(source), str(target)
        adjacency[source].add(target)
        adjacency[target].add(source)
        degree[source] += 1
        degree[target] += 1

    min_connector_degree: Dict[str, int] = {}
    for connector in adjacency.get(self_id, ()):
        connector_degree = degree[connector]
        for reached in adjacency.get(connector, ()):
            if reached == self_id:
                continue
            if connector_degree < min_connector_degree.get(reached, float("inf")):
                min_connector_degree[reached] = connector_degree

    ranked: List[tuple] = []
    for node_id, node_data in nodes:
        node_id = str(node_id)
        if not isinstance(node_data, dict) or node_data.get("type") != DOCUMENT_CHUNK_TYPE:
            continue
        if node_id in exclude_ids:
            continue
        text = str(node_data.get("text") or "").strip()
        if not text:
            continue
        connector_degree = min_connector_degree.get(node_id, float("inf"))
        created_at = node_data.get("created_at") or 0
        ranked.append((connector_degree, -created_at, node_id, text))

    ranked.sort(key=lambda item: (item[0], item[1]))
    return [{"id": node_id, "text": text} for _, _, node_id, text in ranked]


async def find_propagation_candidates(
    self_id: Optional[str],
    exclude_ids: Optional[set] = None,
    depth: int = PROPAGATION_DEPTH,
    max_candidates: int = MAX_PROPAGATION_CANDIDATES,
) -> List[Dict[str, str]]:
    """Propagation Crawler: walk the graph's actual edges out from the new
    fact's own chunk node (e.g. via shared entities like "the user") to reach
    other DocumentChunk nodes within ``depth`` hops — regardless of whether
    their text is anywhere near the new observation in embedding space. This
    is what catches Type II conflicts like "broke my leg" invalidating a
    "gym leg day" chunk that never mentions legs, injuries, or mobility in a
    way vector similarity alone would reliably surface.

    Uses ``GraphDBInterface.get_neighborhood``, Cognee's existing k-hop
    traversal primitive — no new graph-walking code needed upstream. The
    returned nodes are ranked (see ``_rank_propagation_candidates``) before
    truncating to ``max_candidates``, so the fixed LLM-cost cap is spent on
    the most plausibly relevant candidates rather than an arbitrary prefix.
    """
    if not self_id:
        return []

    graph_engine = await get_graph_engine()
    try:
        nodes, edges = await graph_engine.get_neighborhood([self_id], depth=depth)
    except Exception as error:
        logger.warning("stale_guard: propagation traversal failed open: %s", error)
        return []

    exclude_ids = set(exclude_ids or set())
    exclude_ids.add(self_id)

    ranked = _rank_propagation_candidates(self_id, nodes, edges, exclude_ids)

    # Dedupe while preserving rank order (a node can't repeat, but guard
    # against adapters that might return duplicate rows).
    seen = set()
    candidates = []
    for candidate in ranked:
        if candidate["id"] in seen:
            continue
        seen.add(candidate["id"])
        candidates.append(candidate)
        if len(candidates) >= max_candidates:
            break
    return candidates


async def judge_pair(old_text: str, new_text: str) -> StaleVerdict:
    user_prompt = USER_PROMPT_TEMPLATE.format(old_text=old_text, new_text=new_text)
    try:
        return await LLMGateway.acreate_structured_output(
            text_input=user_prompt,
            system_prompt=SYSTEM_PROMPT,
            response_model=StaleVerdict,
        )
    except Exception as error:
        logger.warning("stale_guard: judge LLM call failed open: %s", error)
        return StaleVerdict(
            verdict="UNKNOWN", conflict_type="none", reason=f"judge error: {error}"
        )


async def refute_verdict(old_text: str, new_text: str, verdict: StaleVerdict) -> RefutationCheck:
    """Adversarial second opinion, run only on STALE/REPLACE verdicts before
    they're persisted — marking something stale is destructive (it's hidden
    from all future answers), so a hallucinated verdict deserves one
    skeptical review rather than being trusted on a single LLM call."""
    user_prompt = REFUTER_USER_PROMPT_TEMPLATE.format(
        old_text=old_text,
        new_text=new_text,
        verdict=verdict.verdict,
        conflict_type=verdict.conflict_type,
        reason=verdict.reason,
    )
    try:
        return await LLMGateway.acreate_structured_output(
            text_input=user_prompt,
            system_prompt=REFUTER_SYSTEM_PROMPT,
            response_model=RefutationCheck,
        )
    except Exception as error:
        logger.warning("stale_guard: refuter LLM call failed open: %s", error)
        # Fail safe: if the refuter itself errors, don't block the original
        # verdict from persisting — refutation is a check, not the source of truth.
        return RefutationCheck(could_still_be_valid=False, reasoning=f"refuter error: {error}")


async def adjudicate_new_fact(
    new_text: str,
    top_k: int = CANDIDATE_TOP_K,
    propagation_depth: int = PROPAGATION_DEPTH,
) -> List[Dict[str, Any]]:
    """Core write-time hook: judge ``new_text`` against (a) its semantic
    neighborhood and (b) its graph-traversal neighborhood (Propagation
    Crawler), persist STALE/REPLACE verdicts, and return every judgement made
    (including KEEP) for logging/demo purposes."""
    self_id, semantic_candidates = await find_self_and_semantic_candidates(
        new_text, top_k=top_k
    )
    propagation_candidates = await find_propagation_candidates(
        self_id,
        exclude_ids={c["id"] for c in semantic_candidates},
        depth=propagation_depth,
    )

    candidates = [{"source": "semantic", **c} for c in semantic_candidates] + [
        {"source": "propagation", **c} for c in propagation_candidates
    ]
    if not candidates:
        return []

    graph_engine = await get_graph_engine()
    stale_at = datetime.now(timezone.utc).isoformat()

    judged: List[Dict[str, Any]] = []
    to_persist: Dict[str, Dict[str, Any]] = {}
    n_refuted = 0
    for candidate in candidates:
        verdict = await judge_pair(candidate["text"], new_text)
        entry = {
            "node_id": candidate["id"],
            "old_text": candidate["text"],
            "new_text": new_text,
            "source": candidate["source"],
            "refuted": False,
            **verdict.model_dump(),
        }

        if verdict.verdict in ("STALE", "REPLACE"):
            refutation = await refute_verdict(candidate["text"], new_text, verdict)
            entry["refutation_reason"] = refutation.reasoning
            if refutation.could_still_be_valid:
                # Second opinion found real doubt — fail safe and don't suppress
                # a memory that might still be true. Downgrade for persistence
                # purposes only; the original judge verdict/reasoning above is
                # kept in the returned entry for audit.
                entry["refuted"] = True
                n_refuted += 1
            else:
                to_persist[candidate["id"]] = {
                    "stale": True,
                    "verdict": verdict.verdict,
                    "reason": verdict.reason,
                    "superseded_by": verdict.superseded_by or new_text,
                    "stale_at": stale_at,
                }

        judged.append(entry)

    if to_persist:
        await graph_engine.set_node_stale_state(to_persist)
        n_propagation_only = sum(
            1
            for node_id in to_persist
            if node_id not in {c["id"] for c in semantic_candidates}
        )
        logger.info(
            "stale_guard: marked %d/%d neighbor(s) stale for observation %r "
            "(%d found only via graph propagation, %d refuted and held back)",
            len(to_persist),
            len(candidates),
            new_text[:60],
            n_propagation_only,
            n_refuted,
        )
    elif n_refuted:
        logger.info(
            "stale_guard: %d verdict(s) refuted and held back for observation %r",
            n_refuted,
            new_text[:60],
        )

    return judged


async def passthrough_extraction(data: Optional[Any] = None) -> Optional[Any]:
    """Identity ``memify()`` extraction task: hands ``data`` straight to the
    enrichment stage unchanged. Needed because ``memify()`` substitutes its
    own default extraction tasks (triplet embeddings) whenever
    ``extraction_tasks`` is falsy — passing this instead keeps ``data`` as
    the raw text the State Adjudicator expects."""
    return data


async def adjudicate_new_fact_task(
    data: Optional[Any] = None,
    judgements_sink: Optional[list] = None,
    **_ignored,
) -> Optional[Any]:
    """Thin ``cognee.Task``-compatible wrapper so State Adjudicator runs as a
    real ``memify()`` enrichment task, e.g.::

        sink = []
        await cognee.memify(
            extraction_tasks=[Task(passthrough_extraction)],
            enrichment_tasks=[Task(adjudicate_new_fact_task, judgements_sink=sink)],
            data=new_text,
        )

    Accepts either a raw string or a list of strings/DataPoints with a
    ``.text``/``.raw_data_location`` style attribute; falls back to str(data).
    Enrichment tasks are expected to pass data through, so the original
    ``data`` is returned unchanged (side effects — the stale-state writes —
    already happened). ``memify()`` itself only returns pipeline run status,
    not task output, so callers that need the judgements (e.g. for
    instrumentation/audit) pass a ``judgements_sink`` list to collect them.
    """
    texts: List[str] = []
    items = data if isinstance(data, list) else [data]
    for item in items:
        if item is None:
            continue
        text = getattr(item, "text", None) or (item if isinstance(item, str) else str(item))
        texts.append(text)

    for text in texts:
        if text:
            judgements = await adjudicate_new_fact(text)
            if judgements_sink is not None:
                judgements_sink.extend(judgements)

    return data
