"""LLM spend tracking and the monthly budget guard.

The monthly ceiling is ``Settings.llm_monthly_budget_eur`` (from the
environment). Pipelines that call the model check :func:`budget_ok` before each
batch and stop cleanly when the month-to-date cost would exceed it.
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from findmyjob.config import Settings, get_settings
from findmyjob.models.run import LlmCall, Run


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _calls_this_month(session: Session, now: datetime) -> list[LlmCall]:
    return list(
        session.exec(select(LlmCall).where(col(LlmCall.created_at) >= _month_start(now))).all()
    )


def current_month_cost_eur(session: Session, *, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC).replace(tzinfo=None)
    return round(sum(c.cost_eur for c in _calls_this_month(session, now)), 4)


def remaining_budget_eur(
    session: Session, settings: Settings | None = None, *, now: datetime | None = None
) -> float:
    settings = settings or get_settings()
    return round(settings.llm_monthly_budget_eur - current_month_cost_eur(session, now=now), 4)


def budget_ok(
    session: Session, settings: Settings | None = None, *, now: datetime | None = None
) -> bool:
    return remaining_budget_eur(session, settings, now=now) > 0.0


def mark_budget_exhausted(session: Session, run_id: int) -> None:
    run = session.get(Run, run_id)
    if run is not None and not run.budget_exhausted:
        run.budget_exhausted = True
        session.add(run)


def month_to_date(session: Session, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC).replace(tzinfo=None)
    settings = get_settings()
    calls = _calls_this_month(session, now)

    per_purpose: dict[str, dict[str, float]] = {}
    for call in calls:
        bucket = per_purpose.setdefault(
            call.purpose.value,
            {"calls": 0.0, "cost_eur": 0.0, "input_tokens": 0.0, "output_tokens": 0.0},
        )
        bucket["calls"] += 1
        bucket["cost_eur"] += call.cost_eur
        bucket["input_tokens"] += call.input_tokens
        bucket["output_tokens"] += call.output_tokens

    total = round(sum(c.cost_eur for c in calls), 4)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    day_fraction = (now.day - 1 + now.hour / 24) / days_in_month or (1 / days_in_month)
    projection = round(total / day_fraction, 2) if day_fraction else total

    return {
        "month": now.strftime("%Y-%m"),
        "cost_eur": total,
        "budget_eur": settings.llm_monthly_budget_eur,
        "remaining_eur": round(settings.llm_monthly_budget_eur - total, 4),
        "projected_month_end_eur": projection,
        "calls": len(calls),
        "cache_hits": sum(1 for c in calls if c.cache_hit),
        "per_purpose": {
            k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in per_purpose.items()
        },
    }
