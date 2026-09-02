"""Database engine, session management and schema helpers.

The app is single-user and local, so a synchronous SQLite connection is more
than sufficient. Pipelines are ``async`` for network concurrency but their
database access is synchronous and short-lived.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy.engine import create_engine
from sqlmodel import Session, SQLModel

# Import side effect: register every table on ``SQLModel.metadata``.
from findmyjob import models as _models  # noqa: F401  (re-exported for metadata)
from findmyjob.config import get_settings


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    """Enforce foreign keys and use a write-ahead log on every SQLite connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    settings.ensure_dirs()
    is_sqlite = settings.database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    return create_engine(settings.database_url, connect_args=connect_args, echo=False)


def reset_engine_cache() -> None:
    """Dispose and forget the cached engine (used by tests)."""
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()


def create_all() -> None:
    """Create any missing tables directly from the models (used by tests / bootstrap)."""
    SQLModel.metadata.create_all(get_engine())


def drop_all() -> None:
    """Drop every table. Disables FK enforcement first so order doesn't matter."""
    engine = get_engine()
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        SQLModel.metadata.drop_all(conn)
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session: commit on success, roll back on exception."""
    session = Session(get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session (no implicit commit)."""
    with Session(get_engine()) as session:
        yield session
