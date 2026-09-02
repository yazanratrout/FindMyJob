"""Job postings and everything derived from them: embeddings, analysis, scores."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Column, LargeBinary, UniqueConstraint
from sqlmodel import Field

from findmyjob.models.base import TimestampMixin, utcnow
from findmyjob.models.enums import ContractType, Decision, JobLifecycle


class Job(TimestampMixin, table=True):
    __tablename__ = "job"
    __table_args__ = (UniqueConstraint("source_key", "source_job_id", name="uq_job_source"),)

    id: int | None = Field(default=None, primary_key=True)
    # Null == this row is the canonical posting; otherwise it points at one.
    canonical_job_id: int | None = Field(default=None, foreign_key="job.id", index=True)

    source_key: str = Field(index=True)
    source_job_id: str
    url: str
    apply_url: str | None = None

    title: str
    normalized_title: str = Field(index=True)
    company_id: int | None = Field(default=None, foreign_key="company.id", index=True)
    company_name_raw: str = ""

    location_raw: str | None = None
    is_remote: bool = False
    posted_at: datetime | None = None

    first_seen_run_id: int | None = Field(default=None, foreign_key="run.id")
    last_seen_at: datetime = Field(default_factory=utcnow)
    lifecycle: JobLifecycle = JobLifecycle.ACTIVE

    raw_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    jd_text: str | None = None
    jd_content_hash: str | None = Field(default=None, index=True)
    salary_raw: str | None = None


class JobEmbedding(TimestampMixin, table=True):
    __tablename__ = "job_embedding"

    job_id: int = Field(foreign_key="job.id", primary_key=True)
    model_version: str
    dim: int
    vector: bytes = Field(sa_column=Column(LargeBinary, nullable=False))


class JobAnalysis(TimestampMixin, table=True):
    __tablename__ = "job_analysis"
    __table_args__ = (
        UniqueConstraint("job_id", "analyzer_version", name="uq_analysis_job_version"),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    analyzer_version: str

    must_haves: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    nice_haves: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    languages: list[dict] = Field(default_factory=list, sa_column=Column(JSON))

    weekly_hours: int | None = None
    weekly_hours_basis: str = "unknown"  # stated | inferred | unknown
    contract_type: ContractType = ContractType.UNKNOWN

    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None  # hour | month | year

    start_date_text: str | None = None
    deadline: date | None = None

    enrollment_required: str = "unknown"  # yes | no | unknown
    english_only: bool = False
    application_method: str = "unknown"  # ats_form | email | external | unknown
    documents_requested: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    seniority: str = "unknown"
    location_resolved: dict = Field(default_factory=dict, sa_column=Column(JSON))
    red_flags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source_snippets: dict = Field(default_factory=dict, sa_column=Column(JSON))

    raw_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    parse_failed: bool = False


class JobScore(TimestampMixin, table=True):
    __tablename__ = "job_score"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    run_id: int = Field(foreign_key="run.id", index=True)

    hard_pass: bool = True
    hard_failures: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    soft_score: float = 0.0
    soft_breakdown: dict = Field(default_factory=dict, sa_column=Column(JSON))

    llm_holistic: float | None = None
    llm_rationale: str = ""
    missing_qualifications: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    strengths_to_highlight: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    final_score: float = 0.0
    decision: Decision = Decision.ARCHIVED
    documents_needed: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
