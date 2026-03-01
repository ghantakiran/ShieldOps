"""Runbook Quality Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.runbook_quality_scorer import (
    QualityDimension,
    QualityGrade,
    RunbookType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/runbook-quality-scorer",
    tags=["Runbook Quality Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Runbook quality scorer service unavailable")
    return _engine


class RecordQualityRequest(BaseModel):
    runbook_id: str
    quality_dimension: QualityDimension = QualityDimension.COMPLETENESS
    quality_grade: QualityGrade = QualityGrade.ADEQUATE
    runbook_type: RunbookType = RunbookType.AUTOMATED
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    runbook_id: str
    quality_dimension: QualityDimension = QualityDimension.COMPLETENESS
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/qualities")
async def record_quality(
    body: RecordQualityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_quality(**body.model_dump())
    return result.model_dump()


@router.get("/qualities")
async def list_qualities(
    dimension: QualityDimension | None = None,
    grade: QualityGrade | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_qualities(
            dimension=dimension,
            grade=grade,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/qualities/{record_id}")
async def get_quality(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    found = engine.get_quality(record_id)
    if found is None:
        raise HTTPException(404, f"Quality record '{record_id}' not found")
    return found.model_dump()


@router.post("/assessments")
async def add_assessment(
    body: AddAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_quality_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_quality_distribution()


@router.get("/low-quality")
async def identify_low_quality(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_quality()


@router.get("/quality-rankings")
async def rank_by_quality(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_quality()


@router.get("/trends")
async def detect_quality_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_quality_trends()


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


rqx_route = router
