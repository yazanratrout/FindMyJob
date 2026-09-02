"""User-tunable configuration stored in the database.

Everything here is edited through the web UI (onboarding wizard / Settings) and
persisted between sessions. There is exactly one :class:`AppSettings` row.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Column
from sqlmodel import Field

from findmyjob.models.base import TimestampMixin
from findmyjob.models.enums import AtsType, CompanyOrigin, CoverLetterLanguageMode

DEFAULT_SCORE_WEIGHTS: dict[str, float] = {
    "skills_match": 30,
    "field_relevance": 20,
    "language_fit": 15,
    "hours_fit": 10,
    "seniority_fit": 8,
    "recency": 7,
    "salary_fit": 5,
    "company_affinity": 5,
}

DEFAULT_SOURCES_ENABLED: dict[str, bool] = {
    "ba": True,
    "adzuna": True,
    "arbeitnow": True,
    "themuse": True,
    "greenhouse": True,
    "lever": True,
    "personio": True,
    "smartrecruiters": True,
    "ashby": True,
    "jsonld": True,
}


class AppSettings(TimestampMixin, table=True):
    __tablename__ = "app_settings"

    id: int | None = Field(default=None, primary_key=True)

    # ---- Where & what -------------------------------------------------
    target_city: str = "München"
    target_lat: float | None = None
    target_lon: float | None = None
    radius_km: int = 30
    allow_remote: bool = True
    target_fields: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    target_titles: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    keywords_allow: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    keywords_block: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    job_types: list[str] = Field(
        default_factory=lambda: ["werkstudent", "student_assistant"],
        sa_column=Column(JSON),
    )

    # ---- Limits ------------------------------------------------------
    recency_days: int = 30
    language_max_cefr: str = "B2"
    language_hard: bool = False
    hours_max: int = 20
    hours_hard: bool = True
    contract_types: list[str] = Field(
        default_factory=lambda: ["werkstudent", "part_time"],
        sa_column=Column(JSON),
    )
    contract_type_hard: bool = False

    # ---- Scoring ----------------------------------------------------
    score_threshold_recommend: int = 70
    score_threshold_maybe: int = 55
    weights: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_SCORE_WEIGHTS),
        sa_column=Column(JSON),
    )
    blend_soft_ratio: float = 0.6

    # ---- Schedule & alerts -----------------------------------------
    run_time: str = "10:00"
    run_timezone: str = "Europe/Berlin"
    notify_channels: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    notify_email: str | None = None
    notify_telegram_chat_id: str | None = None
    digest_top_n: int = 8

    # ---- Cover letters -------------------------------------------
    cover_letter_language_mode: CoverLetterLanguageMode = CoverLetterLanguageMode.MATCH_POSTING
    cover_letter_tone: str = "formal"  # formal | semi_formal

    # ---- Sources & modules --------------------------------------
    sources_enabled: dict[str, bool] = Field(
        default_factory=lambda: dict(DEFAULT_SOURCES_ENABLED),
        sa_column=Column(JSON),
    )
    eligibility_module_enabled: bool = False

    # ---- Housekeeping ------------------------------------------
    retention_days: int = 90
    repost_days: int = 21
    onboarding_completed: bool = False


class Company(TimestampMixin, table=True):
    __tablename__ = "company"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    normalized_name: str = Field(index=True)
    ats_type: AtsType = AtsType.NONE
    ats_slug: str | None = None
    careers_url: str | None = None
    city: str | None = None
    is_favorite: bool = False
    is_active: bool = True
    origin: CompanyOrigin = CompanyOrigin.SEED


class SemesterTerm(TimestampMixin, table=True):
    """Lecture periods, used by the eligibility module and the 20h/week check."""

    __tablename__ = "semester_term"

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    label: str
    lecture_start: date
    lecture_end: date
