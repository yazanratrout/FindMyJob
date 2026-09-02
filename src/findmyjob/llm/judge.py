"""LLM holistic fit judgement for a scored job."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from findmyjob.llm.client import LlmClient, LlmResult
from findmyjob.llm.prompts import load_prompt
from findmyjob.models.enums import LlmPurpose

JUDGE_VERSION = "2026-09-02.1"


class JudgeResult(BaseModel):
    holistic_fit: int = Field(ge=0, le=100)
    rationale: str = ""
    missing_qualifications: list[str] = Field(default_factory=list)
    strengths_to_highlight: list[str] = Field(default_factory=list)
    recommendation: Literal["apply", "maybe", "skip"] = "maybe"


def judge_fit(
    *,
    profile_summary: str,
    analysis: dict[str, Any],
    soft_breakdown: dict[str, Any],
    client: LlmClient | None = None,
    run_id: int | None = None,
) -> tuple[JudgeResult, LlmResult]:
    client = client or LlmClient()
    analysis_json = json.dumps(analysis, ensure_ascii=False, default=str)[:6000]
    user = (
        f"=== STUDENT PROFILE ===\n{profile_summary}\n\n"
        f"=== POSTING ANALYSIS ===\n{analysis_json}\n\n"
        f"=== SOFT SCORE BREAKDOWN ===\n{json.dumps(soft_breakdown, default=str)}"
    )
    return client.complete_json(
        purpose=LlmPurpose.JUDGE,
        system=load_prompt("judge") + f"\n\n(judge_version: {JUDGE_VERSION})",
        user=user,
        schema=JudgeResult,
        tier="smart",
        max_tokens=1024,
        run_id=run_id,
    )
