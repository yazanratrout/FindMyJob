"""Persist LLM job analyses, skipping anything already analyzed at this version."""

from __future__ import annotations

from sqlmodel import Session, col, select

from findmyjob.llm.analyzer import ANALYZER_VERSION, JobAnalysisResult, analyze_posting
from findmyjob.llm.client import LlmClient, LlmResult
from findmyjob.logging import get_logger
from findmyjob.models.config import Company
from findmyjob.models.enums import ContractType
from findmyjob.models.job import Job, JobAnalysis

log = get_logger("analyze")

_MIN_TEXT = 80


def _contract_type(value: str) -> ContractType:
    try:
        return ContractType(value)
    except ValueError:
        return ContractType.UNKNOWN


def current_analysis(session: Session, job_id: int) -> JobAnalysis | None:
    return session.exec(
        select(JobAnalysis).where(
            col(JobAnalysis.job_id) == job_id,
            col(JobAnalysis.analyzer_version) == ANALYZER_VERSION,
        )
    ).first()


def persist_analysis(
    session: Session, job_id: int, result: JobAnalysisResult, *, parse_failed: bool = False
) -> JobAnalysis:
    existing = current_analysis(session, job_id)
    row = existing or JobAnalysis(job_id=job_id, analyzer_version=ANALYZER_VERSION)
    row.must_haves = result.must_haves
    row.nice_haves = result.nice_haves
    row.skills = [s.model_dump() for s in result.skills]
    row.languages = [lang.model_dump() for lang in result.languages]
    row.weekly_hours = result.weekly_hours
    row.weekly_hours_basis = result.weekly_hours_basis
    row.contract_type = _contract_type(result.contract_type)
    row.salary_min = result.salary_min
    row.salary_max = result.salary_max
    row.salary_currency = result.salary_currency
    row.salary_period = result.salary_period
    row.start_date_text = result.start_date_text
    row.deadline = result.deadline
    row.enrollment_required = result.enrollment_required
    row.english_only = result.english_only
    row.application_method = result.application_method
    row.documents_requested = result.documents_requested
    row.seniority = result.seniority
    row.red_flags = result.red_flags
    row.source_snippets = result.source_snippets
    row.raw_json = result.model_dump(mode="json")
    row.parse_failed = parse_failed
    session.add(row)
    session.flush()
    return row


def analyze_job(
    session: Session,
    job: Job,
    *,
    city: str,
    client: LlmClient | None = None,
    run_id: int | None = None,
) -> tuple[JobAnalysis | None, LlmResult | None]:
    """Analyze one job unless it's already done or has too little text.

    Returns ``(analysis, llm_result)``; ``llm_result`` is ``None`` on cache/skip.
    """
    assert job.id is not None
    existing = current_analysis(session, job.id)
    if existing is not None:
        return existing, None
    if not job.jd_text or len(job.jd_text.strip()) < _MIN_TEXT:
        return None, None

    company_name = job.company_name_raw
    if job.company_id is not None:
        company = session.get(Company, job.company_id)
        if company is not None:
            company_name = company.name

    result, llm = analyze_posting(
        title=job.title,
        company=company_name,
        city=city,
        jd_text=job.jd_text,
        client=client,
        run_id=run_id,
    )
    analysis = persist_analysis(session, job.id, result)
    return analysis, llm
