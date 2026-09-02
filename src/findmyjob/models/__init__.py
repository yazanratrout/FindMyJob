"""SQLModel table definitions.

Importing this package registers every table on ``SQLModel.metadata`` so that
``create_all`` and Alembic autogenerate see the full schema.
"""

from __future__ import annotations

from findmyjob.models.application import Application, CoverLetter
from findmyjob.models.auth import AppAuth
from findmyjob.models.config import (
    DEFAULT_SCORE_WEIGHTS,
    DEFAULT_SOURCES_ENABLED,
    AppSettings,
    Company,
    SemesterTerm,
)
from findmyjob.models.eligibility import EligibilityEntry
from findmyjob.models.job import Job, JobAnalysis, JobEmbedding, JobScore
from findmyjob.models.llm_cache import LlmCacheEntry
from findmyjob.models.profile import Document, Profile, ProfileSkill
from findmyjob.models.run import LlmCall, PipelineRun, Run

__all__ = [
    "DEFAULT_SCORE_WEIGHTS",
    "DEFAULT_SOURCES_ENABLED",
    "AppAuth",
    "AppSettings",
    "Application",
    "Company",
    "CoverLetter",
    "Document",
    "EligibilityEntry",
    "Job",
    "JobAnalysis",
    "JobEmbedding",
    "JobScore",
    "LlmCacheEntry",
    "LlmCall",
    "PipelineRun",
    "Profile",
    "ProfileSkill",
    "Run",
    "SemesterTerm",
]
