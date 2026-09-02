"""Shared test fixtures.

An isolated temp data dir + SQLite file is configured *before* any application
module is imported, so tests never touch the developer's real database.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

_TMP_DIR = Path(tempfile.mkdtemp(prefix="findmyjob-tests-"))
os.environ["APP_ENV"] = "test"
os.environ["APP_DATA_DIR"] = str(_TMP_DIR)
os.environ["APP_DATABASE_URL"] = f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}"
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key")

import pytest  # noqa: E402
from sqlmodel import Session  # noqa: E402

from findmyjob.config import reset_settings_cache  # noqa: E402
from findmyjob.db import create_all, drop_all, get_engine, reset_engine_cache  # noqa: E402
from findmyjob.services.bootstrap import seed  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_database() -> Iterator[None]:
    """Give every test a clean, empty schema."""
    reset_settings_cache()
    reset_engine_cache()
    drop_all()
    create_all()
    yield
    reset_engine_cache()


@pytest.fixture
def db_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


@pytest.fixture
def seeded_session(db_session: Session) -> Session:
    seed(db_session)
    db_session.commit()
    return db_session


@pytest.fixture
def client() -> Iterator[object]:
    from fastapi.testclient import TestClient

    from findmyjob.api.app import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
