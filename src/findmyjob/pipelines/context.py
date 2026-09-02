"""Runtime context handed to every pipeline during a run."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog
from sqlmodel import Session, col, select

from findmyjob.db import session_scope
from findmyjob.models.base import utcnow
from findmyjob.models.config import AppSettings
from findmyjob.models.enums import RunTrigger


@dataclass(slots=True)
class PipelineContext:
    """Everything a pipeline needs, and nothing it shouldn't reach for."""

    run_id: int
    trigger: RunTrigger
    app_settings: AppSettings
    logger: structlog.stdlib.BoundLogger
    started_at: datetime = field(default_factory=utcnow)
    #: Lightweight scratch space for hand-offs the DB shouldn't carry.
    state: dict[str, Any] = field(default_factory=dict)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """A transactional session (commit on success, rollback on error)."""
        with session_scope() as session:
            yield session

    def bind(self, **kwargs: Any) -> structlog.stdlib.BoundLogger:
        return self.logger.bind(**kwargs)


def load_app_settings(session: Session) -> AppSettings:
    """Load the singleton settings row, detached so it can outlive the session."""
    settings = session.exec(select(AppSettings).order_by(col(AppSettings.id))).first()
    if settings is None:
        raise RuntimeError(
            "No AppSettings row found. Run `findmyjob db seed` before running the pipeline."
        )
    session.expunge(settings)
    return settings
