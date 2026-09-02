from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from findmyjob.models.digest import Digest
from findmyjob.models.run import Run


class DigestRead(BaseModel):
    id: int
    run_id: int
    run_status: str
    seen: bool
    created_at: datetime
    summary: dict[str, Any]
    items: list[dict[str, Any]]
    warnings: list[str]

    @classmethod
    def of(cls, row: Digest, run: Run) -> DigestRead:
        assert row.id is not None
        return cls(
            id=row.id,
            run_id=row.run_id,
            run_status=(run.status.value if hasattr(run.status, "value") else str(run.status)),
            seen=row.seen,
            created_at=row.created_at,
            summary=row.summary,
            items=row.items,
            warnings=row.warnings,
        )
