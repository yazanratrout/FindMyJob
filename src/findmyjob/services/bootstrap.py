"""First-run bootstrap: ensure singleton rows exist and load the company seed."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from importlib import resources
from typing import Any

import yaml
from sqlmodel import Session, select

from findmyjob.db import create_all, drop_all
from findmyjob.logging import get_logger
from findmyjob.models.config import AppSettings, Company
from findmyjob.models.enums import AtsType, CompanyOrigin
from findmyjob.models.profile import Profile
from findmyjob.normalize import normalize_company_name

log = get_logger("bootstrap")


@dataclass(slots=True)
class SeedReport:
    settings_created: bool
    profile_created: bool
    companies_added: int
    companies_updated: int


def _load_company_seed() -> list[dict[str, Any]]:
    raw = resources.files("findmyjob.sources").joinpath("companies.yaml").read_text("utf-8")
    data = yaml.safe_load(raw) or []
    if not isinstance(data, list):
        raise ValueError("companies.yaml must contain a list")
    return data


def ensure_app_settings(session: Session) -> bool:
    if session.exec(select(AppSettings)).first() is not None:
        return False
    session.add(AppSettings())
    log.info("seed.app_settings_created")
    return True


def ensure_profile(session: Session) -> bool:
    if session.exec(select(Profile)).first() is not None:
        return False
    session.add(Profile())
    log.info("seed.profile_created")
    return True


def sync_companies(session: Session) -> tuple[int, int]:
    added = updated = 0
    existing = {c.normalized_name: c for c in session.exec(select(Company)).all()}
    for entry in _load_company_seed():
        name = entry["name"]
        key = normalize_company_name(name)
        ats_type = AtsType(entry.get("ats_type", "none"))
        current = existing.get(key)
        if current is None:
            session.add(
                Company(
                    name=name,
                    normalized_name=key,
                    ats_type=ats_type,
                    ats_slug=entry.get("ats_slug"),
                    careers_url=entry.get("careers_url"),
                    city=entry.get("city"),
                    origin=CompanyOrigin.SEED,
                )
            )
            added += 1
        elif current.origin == CompanyOrigin.SEED:
            # Refresh seed-managed companies; never clobber user edits.
            current.name = name
            current.ats_type = ats_type
            current.ats_slug = entry.get("ats_slug")
            current.careers_url = entry.get("careers_url")
            current.city = entry.get("city")
            session.add(current)
            updated += 1
    return added, updated


def seed(session: Session) -> SeedReport:
    """Idempotent: safe to run on every startup."""
    settings_created = ensure_app_settings(session)
    profile_created = ensure_profile(session)
    added, updated = sync_companies(session)
    report = SeedReport(settings_created, profile_created, added, updated)
    log.info(
        "seed.done",
        settings_created=settings_created,
        profile_created=profile_created,
        companies_added=added,
        companies_updated=updated,
    )
    return report


def reset_database(
    session_factory: Callable[[], AbstractContextManager[Session]],
) -> None:
    """Drop every table and recreate an empty, seeded schema. Destructive."""
    drop_all()
    create_all()
    with session_factory() as session:
        seed(session)
        session.commit()
    log.warning("database.reset")
