from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from findmyjob.config import Settings
from findmyjob.services.http import HttpClient
from findmyjob.sources.ats import (
    AshbySource,
    GreenhouseSource,
    LeverSource,
    PersonioSource,
    SmartRecruitersSource,
)
from findmyjob.sources.base import CompanyRef, SourceQuery
from findmyjob.sources.jsonld import JsonLdSource, extract_job_postings

RECENT_ISO = (datetime.now(UTC) - timedelta(days=2)).isoformat()
RECENT_MS = int((datetime.now(UTC) - timedelta(days=2)).timestamp() * 1000)

QUERY = SourceQuery(
    keywords=["Werkstudent", "Data"],
    city="München",
    job_types=["werkstudent"],
    max_age_days=30,
    limit_per_source=50,
)


@pytest.fixture
def http() -> HttpClient:
    return HttpClient(min_interval_s=0.0, retry_max_wait_s=0.0)


def _company(ats_type: str, slug: str | None = None, url: str | None = None) -> CompanyRef:
    return CompanyRef(id=1, name="Celonis", ats_type=ats_type, ats_slug=slug, careers_url=url)


@respx.mock
async def test_greenhouse(http: HttpClient):
    respx.get("https://boards-api.greenhouse.io/v1/boards/celonis/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 1,
                        "title": "Werkstudent Data Science (m/w/d)",
                        "absolute_url": "https://boards.greenhouse.io/celonis/jobs/1",
                        "location": {"name": "Munich, Germany"},
                        "updated_at": RECENT_ISO,
                        "content": "&lt;p&gt;SQL, Python&lt;/p&gt;",
                    },
                    {
                        "id": 2,
                        "title": "Senior Sales Director",
                        "absolute_url": "x",
                        "location": {"name": "Munich"},
                        "updated_at": RECENT_ISO,
                        "content": "sales",
                    },
                ]
            },
        )
    )
    jobs = await GreenhouseSource(Settings(), http, [_company("greenhouse", "celonis")]).fetch(
        QUERY
    )
    assert [j.source_job_id for j in jobs] == ["celonis:1"]
    assert jobs[0].description_text == "SQL, Python"
    await http.aclose()


@respx.mock
async def test_lever(http: HttpClient):
    respx.get("https://api.lever.co/v0/postings/flixbus").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "abc",
                    "text": "Working Student Analytics",
                    "hostedUrl": "https://jobs.lever.co/flixbus/abc",
                    "applyUrl": "https://jobs.lever.co/flixbus/abc/apply",
                    "categories": {"location": "Munich", "commitment": "Part-time"},
                    "createdAt": RECENT_MS,
                    "descriptionPlain": "Work with data.",
                }
            ],
        )
    )
    jobs = await LeverSource(Settings(), http, [_company("lever", "flixbus")]).fetch(QUERY)
    assert jobs[0].source_job_id == "flixbus:abc"
    assert jobs[0].apply_url.endswith("/apply")
    await http.aclose()


@respx.mock
async def test_personio_xml(http: HttpClient):
    xml = f"""<?xml version="1.0"?>
    <workzag-jobs>
      <position>
        <id>555</id>
        <name>Werkstudent Data Engineering (m/w/d)</name>
        <office>Munich</office>
        <employmentType>part-time</employmentType>
        <createdAt>{RECENT_ISO}</createdAt>
        <jobDescriptions>
          <jobDescription><name>Role</name><value>pipelines with Python</value></jobDescription>
        </jobDescriptions>
      </position>
    </workzag-jobs>"""
    respx.get("https://inovex.jobs.personio.de/xml").mock(
        return_value=httpx.Response(200, text=xml)
    )
    jobs = await PersonioSource(Settings(), http, [_company("personio", "inovex")]).fetch(QUERY)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "inovex:555"
    assert jobs[0].url == "https://inovex.jobs.personio.de/job/555"
    assert "pipelines" in (jobs[0].description_text or "")
    await http.aclose()


@respx.mock
async def test_ashby(http: HttpClient):
    respx.get("https://api.ashbyhq.com/posting-api/job-board/scalablecapital").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": "j1",
                        "title": "Werkstudent Data",
                        "location": "Munich",
                        "isRemote": False,
                        "publishedAt": RECENT_ISO,
                        "jobUrl": "https://jobs.ashbyhq.com/scalablecapital/j1",
                        "descriptionPlain": "SQL and dashboards.",
                    }
                ]
            },
        )
    )
    jobs = await AshbySource(Settings(), http, [_company("ashby", "scalablecapital")]).fetch(QUERY)
    assert jobs[0].source_job_id == "scalablecapital:j1"
    await http.aclose()


@respx.mock
async def test_smartrecruiters(http: HttpClient):
    respx.get("https://api.smartrecruiters.com/v1/companies/acme/postings").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [
                    {
                        "id": "p1",
                        "name": "Werkstudent Data Analytics",
                        "ref": "https://careers.smartrecruiters.com/acme/p1",
                        "releasedDate": RECENT_ISO,
                        "location": {"city": "München", "country": "de"},
                    }
                ]
            },
        )
    )
    jobs = await SmartRecruitersSource(
        Settings(), http, [_company("smartrecruiters", "acme")]
    ).fetch(QUERY)
    assert jobs[0].source_job_id == "acme:p1"
    assert "München" in (jobs[0].location or "")
    await http.aclose()


def test_ats_source_unconfigured_without_matching_companies():
    http = HttpClient(min_interval_s=0.0)
    src = GreenhouseSource(Settings(), http, [_company("lever", "x")])
    assert src.is_configured() is False


def test_extract_job_postings_handles_graph_and_list():
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[
      {"@type":"WebPage"},
      {"@type":"JobPosting","title":"Werkstudent Data","datePosted":"2026-08-20",
       "hiringOrganization":{"name":"Acme"},
       "jobLocation":{"address":{"addressLocality":"München"}},
       "url":"https://acme.test/jobs/1","description":"<p>Python</p>"}
    ]}
    </script>
    """
    postings = extract_job_postings(html)
    assert len(postings) == 1
    assert postings[0]["title"] == "Werkstudent Data"


@respx.mock
async def test_jsonld_source_respects_robots(http: HttpClient):
    respx.get("https://acme.test/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /careers")
    )
    company = _company("none", url="https://acme.test/careers")
    src = JsonLdSource(Settings(), http, [company])
    jobs = await src.fetch(QUERY)
    assert jobs == []  # blocked by robots
    await http.aclose()


@respx.mock
async def test_jsonld_source_extracts_when_allowed(http: HttpClient):
    respx.get("https://acme.test/robots.txt").mock(return_value=httpx.Response(404))
    respx.get("https://acme.test/careers").mock(
        return_value=httpx.Response(
            200,
            text=f"""<html><head>
            <script type="application/ld+json">
            {{"@type":"JobPosting","title":"Werkstudent Data Science",
              "datePosted":"{RECENT_ISO}","hiringOrganization":{{"name":"Acme"}},
              "jobLocation":{{"address":{{"addressLocality":"München"}}}},
              "url":"https://acme.test/jobs/9","description":"<p>SQL, Python</p>"}}
            </script></head><body></body></html>""",
        )
    )
    src = JsonLdSource(Settings(), http, [_company("none", url="https://acme.test/careers")])
    jobs = await src.fetch(QUERY)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "https://acme.test/jobs/9"
    assert jobs[0].company_name == "Acme"
    await http.aclose()
