"""Profile access helpers (the installation has exactly one profile)."""

from __future__ import annotations

from sqlmodel import Session, col, select

from findmyjob.models.profile import Profile


def get_profile(session: Session) -> Profile:
    """Return the singleton profile, creating it if the DB was never seeded."""
    profile = session.exec(select(Profile).order_by(col(Profile.id))).first()
    if profile is None:
        profile = Profile()
        session.add(profile)
        session.flush()
    return profile
