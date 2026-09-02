"""CRUD for lecture-period terms (used by the eligibility module + 20h check)."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, col, select

from findmyjob.models.config import SemesterTerm
from findmyjob.services.profile import get_profile


def list_terms(session: Session) -> list[SemesterTerm]:
    return list(session.exec(select(SemesterTerm).order_by(col(SemesterTerm.lecture_start))).all())


def add_term(
    session: Session, *, label: str, lecture_start: date, lecture_end: date
) -> SemesterTerm:
    if lecture_end < lecture_start:
        raise ValueError("lecture_end must not be before lecture_start")
    profile = get_profile(session)
    term = SemesterTerm(
        profile_id=profile.id,
        label=label,
        lecture_start=lecture_start,
        lecture_end=lecture_end,
    )
    session.add(term)
    session.flush()
    return term


def delete_term(session: Session, term_id: int) -> bool:
    term = session.get(SemesterTerm, term_id)
    if term is None:
        return False
    session.delete(term)
    return True


def is_in_lecture_period(session: Session, day: date) -> bool:
    return any(t.lecture_start <= day <= t.lecture_end for t in list_terms(session))
