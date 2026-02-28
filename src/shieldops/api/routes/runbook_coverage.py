"""Runbook Coverage Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.runbook_coverage import (
    CoverageGap,
    CoverageLevel,
    IncidentType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/runbook-coverage",
    tags=["Runbook Coverage"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Runbook coverage analyzer service unavailable",
        )
    return _engine


class RecordCoverageRequest(BaseModel):
    service: str
    incident_type: IncidentType = IncidentType.OUTAGE
    coverage_level: CoverageLevel = CoverageLevel.NONE
    coverage_score: float = 0.0
    gap: CoverageGap | None = None
    runbook_count: int = 0
    automated: bool = False
    details: str = ""


class AddGapRequest(BaseModel):
    service: str
    incident_type: IncidentType = IncidentType.OUTAGE
    gap: CoverageGap = CoverageGap.MISSING_RUNBOOK
    priority: str = ""
    recommended_action: str = ""
    description: str = ""


@router.post("/records")
async def record_coverage(
    body: RecordCoverageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_coverage(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_coverages(
    coverage_level: CoverageLevel | None = None,
    incident_type: IncidentType | None = None,
    gap: CoverageGap | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_coverages(
            coverage_level=coverage_level,
            incident_type=incident_type,
            gap=gap,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_coverage(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_coverage(record_id)
    if record is None:
        raise HTTPException(404, f"Coverage record '{record_id}' not found")
    return record.model_dump()


@router.post("/gaps")
async def add_gap(
    body: AddGapRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    gap = engine.add_gap(**body.model_dump())
    return gap.model_dump()


@router.get("/by-service")
async def analyze_coverage_by_service(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_coverage_by_service()


@router.get("/uncovered")
async def identify_uncovered_scenarios(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_uncovered_scenarios()


@router.get("/rank-by-score")
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
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_report()
    return report.model_dump()


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


rca_route = router
