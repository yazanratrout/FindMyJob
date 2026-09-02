"""Score-weight calibration from user feedback + tracker outcomes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from findmyjob.db import get_session
from findmyjob.schemas.calibration import CalibrationReportRead
from findmyjob.services.calibration import apply_report, build_report

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.get("", response_model=CalibrationReportRead)
def get_calibration(session: Session = Depends(get_session)) -> CalibrationReportRead:
    return CalibrationReportRead.of(build_report(session))


@router.post("/apply", response_model=CalibrationReportRead)
def apply_calibration(session: Session = Depends(get_session)) -> CalibrationReportRead:
    try:
        apply_report(session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return CalibrationReportRead.of(build_report(session))
