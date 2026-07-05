"""LLM-graded scoring for the before/after demo, replacing brittle substring
matching. Scores each answer against the two capabilities the STALE
benchmark (arxiv 2605.06527) actually measures:

  - state resolution: does the answer's content align with reality *after*
    the update, rather than the stale pre-update belief?
  - premise resistance: if the query's own phrasing presupposed something
    the update invalidated, did the answer notice and correct it (even
    briefly) instead of silently complying?

A keyword check can't tell "recommends a Prague bike shop" (stale) apart
from "notes the user moved to Berlin, so Prague doesn't apply" (correct) —
both may contain the word "Prague". An LLM grader reading the whole answer
in context can.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from cognee.infrastructure.llm import LLMGateway
from cognee.shared.logging_utils import get_logger

logger = get_logger("stale_guard.grader")

GRADER_SYSTEM_PROMPT = """You are grading whether an AI agent's answer correctly \
reflects the CURRENT state of a user's situation, given a sequence of facts it was \
told — including a later UPDATE that implicitly invalidates something earlier, \
without ever explicitly saying so.

You will be shown:
- ORIGINAL_FACTS: what the agent was told first
- UPDATE: a later observation that changes the situation (may silently invalidate \
one or more ORIGINAL_FACTS, directly or through a downstream consequence)
- QUERY: a question asked afterward, which may presuppose the OLD (now-invalidated) \
state
- ANSWER: the agent's actual response

Grade strictly on content, not tone or politeness:
- reflects_current_state: true if ANSWER's substantive content is consistent with \
reality after UPDATE. false if ANSWER asserts, recommends, or plans around the stale \
pre-UPDATE belief as if it were still true.
- corrected_stale_premise: true/false if QUERY's own phrasing presupposed something \
UPDATE invalidated and ANSWER did/didn't notice and correct it. Use null if QUERY \
had no such stale premise to correct.
- verdict:
    "correct" — reflects_current_state is true, and premise was corrected if needed.
    "stale" — ANSWER treats the invalidated belief as still true anywhere in its content.
    "unclear" — ANSWER dodges (e.g. only asks a clarifying question) without asserting \
either the stale or current belief.
- reasoning: one or two sentences citing the specific phrase that drove the verdict.
"""

USER_PROMPT_TEMPLATE = """ORIGINAL_FACTS:
{facts}

UPDATE: {update}

QUERY: {query}

ANSWER: {answer}

Grade this ANSWER."""


class GradedVerdict(BaseModel):
    reflects_current_state: bool = Field(
        description="Does the answer's content align with reality after UPDATE?"
    )
    corrected_stale_premise: Optional[bool] = Field(
        default=None,
        description="True/false if QUERY presupposed a stale fact and ANSWER did/didn't "
        "correct it; null if QUERY had no stale premise to correct.",
    )
    verdict: Literal["correct", "stale", "unclear"]
    reasoning: str


async def grade_answer(
    facts: list, update: str, query: str, answer: str
) -> GradedVerdict:
    user_prompt = USER_PROMPT_TEMPLATE.format(
        facts="\n".join(f"- {fact}" for fact in facts),
        update=update,
        query=query,
        answer=answer,
    )
    try:
        return await LLMGateway.acreate_structured_output(
            text_input=user_prompt,
            system_prompt=GRADER_SYSTEM_PROMPT,
            response_model=GradedVerdict,
        )
    except Exception as error:
        logger.warning("stale_guard: grader LLM call failed open: %s", error)
        return GradedVerdict(
            reflects_current_state=False,
            corrected_stale_premise=None,
            verdict="unclear",
            reasoning=f"grader error: {error}",
        )
