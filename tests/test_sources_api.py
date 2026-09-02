from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from findmyjob.config import Settings
from findmyjob.services.http import HttpClient
from findmyjob.sources.api import (
    AdzunaSource,
    ArbeitnowSource,
    BundesagenturSource,
    TheMuseSource,
)
from findmyjob.sources.base import SourceQuery

RECENT_TS = int((datetime.now(UTC) - timedelta(days=3)).timestamp())
RECENT_ISO = (datetime.now(UTC) - timedelta(days=3)).isoformat()

QUERY = SourceQuery(
    keywords=["Werkstudent Data"],
    city="München",
    radius_km=30,
    max_age_days=30,
    job_types=["werkstudent"],
    limit_per_source=50,
)


@pytest.fixture
def http() -> HttpClient:
    return HttpClient(min_interval_s=0.0, retry_max_wait_s=0.0)


def _settings(**over) -> Settings:
    return Settings(**over)


@respx.mock
async def test_bundesagentur_maps_results(http: HttpClient):
    respx.get("https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "stellenangebote": [
                    {
                        "refnr": "10000-123",
                        "titel": "Werkstudent Data Science (m/w/d)",
                        "arbeitgeber": "Celonis SE",
                        "arbeitsort": {"ort": "München", "land": "Deutschland"},
                        "aktuelleVeroeffentlichungsdatum": RECENT_ISO,
                        "externeUrl": "https://celonis.com/jobs/123",
                    }
                ]
            },
        )
    )
    jobs = await BundesagenturSource(_settings(), http).fetch(QUERY)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_key == "ba"
    assert job.source_job_id == "10000-123"
    assert job.company_name == "Celonis SE"
    assert job.url == "https://celonis.com/jobs/123"
    assert job.posted_at is not None
    await http.aclose()


@respx.mock
async def test_adzuna_requires_and_uses_credentials(http: HttpClient):
    unconfigured = AdzunaSource(_settings(), http)
    assert unconfigured.is_configured() is False

    configured = AdzunaSource(_settings(ADZUNA_APP_ID="id", ADZUNA_APP_KEY="key"), http)
    assert configured.is_configured() is True

    respx.get("https://api.adzuna.com/v1/api/jobs/de/search/1").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "555",
                        "title": "Working Student Analytics",
                        "company": {"display_name": "Acme GmbH"},
                        "location": {"display_name": "München, Bayern"},
                        "created": RECENT_ISO,
                        "redirect_url": "https://adzuna.test/555",
                        "description": "SQL, Python, dbt. 20h/week.",
                        "salary_min": 20000,
                        "salary_max": 24000,
                    }
                ]
            },
        )
    )
    respx.get("https://api.adzuna.com/v1/api/jobs/de/search/2").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    jobs = await configured.fetch(QUERY)
    assert [j.source_job_id for j in jobs] == ["555"]
    assert jobs[0].salary_raw and "EUR/year" in jobs[0].salary_raw
    await http.aclose()


@respx.mock
async def test_arbeitnow_filters_by_keyword_and_city(http: HttpClient):
    respx.get("https://www.arbeitnow.com/api/job-board-api").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "slug": "wd-1",
                        "title": "Werkstudent Data Engineering",
                        "company_name": "DataCo",
                        "location": "München",
                        "remote": False,
                        "url": "https://arbeitnow.test/wd-1",
                        "description": "<p>Build pipelines with Python.</p>",
                        "tags": ["data"],
                        "created_at": RECENT_TS,
                    },
                    {
                        "slug": "sales-2",
                        "title": "Sales Manager",
                        "company_name": "SellCo",
                        "location": "Hamburg",
                        "remote": False,
                        "url": "https://arbeitnow.test/sales-2",
                        "description": "<p>Close deals.</p>",
                        "tags": ["sales"],
                        "created_at": RECENT_TS,
                    },
                ]
            },
        )
    )
    jobs = await ArbeitnowSource(_settings(), http).fetch(QUERY)
    assert [j.source_job_id for j in jobs] == ["wd-1"]
    assert jobs[0].description_text == "Build pipelines with Python."
    await http.aclose()


@respx.mock
async def test_themuse_maps_and_filters(http: HttpClient):
    respx.get("https://www.themuse.com/api/public/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "page_count": 1,
                "results": [
                    {
                        "id": 42,
                        "name": "Werkstudent Data Analytics",
                        "company": {"name": "MuseCo"},
                        "locations": [{"name": "Munich, Germany"}],
                        "publication_date": RECENT_ISO,
                        "refs": {"landing_page": "https://muse.test/42"},
                        "contents": "<p>Data with SQL.</p>",
                        "levels": [{"name": "Internship"}],
                    }
                ],
            },
        )
    )
    jobs = await TheMuseSource(_settings(), http).fetch(QUERY)
    assert len(jobs) == 1
    assert jobs[0].company_name == "MuseCo"
    assert jobs[0].url == "https://muse.test/42"
    await http.aclose()
