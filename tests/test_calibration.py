import argparse

import pytest
from sqlmodel import Session, select

from findmyjob.cli import cmd_calibrate
from findmyjob.models.application import Application
from findmyjob.models.config import DEFAULT_SCORE_WEIGHTS, AppSettings
from findmyjob.models.enums import ApplicationStatus, Decision
from findmyjob.models.feedback import JobFeedback
from findmyjob.models.job import Job, JobScore
from findmyjob.models.run import Run
from findmyjob.services.calibration import apply_report, build_report
from findmyjob.services.feedback import clear_feedback, set_feedback

pytestmark = pytest.mark.usefixtures("seeded_session")


def _breakdown(**raws: float) -> dict:
    return {
        comp: {"raw": raws.get(comp, 0.5), "weight": w, "contribution": raws.get(comp, 0.5) * w}
        for comp, w in DEFAULT_SCORE_WEIGHTS.items()
    }


def _scored_job(db: Session, sid: str, *, skills: float, holistic: float = 50.0) -> int:
    job = Job(source_key="s", source_job_id=sid, url=f"u/{sid}", title="t", normalized_title="t")
    db.add(job)
    db.flush()
    run = Run(trigger="manual", status="completed")
    db.add(run)
    db.flush()
    db.add(
        JobScore(
            job_id=job.id,
            run_id=run.id,
            decision=Decision.MAYBE,
            soft_score=50.0,
            soft_breakdown=_breakdown(skills_match=skills),
            llm_holistic=holistic,
        )
    )
    db.flush()
    return job.id


def test_not_enough_data(db_session: Session):
    _scored_job(db_session, "a", skills=0.9)
    set_feedback(db_session, 1, "up")
    db_session.commit()

    report = build_report(db_session)
    assert report.ready is False
    assert report.n_labeled == 1
    assert "at least" in report.reason


def test_positive_correlation_raises_weight(db_session: Session):
    # 6 liked jobs with high skills_match, 6 disliked with low skills_match
    for i in range(6):
        jid = _scored_job(db_session, f"up{i}", skills=0.9, holistic=80.0)
        set_feedback(db_session, jid, "up")
    for i in range(6):
        jid = _scored_job(db_session, f"down{i}", skills=0.1, holistic=20.0)
        set_feedback(db_session, jid, "down")
    db_session.commit()

    report = build_report(db_session)
    assert report.ready is True
    assert report.n_positive == 6 and report.n_negative == 6

    skills = next(c for c in report.components if c.name == "skills_match")
    assert skills.correlation > 0.5
    assert skills.suggested_weight > skills.current_weight
    assert abs(sum(report.suggested_weights.values()) - 100.0) < 0.5


def test_feedback_overrides_application_label(db_session: Session):
    jid = _scored_job(db_session, "conflict", skills=0.9)
    db_session.add(Application(job_id=jid, status=ApplicationStatus.APPLIED))
    set_feedback(db_session, jid, "down")
    db_session.commit()

    examples = build_report(db_session)
    # only one labelled example, and it is negative (feedback wins)
    assert examples.n_positive == 0
    assert examples.n_negative == 1


def test_application_status_supplies_label(db_session: Session):
    jid = _scored_job(db_session, "app", skills=0.5)
    db_session.add(Application(job_id=jid, status=ApplicationStatus.OFFER))
    db_session.commit()
    report = build_report(db_session)
    assert report.n_labeled == 1 and report.n_positive == 1


def test_apply_writes_weights(db_session: Session):
    for i in range(6):
        jid = _scored_job(db_session, f"up{i}", skills=0.9)
        set_feedback(db_session, jid, "up")
    for i in range(6):
        jid = _scored_job(db_session, f"down{i}", skills=0.1)
        set_feedback(db_session, jid, "down")
    db_session.commit()

    row = apply_report(db_session)
    db_session.commit()

    assert abs(sum(row.weights.values()) - 100.0) < 0.5
    stored = db_session.exec(select(AppSettings)).one()
    assert stored.weights == row.weights
    assert stored.weights["skills_match"] > DEFAULT_SCORE_WEIGHTS["skills_match"]


def test_apply_refuses_without_data(db_session: Session):
    with pytest.raises(ValueError, match="at least"):
        apply_report(db_session)


def test_clear_feedback(db_session: Session):
    jid = _scored_job(db_session, "x", skills=0.5)
    set_feedback(db_session, jid, "up")
    db_session.commit()
    assert clear_feedback(db_session, jid) is True
    assert clear_feedback(db_session, jid) is False
    assert db_session.exec(select(JobFeedback)).all() == []


def test_calibrate_cli(db_session: Session, capsys):
    for i in range(6):
        jid = _scored_job(db_session, f"up{i}", skills=0.9)
        set_feedback(db_session, jid, "up")
    for i in range(6):
        jid = _scored_job(db_session, f"down{i}", skills=0.1)
        set_feedback(db_session, jid, "down")
    db_session.commit()

    assert cmd_calibrate(argparse.Namespace(apply=False)) == 0
    out = capsys.readouterr().out
    assert "skills_match" in out
    assert "--apply" in out


# --------------------------------------------------------------------------- API
def test_feedback_and_calibration_api(client, db_session: Session):
    jid = _scored_job(db_session, "api", skills=0.7)
    db_session.commit()

    resp = client.put(f"/api/jobs/{jid}/feedback", json={"verdict": "up", "note": "nice"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["verdict"] == "up"

    detail = client.get(f"/api/jobs/{jid}")
    assert detail.status_code == 200
    assert detail.json()["feedback"] == "up"

    report = client.get("/api/calibration")
    assert report.status_code == 200
    assert report.json()["ready"] is False

    apply = client.post("/api/calibration/apply")
    assert apply.status_code == 422

    assert client.delete(f"/api/jobs/{jid}/feedback").status_code == 204
    assert client.delete(f"/api/jobs/{jid}/feedback").status_code == 404


def test_feedback_api_rejects_bad_verdict(client, db_session: Session):
    jid = _scored_job(db_session, "bad", skills=0.5)
    db_session.commit()
    assert client.put(f"/api/jobs/{jid}/feedback", json={"verdict": "meh"}).status_code == 422
    assert client.put("/api/jobs/9999/feedback", json={"verdict": "up"}).status_code == 404
