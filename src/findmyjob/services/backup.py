"""Nightly SQLite backup via the online-backup API."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from findmyjob.config import get_settings
from findmyjob.db import get_engine
from findmyjob.logging import get_logger

log = get_logger("backup")

_PREFIX = "findmyjob-"


def backup(*, keep: int = 14, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    settings = get_settings()
    if not settings.database_url.startswith("sqlite:///"):
        raise RuntimeError("backup only supports a local SQLite database")

    settings.backups_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.backups_dir / f"{_PREFIX}{now:%Y%m%d-%H%M%S}.db"

    raw = get_engine().raw_connection()
    try:
        source: sqlite3.Connection = raw.driver_connection  # type: ignore[assignment]
        with sqlite3.connect(dest) as target:
            source.backup(target)
    finally:
        raw.close()

    existing = sorted(settings.backups_dir.glob(f"{_PREFIX}*.db"))
    if keep > 0:
        for old in existing[:-keep]:
            old.unlink(missing_ok=True)

    log.info("backup.done", path=str(dest), kept=min(len(existing), keep or len(existing)))
    return dest


def list_backups() -> list[Path]:
    return sorted(get_settings().backups_dir.glob(f"{_PREFIX}*.db"), reverse=True)
