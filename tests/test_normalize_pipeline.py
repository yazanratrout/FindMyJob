import pytest
from sqlmodel import Session, select

from findmyjob.db import get_engine
from findmyjob.models.config import Company
from findmyjob.models.enums import CompanyOrigin
from findmyjob.models.job import Job
from findmyjob.pipelines.normalize import NormalizePipeline
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.services.companies import add_company

pytestmark = [pytest.mark.usefixtures("seeded_session"), pytest.mark.slow]


def _job(
    db: Session, *, company: str, title: str = "Werkstudent Data", location: str | None = None
):
    job = Job(
        source_key="test",
        source_job_id=f"{company}-{title}",
        url="https://x.test/1",
        title=title,
        normalized_title="",
        company_name_raw=company,
        location_raw=location,
    )
    db.add(job)
    db.flush()
    return job.id


async def test_links_known_company_and_creates_discovered(db_session: Session):
    add_company(db_session, {"name": "Acme Analytics GmbH"})
    known_id = _job(db_session, company="Acme Analytics")
    unknown_id = _job(db_session, company="Totally New Startup")
    blank_id = _job(db_session, company="")
    db_session.commit()

    await Orchestrator([NormalizePipeline()]).execute()

    with Session(get_engine()) as s:
        known = s.get(Job, known_id)
        assert known.company_id is not None
        assert s.get(Company, known.company_id).origin != CompanyOrigin.DISCOVERED

        unknown = s.get(Job, unknown_id)
        discovered = s.get(Company, unknown.company_id)
        assert discovered.origin == CompanyOrigin.DISCOVERED
        assert discovered.is_active is False

        assert s.get(Job, blank_id).company_id is None


async def test_sets_normalized_title_and_remote_flag(db_session: Session):
    job_id = _job(
        db_session,
        company="X",
        title="Werkstudent (m/w/d) Data",
        location="Remote, Germany",
    )
    db_session.commit()
    await Orchestrator([NormalizePipeline()]).execute()
    with Session(get_engine()) as s:
        job = s.get(Job, job_id)
        assert job.normalized_title == "werkstudent data"
        assert job.is_remote is True


async def test_is_idempotent(db_session: Session):
    _job(db_session, company="Acme")
    db_session.commit()
    await Orchestrator([NormalizePipeline()]).execute()
    await Orchestrator([NormalizePipeline()]).execute()
    with Session(get_engine()) as s:
        acme_rows = s.exec(select(Company).where(Company.normalized_name == "acme")).all()
        assert len(acme_rows) == 1
