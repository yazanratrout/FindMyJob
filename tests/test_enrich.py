import httpx
import pytest
import respx
from sqlmodel import Session, select

from findmyjob.db import get_engine
from findmyjob.models.enums import JobLifecycle, PipelineStatus
from findmyjob.models.job import Job
from findmyjob.models.run import PipelineRun
from findmyjob.pipelines.enrich import EnrichPipeline
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.services.http import HttpClient

pytestmark = [pytest.mark.usefixtures("seeded_session"), pytest.mark.slow]

_LONG_DESC = "Build data pipelines with Python and SQL. " * 20


def _fast_http() -> HttpClient:
    return HttpClient(min_interval_s=0.0, retry_max_wait_s=0.0)


def _thin_job(db: Session, url: str, jd_text: str | None = None) -> int:
    job = Job(
        source_key="test",
        source_job_id=url,
        url=url,
        title="Werkstudent Data",
        normalized_title="werkstudent data",
        jd_text=jd_text,
    )
    db.add(job)
    db.flush()
    return job.id


@respx.mock
async def test_enriches_from_page_content(db_session: Session):
    url = "https://jobs.test/1"
    job_id = _thin_job(db_session, url, jd_text="short")
    db_session.commit()

    respx.get("https://jobs.test/robots.txt").mock(return_value=httpx.Response(404))
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text=f"""<html><body><article><h1>Werkstudent Data</h1>
            <p>{_LONG_DESC}</p></article>
            <script type="application/ld+json">
            {{"@type":"JobPosting","title":"Werkstudent Data","description":"{_LONG_DESC}"}}
            </script></body></html>""",
        )
    )

    await Orchestrator([EnrichPipeline(_fast_http)]).execute()
    with Session(get_engine()) as s:
        job = s.get(Job, job_id)
        assert job.jd_text and len(job.jd_text) > 400
        assert job.jd_content_hash


@respx.mock
async def test_merges_jsonld_date_and_salary(db_session: Session):
    url = "https://jobs.test/2"
    job_id = _thin_job(db_session, url, jd_text="short")
    db_session.commit()

    respx.get("https://jobs.test/robots.txt").mock(return_value=httpx.Response(404))
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text=f"""<html><body><article><p>{_LONG_DESC}</p></article>
            <script type="application/ld+json">
            {{"@type":"JobPosting","title":"Werkstudent Data",
              "description":"{_LONG_DESC}",
              "datePosted":"2026-08-15",
              "baseSalary":{{"@type":"MonetaryAmount","currency":"EUR",
                "value":{{"@type":"QuantitativeValue","minValue":16,"maxValue":18,
                          "unitText":"HOUR"}}}}}}
            </script></body></html>""",
        )
    )

    await Orchestrator([EnrichPipeline(_fast_http)]).execute()
    with Session(get_engine()) as s:
        job = s.get(Job, job_id)
        assert job.posted_at is not None and job.posted_at.year == 2026
        assert job.salary_raw and "16" in job.salary_raw


@respx.mock
async def test_dead_link_marks_job_dead(db_session: Session):
    url = "https://gone.test/9"
    job_id = _thin_job(db_session, url)
    db_session.commit()
    respx.get("https://gone.test/robots.txt").mock(return_value=httpx.Response(404))
    respx.get(url).mock(return_value=httpx.Response(404))

    await Orchestrator([EnrichPipeline(_fast_http)]).execute()
    with Session(get_engine()) as s:
        assert s.get(Job, job_id).lifecycle == JobLifecycle.DEAD


@respx.mock
async def test_robots_disallow_skips(db_session: Session):
    url = "https://blocked.test/careers/1"
    job_id = _thin_job(db_session, url, jd_text="tiny")
    db_session.commit()
    respx.get("https://blocked.test/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /careers")
    )

    await Orchestrator([EnrichPipeline(_fast_http)]).execute()
    with Session(get_engine()) as s:
        assert s.get(Job, job_id).jd_text == "tiny"  # untouched
        pr = s.exec(select(PipelineRun)).one()
        assert pr.stats.get("robots_blocked") == 1
        assert pr.status in (PipelineStatus.OK, PipelineStatus.PARTIAL)


async def test_no_targets_completes_clean(db_session: Session):
    _thin_job(db_session, "https://ok.test/1", jd_text="x" * 500)  # already thick
    db_session.commit()
    await Orchestrator([EnrichPipeline(_fast_http)]).execute()
    with Session(get_engine()) as s:
        pr = s.exec(select(PipelineRun)).one()
        assert pr.stats == {}
