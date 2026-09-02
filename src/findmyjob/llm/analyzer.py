"""LLM extraction of structured facts from a job posting."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from findmyjob.llm.client import LlmClient, LlmResult
from findmyjob.llm.prompts import load_prompt
from findmyjob.models.enums import LlmPurpose

#: Bump when the prompt or output shape changes — invalidates cached analyses.
ANALYZER_VERSION = "2026-09-02.1"


class AnalyzedSkill(BaseModel):
    name: str
    required: bool = False


class AnalyzedLanguage(BaseModel):
    lang: str
    cefr: str | None = None
    required: bool = True


class JobAnalysisResult(BaseModel):
    must_haves: list[str] = Field(default_factory=list)
    nice_haves: list[str] = Field(default_factory=list)
    skills: list[AnalyzedSkill] = Field(default_factory=list)
    languages: list[AnalyzedLanguage] = Field(default_factory=list)
    weekly_hours: int | None = None
    weekly_hours_basis: Literal["stated", "inferred", "unknown"] = "unknown"
    contract_type: str = "unknown"
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: Literal["hour", "month", "year"] | None = None
    start_date_text: str | None = None
    deadline: date | None = None
    enrollment_required: Literal["yes", "no", "unknown"] = "unknown"
    english_only: bool = False
    application_method: Literal["ats_form", "email", "external", "unknown"] = "unknown"
    documents_requested: list[str] = Field(default_factory=list)
    seniority: Literal["student", "entry", "junior", "mid", "unknown"] = "unknown"
    red_flags: list[str] = Field(default_factory=list)
    source_snippets: dict[str, str] = Field(default_factory=dict)


def _user_message(*, title: str, company: str, city: str, jd_text: str) -> str:
    return (
        f"Company: {company or 'unknown'}\n"
        f"Title: {title}\n"
        f"Target city (for context only): {city or 'n/a'}\n\n"
        f"--- POSTING ---\n{jd_text.strip()[:12000]}"
    )


def analyze_posting(
    *,
    title: str,
    company: str,
    city: str,
    jd_text: str,
    client: LlmClient | None = None,
    run_id: int | None = None,
) -> tuple[JobAnalysisResult, LlmResult]:
    client = client or LlmClient()
    return client.complete_json(
        purpose=LlmPurpose.ANALYZE,
        system=load_prompt("analyzer") + f"\n\n(analyzer_version: {ANALYZER_VERSION})",
        user=_user_message(title=title, company=company, city=city, jd_text=jd_text),
        schema=JobAnalysisResult,
        tier="cheap",
        max_tokens=2048,
        run_id=run_id,
    )
