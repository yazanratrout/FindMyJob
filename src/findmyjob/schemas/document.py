from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from findmyjob.models.enums import DocumentType, ParseStatus
from findmyjob.models.profile import Document


class DocumentRead(BaseModel):
    id: int
    type: DocumentType
    filename: str
    mime: str
    size_bytes: int
    parse_status: ParseStatus
    parse_error: str | None
    text_chars: int
    uploaded_at: datetime

    @classmethod
    def of(cls, doc: Document) -> DocumentRead:
        assert doc.id is not None
        return cls(
            id=doc.id,
            type=doc.type,
            filename=doc.filename,
            mime=doc.mime,
            size_bytes=doc.size_bytes,
            parse_status=doc.parse_status,
            parse_error=doc.parse_error,
            text_chars=len(doc.extracted_text or ""),
            uploaded_at=doc.uploaded_at,
        )
