"""Operational readiness scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.readiness_scorer import (
    AssessmentTrigger,
    ReadinessDimension,
    ReadinessGrade,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/readiness-scorer",
    tags=["Readiness Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Readiness scorer service unavailable")
    return _engine


class RecordAssessmentRequest(BaseModel):
    service_name: str
    dimension: ReadinessDimension = ReadinessDimension.MONITORING
    grade: ReadinessGrade = ReadinessGrade.ADEQUATE
    score: float = 0.0
    trigger: AssessmentTrigger = AssessmentTrigger.MANUAL
    assessor: str = ""
    details: str = ""


class RecordGapRequest(BaseModel):
    service_name: str
    dimension: ReadinessDimension = ReadinessDimension.MONITORING
    current_grade: ReadinessGrade = ReadinessGrade.FAILING
    target_grade: ReadinessGrade = ReadinessGrade.GOOD
    remediation: str = ""
    priority: int = 0
    details: str = ""


@router.post("/assessments")
async def record_assessment(
    body: RecordAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/assessments")
async def list_assessments(
    service_name: str | None = None,
    dimension: ReadinessDimension | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_assessments(
            service_name=service_name, dimension=dimension, limit=limit
        )
    ]


@router.get("/assessments/{record_id}")
async def get_assessment(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_assessment(record_id)
    if result is None:
        raise HTTPException(404, f"Assessment record '{record_id}' not found")
    return result.model_dump()


@router.post("/gaps")
async def record_gap(
    body: RecordGapRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_gap(**body.model_dump())
    return result.model_dump()


@router.get("/readiness/{service_name}")
async def analyze_service_readiness(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_service_readiness(service_name)


@router.get("/failing")
async def identify_failing_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failing_services()


@router.get("/ranked")
async def rank_by_readiness_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_readiness_score()


@router.get("/weaknesses")
async def detect_dimension_weaknesses(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_dimension_weaknesses()


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


ors_route = router
