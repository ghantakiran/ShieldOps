"""Audit readiness scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.audit_readiness import (
    ReadinessArea,
    ReadinessGap,
    ReadinessGrade,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/audit-readiness",
    tags=["Audit Readiness"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Audit readiness scorer service unavailable",
        )
    return _engine


class RecordReadinessRequest(BaseModel):
    area_name: str
    area: ReadinessArea = ReadinessArea.DOCUMENTATION
    grade: ReadinessGrade = ReadinessGrade.PARTIALLY_READY
    gap: ReadinessGap = ReadinessGap.MISSING_EVIDENCE
    readiness_pct: float = 0.0
    details: str = ""


class AddAssessmentRequest(BaseModel):
    area_name: str
    area: ReadinessArea = ReadinessArea.DOCUMENTATION
    grade: ReadinessGrade = ReadinessGrade.PARTIALLY_READY
    min_readiness_pct: float = 80.0
    review_frequency_days: float = 30.0


@router.post("/records")
async def record_readiness(
    body: RecordReadinessRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_readiness(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_readiness_records(
    area_name: str | None = None,
    area: ReadinessArea | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_readiness_records(
            area_name=area_name,
            area=area,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_readiness(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_readiness(record_id)
    if result is None:
        raise HTTPException(404, f"Readiness record '{record_id}' not found")
    return result.model_dump()


@router.post("/assessments")
async def add_assessment(
    body: AddAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{area_name}")
async def analyze_readiness_by_area(
    area_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_readiness_by_area(area_name)


@router.get("/critical-gaps")
async def identify_critical_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_gaps()


@router.get("/rankings")
async def rank_by_readiness_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_readiness_score()


@router.get("/trends")
async def detect_readiness_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_readiness_trends()


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


ard_route = router
