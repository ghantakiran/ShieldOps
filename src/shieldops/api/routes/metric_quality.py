"""Metric Quality Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.metric_quality import (
    QualityDimension,
    QualityIssue,
    QualityLevel,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/metric-quality", tags=["Metric Quality"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Metric quality service unavailable")
    return _engine


class RecordQualityRequest(BaseModel):
    metric_name: str
    quality_dimension: QualityDimension = QualityDimension.COMPLETENESS
    quality_level: QualityLevel = QualityLevel.ACCEPTABLE
    quality_issue: QualityIssue = QualityIssue.MISSING_DATA
    quality_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    assessment_name: str
    quality_dimension: QualityDimension = QualityDimension.COMPLETENESS
    score_threshold: float = 0.0
    avg_quality_score: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_quality(
    body: RecordQualityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_quality(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_qualities(
    dimension: QualityDimension | None = None,
    level: QualityLevel | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_qualities(
            dimension=dimension,
            level=level,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_quality(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_quality(record_id)
    if result is None:
        raise HTTPException(404, f"Metric quality record '{record_id}' not found")
    return result.model_dump()


@router.post("/assessments")
async def add_assessment(
    body: AddAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/quality-analysis")
async def analyze_metric_quality(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_metric_quality()


@router.get("/poor-metrics")
async def identify_poor_metrics(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_poor_metrics()


@router.get("/quality-rankings")
async def rank_by_quality_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_quality_score()


@router.get("/degradation")
async def detect_quality_degradation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_quality_degradation()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


mqs_route = router
