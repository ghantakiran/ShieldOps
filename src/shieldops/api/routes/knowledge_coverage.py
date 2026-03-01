"""Knowledge Coverage Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.knowledge_coverage import (
    CoverageArea,
    CoverageGapType,
    CoverageLevel,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/knowledge-coverage", tags=["Knowledge Coverage"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Knowledge coverage service unavailable")
    return _engine


class RecordCoverageRequest(BaseModel):
    service_id: str
    coverage_area: CoverageArea = CoverageArea.RUNBOOKS
    coverage_level: CoverageLevel = CoverageLevel.NONE
    coverage_gap_type: CoverageGapType = CoverageGapType.MISSING_RUNBOOK
    coverage_pct: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddGapRequest(BaseModel):
    gap_pattern: str
    coverage_area: CoverageArea = CoverageArea.RUNBOOKS
    severity_score: float = 0.0
    affected_services: int = 0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_coverage(
    body: RecordCoverageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_coverage(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_coverages(
    coverage_area: CoverageArea | None = None,
    coverage_level: CoverageLevel | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_coverages(
            coverage_area=coverage_area,
            coverage_level=coverage_level,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_coverage(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_coverage(record_id)
    if result is None:
        raise HTTPException(404, f"Coverage record '{record_id}' not found")
    return result.model_dump()


@router.post("/gaps")
async def add_gap(
    body: AddGapRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_gap(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_coverage_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_coverage_patterns()


@router.get("/coverage-gaps")
async def identify_coverage_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_coverage_gaps()


@router.get("/coverage-rankings")
async def rank_by_coverage_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_coverage_score()


@router.get("/trends")
async def detect_coverage_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
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


kca_route = router
