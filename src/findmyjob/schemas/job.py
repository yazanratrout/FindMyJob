from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from findmyjob.models.enums import Decision
from findmyjob.models.job import JobAnalysis
from findmyjob.services.job_read import JobRow


def _format_salary(analysis: JobAnalysis | None, fallback: str | None) -> str | None:
    if not analysis or not analysis.salary_min:
        return fallback
    hi = analysis.salary_max or analysis.salary_min
    currency = analysis.salary_currency or "EUR"
    period = f"/{analysis.salary_period}" if analysis.salary_period else ""
    return f"{analysis.salary_min:.0f}-{hi:.0f} {currency}{period}"


class JobCard(BaseModel):
    id: int
    title: str
    company: str
    location: str | None
    is_remote: bool
    source: str
    url: str
    apply_url: str | None
    posted_at: datetime | None
    is_new: bool

    final_score: float
    soft_score: float
    llm_holistic: float | None
    decision: Decision
    strengths: list[str]
    missing: list[str]

    weekly_hours: int | None
    salary: str | None
    contract_type: str | None

    @classmethod
    def of(cls, row: JobRow) -> JobCard:
        job, score, analysis = row.job, row.score, row.analysis
        assert job.id is not None
        company = row.company.name if row.company else job.company_name_raw
        salary = _format_salary(analysis, job.salary_raw)
        return cls(
            id=job.id,
            title=job.title,
            company=company or "unknown",
            location=job.location_raw,
            is_remote=job.is_remote,
            source=job.source_key,
            url=job.url,
            apply_url=job.apply_url,
            posted_at=job.posted_at,
            is_new=row.is_new,
            final_score=score.final_score,
            soft_score=score.soft_score,
            llm_holistic=score.llm_holistic,
            decision=score.decision,
            strengths=score.strengths_to_highlight[:3],
            missing=score.missing_qualifications[:3],
            weekly_hours=analysis.weekly_hours if analysis else None,
            salary=salary,
            contract_type=(
                analysis.contract_type.value
                if analysis and hasattr(analysis.contract_type, "value")
                else None
            ),
        )


class JobList(BaseModel):
    jobs: list[JobCard]
    counts: dict[str, int]


class ScoreComponent(BaseModel):
    raw: float
    weight: float
    contribution: float


class DocumentNeed(BaseModel):
    doc_type: str
    necessity: str
    reason: str
    have: bool


class JobDetail(JobCard):
    jd_text: str | None
    company_url: str | None
    hard_pass: bool
    hard_failures: list[str]
    rationale: str
    soft_breakdown: dict[str, ScoreComponent]
    documents_needed: list[DocumentNeed]
    analysis: dict[str, Any] | None
    application_id: int | None = None
    application_status: str | None = None

    @classmethod
    def of_detail(cls, row: JobRow, application: Any = None) -> JobDetail:
        base = JobCard.of(row).model_dump()
        score = row.score
        return cls(
            **base,
            jd_text=row.job.jd_text,
            company_url=row.company.careers_url if row.company else None,
            hard_pass=score.hard_pass,
            hard_failures=score.hard_failures,
            rationale=score.llm_rationale,
            soft_breakdown={k: ScoreComponent(**v) for k, v in score.soft_breakdown.items()},
            documents_needed=[DocumentNeed(**d) for d in score.documents_needed],
            analysis=row.analysis.raw_json if row.analysis else None,
            application_id=application.id if application is not None else None,
            application_status=(application.status.value if application is not None else None),
        )
