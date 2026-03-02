"""Team Capacity Planner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.team_capacity_planner import (
    BurnoutRisk,
    CapacityStatus,
    LoadCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/team-capacity-planner",
    tags=["Team Capacity Planner"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Team capacity planner service unavailable")
    return _engine


class RecordCapacityRequest(BaseModel):
    team_name: str
    capacity_status: CapacityStatus = CapacityStatus.AVAILABLE
    load_category: LoadCategory = LoadCategory.INCIDENT_RESPONSE
    burnout_risk: BurnoutRisk = BurnoutRisk.MINIMAL
    utilization_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    team_name: str
    capacity_status: CapacityStatus = CapacityStatus.AVAILABLE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/capacity-records")
async def record_capacity(
    body: RecordCapacityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_capacity(**body.model_dump())
    return result.model_dump()


@router.get("/capacity-records")
async def list_capacity_records(
    capacity_status: CapacityStatus | None = None,
    load_category: LoadCategory | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_capacity_records(
            capacity_status=capacity_status,
            load_category=load_category,
            team=team,
            limit=limit,
        )
    ]


@router.get("/capacity-records/{record_id}")
async def get_capacity(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    found = engine.get_capacity(record_id)
    if found is None:
        raise HTTPException(404, f"Capacity record '{record_id}' not found")
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
async def analyze_capacity_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_capacity_distribution()


@router.get("/overloaded-teams")
async def identify_overloaded_teams(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overloaded_teams()


@router.get("/utilization-rankings")
async def rank_by_utilization(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_utilization()


@router.get("/trends")
async def detect_capacity_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_capacity_trends()


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


tcp_route = router
