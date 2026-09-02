"""Eligibility gauge + non-EU working-day ledger."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from findmyjob.db import get_session
from findmyjob.schemas.eligibility import (
    EligibilityEntryCreate,
    EligibilityEntryRead,
    EligibilityGauge,
)
from findmyjob.services.eligibility import (
    EligibilityError,
    add_entry,
    delete_entry,
    gauge,
    list_entries,
)

router = APIRouter(prefix="/eligibility", tags=["eligibility"])


@router.get("", response_model=EligibilityGauge)
def get_gauge(session: Session = Depends(get_session)) -> EligibilityGauge:
    return EligibilityGauge(**gauge(session))


@router.get("/entries", response_model=list[EligibilityEntryRead])
def get_entries(session: Session = Depends(get_session)) -> list[EligibilityEntryRead]:
    return [EligibilityEntryRead.of(e) for e in list_entries(session)]


@router.post("/entries", response_model=EligibilityEntryRead, status_code=201)
def create_entry(
    body: EligibilityEntryCreate, session: Session = Depends(get_session)
) -> EligibilityEntryRead:
    try:
        entry = add_entry(
            session,
            period_start=body.period_start,
            period_end=body.period_end,
            day_type=body.day_type,
            note=body.note,
        )
    except EligibilityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return EligibilityEntryRead.of(entry)


@router.delete("/entries/{entry_id}", status_code=204)
def remove_entry(entry_id: int, session: Session = Depends(get_session)) -> None:
    if not delete_entry(session, entry_id):
        raise HTTPException(status_code=404, detail="entry not found")
    session.commit()
