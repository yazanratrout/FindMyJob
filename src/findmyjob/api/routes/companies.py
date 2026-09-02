"""Company registry endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from findmyjob.db import get_session
from findmyjob.schemas.company import (
    AtsDetectRequest,
    AtsDetectResult,
    CompanyCreate,
    CompanyRead,
    CompanyUpdate,
    company_read,
)
from findmyjob.services.companies import (
    CompanyError,
    add_company,
    default_fetch_text,
    delete_company,
    detect_ats,
    list_companies,
    update_company,
)

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyRead])
def get_companies(
    active_only: bool = False, session: Session = Depends(get_session)
) -> list[CompanyRead]:
    return [company_read(c) for c in list_companies(session, active_only=active_only)]


@router.post("", response_model=CompanyRead, status_code=201)
def create_company(body: CompanyCreate, session: Session = Depends(get_session)) -> CompanyRead:
    try:
        company = add_company(session, body.model_dump())
    except CompanyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return company_read(company)


@router.put("/{company_id}", response_model=CompanyRead)
def edit_company(
    company_id: int, body: CompanyUpdate, session: Session = Depends(get_session)
) -> CompanyRead:
    try:
        company = update_company(session, company_id, body.model_dump(exclude_unset=True))
    except CompanyError as exc:
        status = 404 if "not found" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    session.commit()
    return company_read(company)


@router.delete("/{company_id}", status_code=204)
def remove_company(company_id: int, session: Session = Depends(get_session)) -> None:
    if not delete_company(session, company_id):
        raise HTTPException(status_code=404, detail="company not found")
    session.commit()


@router.post("/detect", response_model=AtsDetectResult)
async def detect_company_ats(body: AtsDetectRequest) -> AtsDetectResult:
    result = await detect_ats(body.careers_url, fetch_text=default_fetch_text)
    return AtsDetectResult(**result)
