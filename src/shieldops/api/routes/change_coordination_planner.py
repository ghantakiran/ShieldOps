"""Change Coordination Planner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.change_coordination_planner import (
    ConflictSeverity,
    CoordinationStatus,
    ScheduleWindow,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/change-coordination-planner",
    tags=["Change Coordination Planner"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Change coordination planner service unavailable")
    return _engine


class RecordCoordinationRequest(BaseModel):
    change_id: str
    coordination_status: CoordinationStatus = CoordinationStatus.ALIGNED
    conflict_severity: ConflictSeverity = ConflictSeverity.NONE
    schedule_window: ScheduleWindow = ScheduleWindow.OFF_PEAK
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    change_id: str
    coordination_status: CoordinationStatus = CoordinationStatus.ALIGNED
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/coordinations")
async def record_coordination(
    body: RecordCoordinationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_coordination(**body.model_dump())
    return result.model_dump()


@router.get("/coordinations")
async def list_coordinations(
    coordination_status: CoordinationStatus | None = None,
    conflict_severity: ConflictSeverity | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_coordinations(
            coordination_status=coordination_status,
            conflict_severity=conflict_severity,
            team=team,
            limit=limit,
        )
    ]


@router.get("/coordinations/{record_id}")
async def get_coordination(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    found = engine.get_coordination(record_id)
    if found is None:
        raise HTTPException(404, f"Coordination '{record_id}' not found")
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
async def analyze_coordination_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_coordination_distribution()


@router.get("/high-risk-coordinations")
async def identify_high_risk_coordinations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_coordinations()


@router.get("/risk-rankings")
async def rank_by_risk(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk()


@router.get("/trends")
async def detect_coordination_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_coordination_trends()


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


ccp_route = router
