"""Public ATS job-board connectors (no scraping, documented endpoints only)."""

from findmyjob.sources.ats.ashby import AshbySource
from findmyjob.sources.ats.greenhouse import GreenhouseSource
from findmyjob.sources.ats.lever import LeverSource
from findmyjob.sources.ats.personio import PersonioSource
from findmyjob.sources.ats.smartrecruiters import SmartRecruitersSource

ATS_SOURCE_CLASSES = (
    GreenhouseSource,
    LeverSource,
    PersonioSource,
    SmartRecruitersSource,
    AshbySource,
)

__all__ = [
    "ATS_SOURCE_CLASSES",
    "AshbySource",
    "GreenhouseSource",
    "LeverSource",
    "PersonioSource",
    "SmartRecruitersSource",
]
