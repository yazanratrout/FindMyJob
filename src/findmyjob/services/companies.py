"""Company registry: CRUD, ATS detection, and the ref list for connectors."""

from __future__ import annotations

import re
from typing import Any

import httpx
from sqlmodel import Session, col, select

from findmyjob.logging import get_logger
from findmyjob.models.config import Company
from findmyjob.models.enums import AtsType, CompanyOrigin
from findmyjob.normalize import normalize_company_name
from findmyjob.sources.base import CompanyRef

log = get_logger("companies")


class CompanyError(ValueError):
    """Invalid company input."""


def list_companies(session: Session, *, active_only: bool = False) -> list[Company]:
    stmt = select(Company).order_by(col(Company.name))
    if active_only:
        stmt = stmt.where(col(Company.is_active))
    return list(session.exec(stmt).all())


def company_refs(session: Session) -> list[CompanyRef]:
    """Active companies that a connector could actually query."""
    refs: list[CompanyRef] = []
    for c in list_companies(session, active_only=True):
        if c.ats_type != AtsType.NONE and not c.ats_slug:
            continue
        if c.ats_type == AtsType.NONE and not c.careers_url:
            continue
        refs.append(
            CompanyRef(
                id=c.id,
                name=c.name,
                ats_type=c.ats_type.value,
                ats_slug=c.ats_slug,
                careers_url=c.careers_url,
                city=c.city,
            )
        )
    return refs


def add_company(session: Session, data: dict[str, Any]) -> Company:
    name = (data.get("name") or "").strip()
    if not name:
        raise CompanyError("name is required")
    key = normalize_company_name(name)
    if session.exec(select(Company).where(col(Company.normalized_name) == key)).first():
        raise CompanyError(f"company '{name}' already exists")
    try:
        ats_type = AtsType(data.get("ats_type", "none"))
    except ValueError as exc:
        raise CompanyError(f"invalid ats_type: {data.get('ats_type')}") from exc
    company = Company(
        name=name,
        normalized_name=key,
        ats_type=ats_type,
        ats_slug=data.get("ats_slug"),
        careers_url=data.get("careers_url"),
        city=data.get("city"),
        is_favorite=bool(data.get("is_favorite", False)),
        is_active=bool(data.get("is_active", True)),
        origin=CompanyOrigin.USER,
    )
    session.add(company)
    session.flush()
    return company


def update_company(session: Session, company_id: int, patch: dict[str, Any]) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise CompanyError("company not found")
    for field in ("name", "ats_slug", "careers_url", "city", "is_favorite", "is_active"):
        if field in patch:
            setattr(company, field, patch[field])
    if "ats_type" in patch:
        try:
            company.ats_type = AtsType(patch["ats_type"])
        except ValueError as exc:
            raise CompanyError(f"invalid ats_type: {patch['ats_type']}") from exc
    if "name" in patch:
        company.normalized_name = normalize_company_name(company.name)
    session.add(company)
    session.flush()
    return company


def delete_company(session: Session, company_id: int) -> bool:
    company = session.get(Company, company_id)
    if company is None:
        return False
    session.delete(company)
    return True


_ATS_URL_PATTERNS: list[tuple[AtsType, re.Pattern[str]]] = [
    (
        AtsType.GREENHOUSE,
        re.compile(r"(?:job-)?boards\.greenhouse\.io/(?:embed/job_board\?for=)?([\w-]+)"),
    ),
    (AtsType.LEVER, re.compile(r"jobs\.lever\.co/([\w-]+)")),
    (AtsType.PERSONIO, re.compile(r"([\w-]+)\.jobs\.personio\.(?:de|com)")),
    (AtsType.ASHBY, re.compile(r"jobs\.ashbyhq\.com/([\w-]+)")),
    (AtsType.SMARTRECRUITERS, re.compile(r"careers\.smartrecruiters\.com/([\w-]+)")),
]


async def detect_ats(url: str, *, fetch_text: Any = None) -> dict[str, str | None]:
    """Guess ``ats_type`` + ``ats_slug`` from a careers URL (and, if needed, its HTML)."""
    for ats_type, pattern in _ATS_URL_PATTERNS:
        match = pattern.search(url)
        if match:
            return {"ats_type": ats_type.value, "ats_slug": match.group(1)}

    if fetch_text is not None:
        try:
            html_text = await fetch_text(url)
        except Exception:
            html_text = ""
        for ats_type, pattern in _ATS_URL_PATTERNS:
            match = pattern.search(html_text)
            if match:
                return {"ats_type": ats_type.value, "ats_slug": match.group(1)}

    return {"ats_type": AtsType.NONE.value, "ats_slug": None}


async def default_fetch_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "FindMyJob/0.1"})
        resp.raise_for_status()
        return resp.text
