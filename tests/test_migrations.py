"""Guard: the Alembic migrations must fully describe the SQLModel schema."""

from __future__ import annotations

import pytest
from alembic import command
from alembic.util.exc import CommandError

from findmyjob.config import reset_settings_cache
from findmyjob.db import reset_engine_cache


def test_head_migration_matches_models(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{(tmp_path / 'head.db').as_posix()}")
    reset_settings_cache()
    reset_engine_cache()

    from findmyjob.db_migrate import alembic_config

    command.upgrade(alembic_config(), "head")
    try:
        command.check(alembic_config())
    except CommandError as exc:  # pragma: no cover - failure path
        pytest.fail(f"Models drifted from migrations — run `just db-revision`:\n{exc}")
