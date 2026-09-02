"""Calibration: learn score weights from what the user actually liked.

Signals (per canonical job):

* an explicit thumbs-up / thumbs-down (:mod:`findmyjob.services.feedback`), or
* the application status - ``applied`` / ``interview`` / ``offer`` count as
  positive, ``rejected`` / ``withdrawn`` as negative. Explicit feedback wins
  over a status-derived label.

For every labelled job we take the *raw* value of each soft-score component
(from the latest :class:`JobScore`), then compute the Pearson correlation
between each component and the outcome. A positive correlation nudges that
component's weight up, a negative one down; the proposed set is renormalised to
sum to 100. The judge (LLM holistic) score is correlated too and used to nudge
``blend_soft_ratio``.

Pure-ish: reads the DB, never writes. :func:`apply_report` is the only writer
and it goes through :func:`findmyjob.services.settings.update_app_settings`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from sqlmodel import Session, col, select

from findmyjob.logging import get_logger
from findmyjob.models.application import Application
from findmyjob.models.config import DEFAULT_SCORE_WEIGHTS, AppSettings
from findmyjob.models.enums import ApplicationStatus
from findmyjob.models.feedback import JobFeedback
from findmyjob.models.job import Job, JobScore
from findmyjob.services.settings import get_app_settings, update_app_settings

log = get_logger("calibration")

COMPONENTS: tuple[str, ...] = tuple(DEFAULT_SCORE_WEIGHTS)

#: minimum labelled jobs (and minimum of each class) before we trust the numbers
MIN_LABELED = 8
MIN_PER_CLASS = 2

#: how hard a correlation pulls a weight: new = old * (1 + RATE * corr)
LEARNING_RATE = 0.6
MIN_WEIGHT = 1.0
MAX_WEIGHT = 40.0
BLEND_MIN, BLEND_MAX = 0.3, 0.8
BLEND_STEP = 0.1

_POSITIVE = {ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER}
_NEGATIVE = {ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}


@dataclass(slots=True)
class Example:
    job_id: int
    label: float  # 1.0 positive, 0.0 negative
    source: str  # "feedback" | "application"
    components: dict[str, float]
    judge: float | None


@dataclass(slots=True)
class ComponentReport:
    name: str
    correlation: float
    current_weight: float
    suggested_weight: float


@dataclass(slots=True)
class CalibrationReport:
    ready: bool
    reason: str
    n_labeled: int
    n_positive: int
    n_negative: int
    min_labeled: int
    components: list[ComponentReport] = field(default_factory=list)
    judge_correlation: float | None = None
    current_blend_soft_ratio: float = 0.6
    suggested_blend_soft_ratio: float = 0.6
    suggested_weights: dict[str, float] = field(default_factory=dict)


def _latest_scores(session: Session, job_ids: set[int]) -> dict[int, JobScore]:
    latest: dict[int, JobScore] = {}
    if not job_ids:
        return latest
    rows = session.exec(
        select(JobScore).where(col(JobScore.job_id).in_(job_ids)).order_by(col(JobScore.id))
    ).all()
    for score in rows:  # ascending id -> last write wins
        latest[score.job_id] = score
    return latest


def collect_examples(session: Session) -> list[Example]:
    feedback = {
        f.job_id: f for f in session.exec(select(JobFeedback)).all() if f.verdict in ("up", "down")
    }
    apps = {a.job_id: a for a in session.exec(select(Application)).all()}

    labels: dict[int, tuple[float, str]] = {}
    for job_id, fb in feedback.items():
        labels[job_id] = (1.0 if fb.verdict == "up" else 0.0, "feedback")
    for job_id, app in apps.items():
        if job_id in labels:
            continue
        if app.status in _POSITIVE:
            labels[job_id] = (1.0, "application")
        elif app.status in _NEGATIVE:
            labels[job_id] = (0.0, "application")

    scores = _latest_scores(session, set(labels))
    examples: list[Example] = []
    for job_id, (label, source) in labels.items():
        score = scores.get(job_id)
        if score is None or not score.soft_breakdown:
            continue
        if session.get(Job, job_id) is None:
            continue
        components = {
            comp: float(score.soft_breakdown.get(comp, {}).get("raw", 0.0)) for comp in COMPONENTS
        }
        judge = None if score.llm_holistic is None else float(score.llm_holistic) / 100.0
        examples.append(Example(job_id, label, source, components, judge))
    return examples


def _pearson(xs: list[float], ys: list[float]) -> float:
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    if x.size < 2 or x.std() == 0.0 or y.std() == 0.0:
        return 0.0
    corr = float(np.corrcoef(x, y)[0, 1])
    return 0.0 if math.isnan(corr) else round(corr, 3)


def _renormalise(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values()) or 1.0
    scaled = {k: round(v * 100.0 / total, 1) for k, v in weights.items()}
    drift = round(100.0 - sum(scaled.values()), 1)
    if drift and scaled:
        top = max(scaled, key=lambda k: scaled[k])
        scaled[top] = round(scaled[top] + drift, 1)
    return scaled


def build_report(session: Session) -> CalibrationReport:
    settings = get_app_settings(session)
    current = {
        c: float(settings.weights.get(c, DEFAULT_SCORE_WEIGHTS.get(c, 0.0))) for c in COMPONENTS
    }
    blend = float(settings.blend_soft_ratio)

    examples = collect_examples(session)
    n_pos = sum(1 for e in examples if e.label == 1.0)
    n_neg = len(examples) - n_pos

    base = CalibrationReport(
        ready=False,
        reason="",
        n_labeled=len(examples),
        n_positive=n_pos,
        n_negative=n_neg,
        min_labeled=MIN_LABELED,
        current_blend_soft_ratio=blend,
        suggested_blend_soft_ratio=blend,
        suggested_weights=dict(current),
    )

    if len(examples) < MIN_LABELED:
        base.reason = (
            f"Need at least {MIN_LABELED} rated jobs (have {len(examples)}). "
            "Give jobs a thumbs-up / thumbs-down or advance them in the tracker."
        )
        return base
    if n_pos < MIN_PER_CLASS or n_neg < MIN_PER_CLASS:
        base.reason = (
            f"Need at least {MIN_PER_CLASS} positive and {MIN_PER_CLASS} negative "
            f"examples (have {n_pos} / {n_neg})."
        )
        return base

    labels = [e.label for e in examples]
    components: list[ComponentReport] = []
    raw_suggestion: dict[str, float] = {}
    for comp in COMPONENTS:
        corr = _pearson([e.components[comp] for e in examples], labels)
        proposed = current[comp] * (1.0 + LEARNING_RATE * corr)
        proposed = min(MAX_WEIGHT, max(MIN_WEIGHT, proposed))
        raw_suggestion[comp] = proposed
        components.append(ComponentReport(comp, corr, round(current[comp], 1), 0.0))

    suggested = _renormalise(raw_suggestion)
    for cr in components:
        cr.suggested_weight = suggested[cr.name]

    judge_pairs = [(e.judge, e.label) for e in examples if e.judge is not None]
    judge_corr: float | None = None
    suggested_blend = blend
    if len(judge_pairs) >= MIN_LABELED:
        judge_corr = _pearson([j for j, _ in judge_pairs], [lbl for _, lbl in judge_pairs])
        mean_soft_corr = float(np.mean([abs(cr.correlation) for cr in components]))
        if judge_corr - mean_soft_corr > 0.15:
            suggested_blend = round(max(BLEND_MIN, blend - BLEND_STEP), 2)
        elif mean_soft_corr - judge_corr > 0.15:
            suggested_blend = round(min(BLEND_MAX, blend + BLEND_STEP), 2)

    return CalibrationReport(
        ready=True,
        reason="Suggestions based on your ratings and tracker outcomes.",
        n_labeled=len(examples),
        n_positive=n_pos,
        n_negative=n_neg,
        min_labeled=MIN_LABELED,
        components=components,
        judge_correlation=judge_corr,
        current_blend_soft_ratio=blend,
        suggested_blend_soft_ratio=suggested_blend,
        suggested_weights=suggested,
    )


def apply_report(session: Session) -> AppSettings:
    report = build_report(session)
    if not report.ready:
        raise ValueError(report.reason or "not enough data to calibrate")
    row = update_app_settings(
        session,
        {
            "weights": report.suggested_weights,
            "blend_soft_ratio": report.suggested_blend_soft_ratio,
        },
    )
    log.info(
        "calibration.applied",
        n_labeled=report.n_labeled,
        blend=report.suggested_blend_soft_ratio,
    )
    return row
