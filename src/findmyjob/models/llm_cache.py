"""Content-addressed cache of LLM responses.

Keyed by a hash of (purpose, model, system, user). Lets identical prompts —
e.g. the same job description analyzed twice — cost nothing the second time.
"""

from __future__ import annotations

from sqlmodel import Field

from findmyjob.models.base import TimestampMixin


class LlmCacheEntry(TimestampMixin, table=True):
    __tablename__ = "llm_cache_entry"

    key: str = Field(primary_key=True)
    purpose: str
    model: str
    response_text: str
    input_tokens: int = 0
    output_tokens: int = 0
