"""Knowledge Gap Detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.knowledge_gap_detector import (
    GapDomain,
    GapSeverity,
    GapStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/knowledge-gap-detector",
    tags=["Knowledge Gap Detector"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Knowledge gap detector service unavailable")
    return _engine


class RecordGapRequest(BaseModel):
    gap_id: str
    gap_severity: GapSeverity = GapSeverity.MODERATE
    gap_domain: GapDomain = GapDomain.INFRASTRUCTURE
    gap_status: GapStatus = GapStatus.OPEN
    coverage_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    gap_id: str
    gap_severity: GapSeverity = GapSeverity.MODERATE
    assessment_score: float = 0.0
    threshold: float = 80.0
    description: str = ""
    model_config = {"extra": "forbid"}


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
    gap_severity: GapSeverity | None = None,
    gap_domain: GapDomain | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_gaps(
            gap_severity=gap_severity,
            gap_domain=gap_domain,
            team=team,
            limit=limit,
        )
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


@router.get("/distribution")
async def analyze_gap_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_gap_distribution()


@router.get("/critical-gaps")
async def identify_critical_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_gaps()


@router.get("/coverage-rankings")
async def rank_by_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_coverage()


@router.get("/trends")
async def detect_gap_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_gap_trends()


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


kgd_route = router
