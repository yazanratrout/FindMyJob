"""Helpers for the per-run `JobScore` row and the profile facts scoring needs."""

from __future__ import annotations

from sqlmodel import Session, col, select

from findmyjob.models.config import Company
from findmyjob.models.enums import CompanyOrigin, SkillCategory
from findmyjob.models.job import JobScore
from findmyjob.models.profile import ProfileSkill
from findmyjob.services.profile import get_profile


def get_run_score(session: Session, job_id: int, run_id: int) -> JobScore | None:
    return session.exec(
        select(JobScore).where(col(JobScore.job_id) == job_id, col(JobScore.run_id) == run_id)
    ).first()


def upsert_run_score(session: Session, job_id: int, run_id: int) -> JobScore:
    score = get_run_score(session, job_id, run_id)
    if score is None:
        score = JobScore(job_id=job_id, run_id=run_id)
        session.add(score)
        session.flush()
    return score


def profile_skill_names(session: Session) -> list[str]:
    profile = get_profile(session)
    rows = session.exec(
        select(ProfileSkill).where(
            col(ProfileSkill.profile_id) == profile.id,
            col(ProfileSkill.category) != SkillCategory.LANGUAGE,
        )
    ).all()
    return [r.name for r in rows]


def profile_language_levels(session: Session) -> dict[str, str]:
    """``{"german": "B2", "english": "C1"}`` from the profile's language skills."""
    profile = get_profile(session)
    rows = session.exec(
        select(ProfileSkill).where(
            col(ProfileSkill.profile_id) == profile.id,
            col(ProfileSkill.category) == SkillCategory.LANGUAGE,
        )
    ).all()
    levels: dict[str, str] = {}
    for row in rows:
        level = row.evidence.replace("CEFR", "").strip().upper() or "B1"
        levels[row.name.lower()] = level
    return levels


def company_affinity(session: Session, company_id: int | None) -> float:
    if company_id is None:
        return 0.5
    company = session.get(Company, company_id)
    if company is None:
        return 0.5
    if company.is_favorite:
        return 1.0
    if company.origin in (CompanyOrigin.SEED, CompanyOrigin.USER) and company.is_active:
        return 0.8
    return 0.5
