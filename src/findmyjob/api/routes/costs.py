"""LLM spend endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from findmyjob.db import get_session
from findmyjob.services.cost import month_to_date

router = APIRouter(tags=["costs"])


@router.get("/costs")
def get_costs(session: Session = Depends(get_session)) -> dict[str, Any]:
    return month_to_date(session)
