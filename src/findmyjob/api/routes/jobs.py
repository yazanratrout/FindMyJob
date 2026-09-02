"""Ranked job list + job detail for the dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from findmyjob.db import get_session
from findmyjob.models.enums import Decision
from findmyjob.schemas.calibration import FeedbackRead, FeedbackRequest
from findmyjob.schemas.job import JobCard, JobDetail, JobList
from findmyjob.services.feedback import FeedbackError, clear_feedback, set_feedback
from findmyjob.services.job_read import bucket_counts, get_job_row, list_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])

_BUCKETS: dict[str, list[Decision]] = {
    "recommended": [Decision.RECOMMENDED],
    "maybe": [Decision.MAYBE],
    "shortlist": [Decision.RECOMMENDED, Decision.MAYBE],
    "all": [Decision.RECOMMENDED, Decision.MAYBE, Decision.ARCHIVED],
}


@router.get("", response_model=JobList)
def get_jobs(
    bucket: str = Query("shortlist"),
    source: str | None = None,
    search: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
) -> JobList:
    buckets = _BUCKETS.get(bucket, _BUCKETS["shortlist"])
    rows = list_jobs(session, buckets=buckets, source=source, search=search, limit=limit)
    return JobList(
        jobs=[JobCard.of(r) for r in rows],
        counts=bucket_counts(session),
    )


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: int, session: Session = Depends(get_session)) -> JobDetail:
    row = get_job_row(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found or not scored yet")
    from findmyjob.services.applications import application_for_job
    from findmyjob.services.feedback import get_feedback

    fb = get_feedback(session, job_id)
    return JobDetail.of_detail(
        row,
        application_for_job(session, job_id),
        feedback=fb.verdict if fb else None,
    )


@router.put("/{job_id}/feedback", response_model=FeedbackRead)
def put_feedback(
    job_id: int, body: FeedbackRequest, session: Session = Depends(get_session)
) -> FeedbackRead:
    try:
        row = set_feedback(session, job_id, body.verdict, body.note)
    except FeedbackError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return FeedbackRead(job_id=row.job_id, verdict=row.verdict, note=row.note)


@router.delete("/{job_id}/feedback", status_code=204)
def delete_feedback(job_id: int, session: Session = Depends(get_session)) -> None:
    if not clear_feedback(session, job_id):
        raise HTTPException(status_code=404, detail="no feedback for this job")
    session.commit()
