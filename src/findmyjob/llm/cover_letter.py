"""LLM generation of a tailored cover letter."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from findmyjob.llm.client import LlmClient, LlmResult
from findmyjob.llm.prompts import load_prompt
from findmyjob.models.enums import LlmPurpose

COVER_LETTER_VERSION = "2026-09-02.1"


class Recipient(BaseModel):
    company: str = ""
    name: str | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None


class ClaimUsed(BaseModel):
    claim: str
    evidence_from_profile: str


class CoverLetterResult(BaseModel):
    language: Literal["de", "en"] = "de"
    recipient: Recipient = Field(default_factory=Recipient)
    subject: str = ""
    salutation: str = ""
    paragraphs: list[str] = Field(default_factory=list)
    closing: str = ""
    claims_used: list[ClaimUsed] = Field(default_factory=list)


def generate_cover_letter(
    *,
    profile_summary: str,
    voice_sample: str,
    analysis: dict[str, Any],
    jd_text: str,
    company_name: str,
    language: Literal["de", "en"],
    tone: str,
    instruction: str | None = None,
    client: LlmClient | None = None,
    run_id: int | None = None,
) -> tuple[CoverLetterResult, LlmResult]:
    client = client or LlmClient()
    analysis_json = json.dumps(analysis, ensure_ascii=False, default=str)[:4000]
    sample = (voice_sample or "(none provided)")[:2500]
    user = (
        f"Language: {language}\nTone: {tone}\nCompany: {company_name}\n\n"
        f"=== STUDENT PROFILE ===\n{profile_summary}\n\n"
        f"=== WRITING SAMPLE (voice only) ===\n{sample}\n\n"
        f"=== POSTING ANALYSIS ===\n{analysis_json}\n\n"
        f"=== POSTING TEXT ===\n{jd_text.strip()[:6000]}"
    )
    if instruction:
        user += f"\n\n=== REVISION REQUEST ===\n{instruction}"

    system = load_prompt("cover_letter") + f"\n\n(version: {COVER_LETTER_VERSION})"
    # Instruction-driven regenerations must not be served from the cache.
    return client.complete_json(
        purpose=LlmPurpose.COVER_LETTER,
        system=system,
        user=user,
        schema=CoverLetterResult,
        tier="smart",
        max_tokens=2048,
        run_id=run_id,
        use_cache=instruction is None,
    )
