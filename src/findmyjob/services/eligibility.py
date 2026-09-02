"""Optional eligibility module: Werkstudent rules + the non-EU working-day ledger.

Guidance only — the app shows a disclaimer. Behind
``AppSettings.eligibility_module_enabled``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlmodel import Session, col, select

from findmyjob.models.eligibility import EligibilityEntry
from findmyjob.models.job import Job, JobAnalysis
from findmyjob.services.profile import get_profile
from findmyjob.services.semester import is_in_lecture_period
from findmyjob.services.settings import get_app_settings

#: Non-EU/EEA students: 140 full days (or 280 half days) per calendar year.
ANNUAL_FULL_DAYS = 140
#: Below this many days of remaining enrolment, flag the role.
ENROLMENT_MIN_DAYS = 60
#: Werkstudent weekly-hours cap during the lecture period.
TERM_HOURS_CAP = 20


class EligibilityError(ValueError):
    """Invalid ledger entry."""


def _span_days(start: date, end: date) -> int:
    return (end - start).days + 1


def _entry_weight(entry: EligibilityEntry, year: int) -> float:
    y0, y1 = date(year, 1, 1), date(year, 12, 31)
    start, end = max(entry.period_start, y0), min(entry.period_end, y1)
    if start > end:
        return 0.0
    factor = 0.5 if entry.day_type == "half" else 1.0
    return _span_days(start, end) * factor


def days_used(session: Session, *, year: int | None = None) -> float:
    year = year or date.today().year
    profile = get_profile(session)
    entries = session.exec(
        select(EligibilityEntry).where(col(EligibilityEntry.profile_id) == profile.id)
    ).all()
    return round(sum(_entry_weight(e, year) for e in entries), 1)


def gauge(session: Session) -> dict[str, Any]:
    settings = get_app_settings(session)
    profile = get_profile(session)
    used = days_used(session)
    return {
        "enabled": settings.eligibility_module_enabled,
        "applies": not profile.is_eu_eea,
        "year": date.today().year,
        "days_used": used,
        "limit_full_days": ANNUAL_FULL_DAYS,
        "remaining": round(max(0.0, ANNUAL_FULL_DAYS - used), 1),
    }


def list_entries(session: Session) -> list[EligibilityEntry]:
    profile = get_profile(session)
    return list(
        session.exec(
            select(EligibilityEntry)
            .where(col(EligibilityEntry.profile_id) == profile.id)
            .order_by(col(EligibilityEntry.period_start).desc())
        ).all()
    )


def add_entry(
    session: Session,
    *,
    period_start: date,
    period_end: date,
    day_type: str = "full",
    job_id: int | None = None,
    note: str = "",
) -> EligibilityEntry:
    if period_end < period_start:
        raise EligibilityError("period_end must not be before period_start")
    if day_type not in ("full", "half"):
        raise EligibilityError("day_type must be 'full' or 'half'")
    profile = get_profile(session)
    entry = EligibilityEntry(
        profile_id=profile.id,
        period_start=period_start,
        period_end=period_end,
        day_type=day_type,
        day_count=_span_days(period_start, period_end),
        job_id=job_id,
        note=note,
    )
    session.add(entry)
    session.flush()
    return entry


def delete_entry(session: Session, entry_id: int) -> bool:
    entry = session.get(EligibilityEntry, entry_id)
    if entry is None:
        return False
    session.delete(entry)
    return True


def _contract(analysis: JobAnalysis) -> str:
    value = analysis.contract_type
    return value.value if hasattr(value, "value") else str(value)


def disqualifiers(
    session: Session,
    job: Job,
    analysis: JobAnalysis | None,
    *,
    today: date | None = None,
) -> list[str]:
    """Eligibility-based hard failures (only when the module is enabled)."""
    settings = get_app_settings(session)
    if not settings.eligibility_module_enabled:
        return []

    profile = get_profile(session)
    today = today or date.today()
    out: list[str] = []

    if not profile.is_eu_eea and days_used(session) >= ANNUAL_FULL_DAYS:
        out.append("eligibility:non_eu_days_exhausted")

    horizon = profile.enrollment_valid_until or profile.expected_graduation
    if horizon is not None and horizon <= today + timedelta(days=ENROLMENT_MIN_DAYS):
        out.append("eligibility:enrolment_ending")

    if (
        analysis is not None
        and _contract(analysis) == "werkstudent"
        and analysis.weekly_hours is not None
        and analysis.weekly_hours > TERM_HOURS_CAP
        and (not analysis.start_date_text or is_in_lecture_period(session, today))
    ):
        out.append("eligibility:over_20h_in_term")

    return out
