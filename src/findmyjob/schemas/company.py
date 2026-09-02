from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from findmyjob.models.config import Company
from findmyjob.models.enums import AtsType, CompanyOrigin


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    ats_type: AtsType
    ats_slug: str | None
    careers_url: str | None
    city: str | None
    is_favorite: bool
    is_active: bool
    origin: CompanyOrigin


class CompanyCreate(BaseModel):
    name: str
    ats_type: AtsType = AtsType.NONE
    ats_slug: str | None = None
    careers_url: str | None = None
    city: str | None = None
    is_favorite: bool = False
    is_active: bool = True


class CompanyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    ats_type: AtsType | None = None
    ats_slug: str | None = None
    careers_url: str | None = None
    city: str | None = None
    is_favorite: bool | None = None
    is_active: bool | None = None


class AtsDetectRequest(BaseModel):
    careers_url: str


class AtsDetectResult(BaseModel):
    ats_type: str
    ats_slug: str | None


def company_read(row: Company) -> CompanyRead:
    return CompanyRead.model_validate(row)
