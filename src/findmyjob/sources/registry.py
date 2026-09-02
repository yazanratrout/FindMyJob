"""Build the set of active job sources from settings + credentials + companies."""

from __future__ import annotations

from findmyjob.config import Settings
from findmyjob.logging import get_logger
from findmyjob.models.config import AppSettings
from findmyjob.services.http import HttpClient
from findmyjob.sources.api import (
    AdzunaSource,
    ArbeitnowSource,
    BundesagenturSource,
    TheMuseSource,
)
from findmyjob.sources.ats import ATS_SOURCE_CLASSES
from findmyjob.sources.base import CompanyRef, JobSource, SourceQuery
from findmyjob.sources.jsonld import JsonLdSource

log = get_logger("sources")

# Sources that only need process settings + http.
_SIMPLE_SOURCE_CLASSES: tuple[type[JobSource], ...] = (
    BundesagenturSource,
    AdzunaSource,
    ArbeitnowSource,
    TheMuseSource,
)


def build_sources(
    process_settings: Settings,
    app_settings: AppSettings,
    http: HttpClient,
    companies: list[CompanyRef] | None = None,
) -> list[JobSource]:
    """Instantiate every source that is enabled and configured."""
    companies = companies or []
    active: list[JobSource] = []

    def _add(source: JobSource) -> None:
        if not app_settings.sources_enabled.get(source.key, True):
            return
        if not source.is_configured():
            log.info("sources.skip_unconfigured", source=source.key)
            return
        active.append(source)

    for cls in _SIMPLE_SOURCE_CLASSES:
        _add(cls(process_settings, http))
    for cls in (*ATS_SOURCE_CLASSES, JsonLdSource):
        _add(cls(process_settings, http, companies))

    return active


def build_source_query(app_settings: AppSettings) -> SourceQuery:
    keywords = list(
        dict.fromkeys([*app_settings.target_titles, *app_settings.keywords_allow])
    ) or list(app_settings.target_fields)
    return SourceQuery(
        keywords=keywords,
        city=app_settings.target_city,
        lat=app_settings.target_lat,
        lon=app_settings.target_lon,
        radius_km=app_settings.radius_km,
        allow_remote=app_settings.allow_remote,
        max_age_days=app_settings.recency_days,
        job_types=list(app_settings.job_types),
        limit_per_source=150,
    )
