"""Shared model building blocks."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Timezone-naive UTC timestamp (SQLite stores no tz info)."""
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin(SQLModel):
    """Adds ``created_at`` / ``updated_at`` columns.

    Inherit *before* ``table=True`` models, e.g.::

        class Thing(TimestampMixin, table=True):
            ...
    """

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": utcnow},
    )


def json_column() -> dict:
    """Kwargs for a JSON-backed column with a sane server default."""
    from sqlalchemy import JSON, Column

    return {"sa_column": Column(JSON, nullable=False)}
