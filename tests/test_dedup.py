import numpy as np
import pytest
from sqlmodel import Session, select

from findmyjob.db import get_engine
from findmyjob.models.job import Job, JobEmbedding
from findmyjob.pipelines.dedup import DedupPipeline, canonical_key
from findmyjob.pipelines.orchestrator import Orchestrator

pytestmark = [pytest.mark.usefixtures("seeded_session"), pytest.mark.slow]


class FakeEmbedder:
    dim = 4
    model_version = "fake-v1"

    def __init__(self, mapping: dict[str, list[float]]):
        self._mapping = mapping
        self.calls = 0

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls += len(texts)
        rows = []
        for text in texts:
            vec = [1.0, 0.0, 0.0, 0.0]
            for key, v in self._mapping.items():
                if key in text:
                    vec = v
            rows.append(vec)
        return np.asarray(rows, dtype=np.float32)


def _job(db: Session, *, sid: str, company: str, title: str, jd: str = "desc") -> int:
    job = Job(
        source_key=sid.split(":")[0],
        source_job_id=sid,
        url=f"https://x.test/{sid}",
        title=title,
        normalized_title="",
        company_name_raw=company,
        jd_text=jd,
    )
    db.add(job)
    db.flush()
    return job.id


def test_canonical_key_ignores_gender_marker_and_suffix():
    a = canonical_key("Celonis SE", "Werkstudent (m/w/d) Data")
    b = canonical_key("Celonis", "Werkstudent Data")
    assert a == b


async def test_canonical_key_links_cross_source_duplicates(db_session: Session):
    keep = _job(db_session, sid="ba:1", company="Acme", title="Werkstudent Data (m/w/d)")
    dupe = _job(db_session, sid="adzuna:9", company="Acme", title="Werkstudent Data")
    other = _job(db_session, sid="ba:2", company="Acme", title="Werkstudent Marketing")
    db_session.commit()

    await Orchestrator([DedupPipeline(embedder=None)]).execute()

    with Session(get_engine()) as s:
        assert s.get(Job, dupe).canonical_job_id == keep
        assert s.get(Job, keep).canonical_job_id is None
        assert s.get(Job, other).canonical_job_id is None


def test_titles_compatible_guards_same_company_boilerplate():
    from findmyjob.pipelines.dedup import titles_compatible

    # the case the semantic tier exists for: same role, different wording/language
    assert titles_compatible("Werkstudent Analytics", "Working Student Analytics")
    assert titles_compatible("Werkstudent Data (m/w/d)", "Werkstudent Data Science")
    # different roles at one employer share boilerplate but not a subject
    assert not titles_compatible("Account Executive - Federal", "Enterprise AI Consultant")
    assert not titles_compatible("Lead Value Engineer", "Cloud Economics Specialist")


async def test_semantic_does_not_merge_different_roles(db_session: Session):
    """Same company, near-identical boilerplate, but genuinely different jobs."""
    a = _job(db_session, sid="s1:1", company="Acme", title="Account Executive Federal", jd="AAA")
    b = _job(db_session, sid="s2:1", company="Acme", title="Enterprise AI Consultant", jd="AAA")
    db_session.commit()

    embedder = FakeEmbedder({"AAA": [1.0, 0.0, 0.0, 0.0]})  # identical vectors
    await Orchestrator([DedupPipeline(embedder=embedder)]).execute()

    with Session(get_engine()) as s:
        assert s.get(Job, b).canonical_job_id is None  # kept apart by the title guard
        assert s.get(Job, a).canonical_job_id is None


async def test_semantic_links_near_identical_postings(db_session: Session):
    a = _job(db_session, sid="s1:1", company="Beta", title="Werkstudent Analytics", jd="AAA")
    b = _job(db_session, sid="s2:1", company="Beta", title="Working Student Analytics", jd="BBB")
    c = _job(db_session, sid="s3:1", company="Beta", title="Werkstudent Backend", jd="CCC")
    db_session.commit()

    embedder = FakeEmbedder(
        {
            "AAA": [1.0, 0.0, 0.0, 0.0],
            "BBB": [0.99, 0.01, 0.0, 0.0],  # ~identical to AAA
            "CCC": [0.0, 1.0, 0.0, 0.0],  # orthogonal
        }
    )
    await Orchestrator([DedupPipeline(embedder=embedder)]).execute()

    with Session(get_engine()) as s:
        assert s.get(Job, b).canonical_job_id == a
        assert s.get(Job, c).canonical_job_id is None
        assert len(s.exec(select(JobEmbedding)).all()) == 3


async def test_embeddings_are_reused_on_second_run(db_session: Session):
    _job(db_session, sid="s1:1", company="Beta", title="Werkstudent A", jd="AAA")
    _job(db_session, sid="s2:1", company="Beta", title="Werkstudent B", jd="CCC")
    db_session.commit()

    embedder = FakeEmbedder({"AAA": [1.0, 0, 0, 0], "CCC": [0, 1.0, 0, 0]})
    await Orchestrator([DedupPipeline(embedder=embedder)]).execute()
    assert embedder.calls == 2
    await Orchestrator([DedupPipeline(embedder=embedder)]).execute()
    assert embedder.calls == 2  # nothing re-embedded


async def test_semantic_skipped_without_model(db_session: Session):
    _job(db_session, sid="s1:1", company="Beta", title="Werkstudent A")
    db_session.commit()
    run_id = await Orchestrator([DedupPipeline(embedder=None)]).execute()
    with Session(get_engine()) as s:
        from findmyjob.models.run import PipelineRun

        pr = s.exec(select(PipelineRun).where(PipelineRun.run_id == run_id)).one()
        assert pr.stats.get("semantic_skipped") == 1
