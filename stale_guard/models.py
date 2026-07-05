from typing import Literal, Optional
from pydantic import BaseModel, Field


class StaleVerdict(BaseModel):
    """Structured verdict returned by the State Adjudicator LLM judge for one
    (old_memory, new_observation) pair, following the STALE benchmark's
    KEEP/STALE/REPLACE/UNKNOWN taxonomy (arxiv 2605.06527)."""

    verdict: Literal["KEEP", "STALE", "REPLACE", "UNKNOWN"] = Field(
        description="KEEP: old memory unaffected. STALE: new observation implicitly "
        "invalidates the old memory. REPLACE: same as STALE, and the new observation "
        "directly supplies the replacement value. UNKNOWN: cannot confidently decide."
    )
    conflict_type: Literal["type1_coreferential", "type2_propagated", "none"] = Field(
        description="type1_coreferential: same attribute, contradicting value (e.g. "
        "lives in Prague -> lives in Berlin). type2_propagated: the new observation "
        "invalidates a *downstream* fact that depends on it without mentioning it "
        "directly (e.g. broke a leg -> daily cycling commute is no longer valid). "
        "none: verdict is KEEP."
    )
    reason: str = Field(description="One-sentence justification a user could audit.")
    superseded_by: Optional[str] = Field(
        default=None,
        description="If REPLACE or STALE, the short current-truth statement that "
        "should be treated as authoritative going forward. Null otherwise.",
    )


class RefutationCheck(BaseModel):
    """Adversarial second opinion on a STALE/REPLACE verdict, before it's
    persisted. A hallucinated STALE verdict silently suppresses a true memory
    forever, so anything destructive gets one skeptical review first."""

    could_still_be_valid: bool = Field(
        description="True if you can find a genuinely plausible reason OLD_MEMORY "
        "might still be true despite NEW_OBSERVATION and the proposed verdict — "
        "i.e. you are refuting the verdict. False if you agree the verdict is sound. "
        "Default to False (agree) unless you find real doubt; do not manufacture "
        "objections just to hedge."
    )
    reasoning: str = Field(description="One-sentence justification.")
