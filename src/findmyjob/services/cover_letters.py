"""Generate / edit / render tailored cover letters."""

from __future__ import annotations

import re
from typing import Literal

from sqlmodel import Session, col, func, select

from findmyjob.config import get_settings
from findmyjob.llm.client import LlmClient
from findmyjob.llm.cover_letter import CoverLetterResult, generate_cover_letter
from findmyjob.logging import get_logger
from findmyjob.models.application import Application, CoverLetter
from findmyjob.models.config import Company
from findmyjob.models.enums import ApplicationStatus, CoverLetterLanguageMode
from findmyjob.models.job import Job, JobAnalysis
from findmyjob.models.profile import Profile
from findmyjob.services.analyze import current_analysis
from findmyjob.services.profile import get_profile, profile_summary_text
from findmyjob.services.settings import get_app_settings

log = get_logger("cover_letters")


class CoverLetterError(ValueError):
    """Invalid request for a cover letter."""


def _safe(name: str) -> str:
    return re.sub(r"[^\w \-]", "", name).strip() or "Company"


def _resolve_language(
    mode: CoverLetterLanguageMode, analysis: JobAnalysis | None
) -> Literal["de", "en"]:
    if mode == CoverLetterLanguageMode.ALWAYS_DE:
        return "de"
    if mode == CoverLetterLanguageMode.ALWAYS_EN:
        return "en"
    return "en" if analysis is not None and analysis.english_only else "de"


def _sender(profile: Profile) -> dict[str, str]:
    return {
        "name": profile.full_name or "",
        "street": profile.street,
        "postal_code": profile.postal_code,
        "city": profile.city,
        "email": profile.email,
        "phone": profile.phone,
    }


def _company_name(session: Session, job: Job) -> str:
    if job.company_id is not None:
        company = session.get(Company, job.company_id)
        if company is not None:
            return company.name
    return job.company_name_raw or "the company"


def _next_version(session: Session, job_id: int) -> int:
    current = session.exec(
        select(func.max(col(CoverLetter.version))).where(col(CoverLetter.job_id) == job_id)
    ).one()
    return int(current or 0) + 1


def list_for_job(session: Session, job_id: int) -> list[CoverLetter]:
    return list(
        session.exec(
            select(CoverLetter)
            .where(col(CoverLetter.job_id) == job_id)
            .order_by(col(CoverLetter.version).desc())
        ).all()
    )


def get(session: Session, cover_letter_id: int) -> CoverLetter | None:
    return session.get(CoverLetter, cover_letter_id)


def _render(session: Session, cover_letter: CoverLetter) -> None:
    from findmyjob.docx.render import render_cover_letter

    profile = get_profile(session)
    content = CoverLetterResult.model_validate(cover_letter.content)
    company = _safe(content.recipient.company)
    out = (
        get_settings().letters_dir
        / str(cover_letter.job_id)
        / f"Cover letter {company} v{cover_letter.version}.docx"
    )
    render_cover_letter(content, _sender(profile), out)
    cover_letter.docx_path = str(out)
    session.add(cover_letter)
    session.flush()


def _mark_preparing(session: Session, job_id: int) -> None:
    app = session.exec(select(Application).where(col(Application.job_id) == job_id)).first()
    if app is None:
        session.add(Application(job_id=job_id, status=ApplicationStatus.PREPARING))
    elif app.status == ApplicationStatus.INTERESTED:
        app.status = ApplicationStatus.PREPARING
        session.add(app)


def generate(
    session: Session,
    job_id: int,
    *,
    instruction: str | None = None,
    client: LlmClient | None = None,
    run_id: int | None = None,
) -> CoverLetter:
    job = session.get(Job, job_id)
    if job is None:
        raise CoverLetterError("job not found")

    analysis = current_analysis(session, job_id)
    settings = get_app_settings(session)
    profile = get_profile(session)
    company = _company_name(session, job)
    language = _resolve_language(settings.cover_letter_language_mode, analysis)

    result, _llm = generate_cover_letter(
        profile_summary=profile_summary_text(session),
        voice_sample=profile.voice_sample_text,
        analysis=analysis.raw_json if analysis else {},
        jd_text=job.jd_text or job.title,
        company_name=company,
        language=language,
        tone=settings.cover_letter_tone,
        instruction=instruction,
        client=client,
        run_id=run_id,
    )
    if not result.recipient.company:
        result.recipient.company = company

    cover_letter = CoverLetter(
        job_id=job_id,
        version=_next_version(session, job_id),
        language=result.language,
        tone=settings.cover_letter_tone,
        content=result.model_dump(mode="json"),
        claims_used=[c.model_dump() for c in result.claims_used],
    )
    session.add(cover_letter)
    session.flush()
    _render(session, cover_letter)
    _mark_preparing(session, job_id)
    log.info("cover_letters.generated", job_id=job_id, version=cover_letter.version)
    return cover_letter


def update(session: Session, cover_letter_id: int, content: dict) -> CoverLetter:
    cover_letter = session.get(CoverLetter, cover_letter_id)
    if cover_letter is None:
        raise CoverLetterError("cover letter not found")
    # Validate the shape before storing.
    CoverLetterResult.model_validate(content)
    cover_letter.content = content
    cover_letter.user_edited = True
    session.add(cover_letter)
    session.flush()
    _render(session, cover_letter)
    return cover_letter


def regenerate(
    session: Session,
    cover_letter_id: int,
    instruction: str | None,
    *,
    client: LlmClient | None = None,
) -> CoverLetter:
    cover_letter = session.get(CoverLetter, cover_letter_id)
    if cover_letter is None:
        raise CoverLetterError("cover letter not found")
    return generate(session, cover_letter.job_id, instruction=instruction, client=client)
