"""Observability gap detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.observability_gap import (
    CoverageLevel,
    GapSeverity,
    GapType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/observability-gap",
    tags=["Observability Gap"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Observability gap service unavailable")
    return _engine


class RecordGapRequest(BaseModel):
    service_name: str
    gap_type: GapType = GapType.MISSING_METRICS
    severity: GapSeverity = GapSeverity.MODERATE
    coverage: CoverageLevel = CoverageLevel.PARTIAL
    coverage_pct: float = 0.0
    details: str = ""


class AddAssessmentRequest(BaseModel):
    assessment_name: str
    gap_type: GapType = GapType.MISSING_METRICS
    severity: GapSeverity = GapSeverity.MODERATE
    target_coverage_pct: float = 80.0
    review_interval_days: int = 30


@router.post("/gaps")
async def record_gap(
    body: RecordGapRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_gap(**body.model_dump())
    return result.model_dump()


@router.get("/gaps")
async def list_gaps(
    service_name: str | None = None,
    gap_type: GapType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_gaps(service_name=service_name, gap_type=gap_type, limit=limit)
    ]


@router.get("/gaps/{record_id}")
async def get_gap(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_gap(record_id)
    if result is None:
        raise HTTPException(404, f"Gap '{record_id}' not found")
    return result.model_dump()


@router.post("/assessments")
async def add_assessment(
    body: AddAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/coverage/{service_name}")
async def analyze_coverage_gaps(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_coverage_gaps(service_name)


@router.get("/critical-gaps")
async def identify_critical_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_gaps()


@router.get("/rankings")
async def rank_by_gap_severity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_gap_severity()


@router.get("/coverage-trends")
async def detect_coverage_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_coverage_trends()


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


ogd_route = router
