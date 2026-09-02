"""Programmatic access to Alembic migrations."""

from __future__ import annotations

from alembic import command
from alembic.config import Config

from findmyjob.config import REPO_ROOT, get_settings


def alembic_config() -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    return cfg


def upgrade_to_head() -> None:
    command.upgrade(alembic_config(), "head")
