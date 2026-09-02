"""LLM-backed CV / document parser producing a structured profile."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from findmyjob.llm.client import LlmClient, LlmResult
from findmyjob.llm.prompts import load_prompt
from findmyjob.models.enums import LlmPurpose


class Address(BaseModel):
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = None


class ParsedSkill(BaseModel):
    name: str
    category: str = "technical"
    proficiency: int = Field(default=3, ge=1, le=5)
    years: float | None = None
    evidence: str = ""


class ParsedLanguage(BaseModel):
    lang: str
    cefr: str


class WorkItem(BaseModel):
    title: str = ""
    org: str = ""
    start: date | None = None
    end: date | None = None
    bullets: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    institution: str = ""
    program: str = ""
    start: date | None = None
    end: date | None = None
    grade: str | None = None


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    tech: list[str] = Field(default_factory=list)


class ParsedProfile(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: Address = Field(default_factory=Address)
    nationality: str | None = None
    is_eu_eea: bool | None = None
    university: str | None = None
    program: str | None = None
    degree_level: str | None = None
    current_semester: int | None = None
    enrollment_valid_until: date | None = None
    expected_graduation: date | None = None
    skills: list[ParsedSkill] = Field(default_factory=list)
    languages: list[ParsedLanguage] = Field(default_factory=list)
    work_history: list[WorkItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    highlights_from_references: list[str] = Field(default_factory=list)


def _build_user_message(sections: dict[str, str]) -> str:
    parts = []
    for label, text in sections.items():
        text = (text or "").strip()
        if text:
            parts.append(f"=== {label.upper()} ===\n{text}")
    return "\n\n".join(parts) if parts else "(no document text available)"


def parse_profile(
    sections: dict[str, str],
    *,
    client: LlmClient | None = None,
    run_id: int | None = None,
) -> tuple[ParsedProfile, LlmResult]:
    """`sections` maps a document label ('cv', 'transcript', …) to its text."""
    client = client or LlmClient()
    return client.complete_json(
        purpose=LlmPurpose.PROFILE_PARSE,
        system=load_prompt("profile_parser"),
        user=_build_user_message(sections),
        schema=ParsedProfile,
        tier="smart",
        max_tokens=4096,
        run_id=run_id,
    )
