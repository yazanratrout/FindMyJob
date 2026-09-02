"""LLM-backed keyword suggestions for the search-tuning step of onboarding."""

from __future__ import annotations

from pydantic import BaseModel, Field

from findmyjob.llm.client import LlmClient, LlmResult
from findmyjob.llm.prompts import load_prompt
from findmyjob.models.enums import LlmPurpose


class KeywordSuggestions(BaseModel):
    core: list[str] = Field(default_factory=list)
    adjacent: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    likely_noise: list[str] = Field(default_factory=list)


def suggest_keywords(
    *,
    target_fields: list[str],
    target_titles: list[str],
    skills: list[str],
    client: LlmClient | None = None,
    run_id: int | None = None,
) -> tuple[KeywordSuggestions, LlmResult]:
    client = client or LlmClient()
    user = (
        f"Target fields: {', '.join(target_fields) or '(none given)'}\n"
        f"Target job titles: {', '.join(target_titles) or '(none given)'}\n"
        f"Skills from CV: {', '.join(skills) or '(none given)'}"
    )
    return client.complete_json(
        purpose=LlmPurpose.KEYWORD_SUGGEST,
        system=load_prompt("keyword_suggest"),
        user=user,
        schema=KeywordSuggestions,
        tier="cheap",
        max_tokens=1024,
        run_id=run_id,
    )
