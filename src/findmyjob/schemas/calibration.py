from __future__ import annotations

from pydantic import BaseModel, Field

from findmyjob.services.calibration import CalibrationReport


class FeedbackRequest(BaseModel):
    verdict: str = Field(pattern="^(up|down)$")
    note: str = ""


class FeedbackRead(BaseModel):
    job_id: int
    verdict: str
    note: str


class ComponentReportRead(BaseModel):
    name: str
    correlation: float
    current_weight: float
    suggested_weight: float


class CalibrationReportRead(BaseModel):
    ready: bool
    reason: str
    n_labeled: int
    n_positive: int
    n_negative: int
    min_labeled: int
    components: list[ComponentReportRead]
    judge_correlation: float | None
    current_blend_soft_ratio: float
    suggested_blend_soft_ratio: float
    suggested_weights: dict[str, float]

    @classmethod
    def of(cls, report: CalibrationReport) -> CalibrationReportRead:
        return cls(
            ready=report.ready,
            reason=report.reason,
            n_labeled=report.n_labeled,
            n_positive=report.n_positive,
            n_negative=report.n_negative,
            min_labeled=report.min_labeled,
            components=[
                ComponentReportRead(
                    name=c.name,
                    correlation=c.correlation,
                    current_weight=c.current_weight,
                    suggested_weight=c.suggested_weight,
                )
                for c in report.components
            ],
            judge_correlation=report.judge_correlation,
            current_blend_soft_ratio=report.current_blend_soft_ratio,
            suggested_blend_soft_ratio=report.suggested_blend_soft_ratio,
            suggested_weights=report.suggested_weights,
        )
