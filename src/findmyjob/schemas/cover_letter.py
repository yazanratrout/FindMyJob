from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from findmyjob.models.application import CoverLetter


class CoverLetterRead(BaseModel):
    id: int
    job_id: int
    version: int
    language: str
    tone: str
    content: dict[str, Any]
    claims_used: list[dict[str, Any]]
    user_edited: bool
    has_docx: bool
    created_at: datetime

    @classmethod
    def of(cls, row: CoverLetter) -> CoverLetterRead:
        assert row.id is not None
        return cls(
            id=row.id,
            job_id=row.job_id,
            version=row.version,
            language=row.language,
            tone=row.tone,
            content=row.content,
            claims_used=row.claims_used,
            user_edited=row.user_edited,
            has_docx=bool(row.docx_path),
            created_at=row.created_at,
        )


class CoverLetterUpdate(BaseModel):
    content: dict[str, Any]


class RegenerateRequest(BaseModel):
    instruction: str | None = None
