"""Local single-user authentication."""

from __future__ import annotations

from sqlmodel import Field

from findmyjob.models.base import TimestampMixin


class AppAuth(TimestampMixin, table=True):
    """One row holding the Argon2 hash of the app passphrase."""

    __tablename__ = "app_auth"

    id: int | None = Field(default=None, primary_key=True)
    passphrase_hash: str
