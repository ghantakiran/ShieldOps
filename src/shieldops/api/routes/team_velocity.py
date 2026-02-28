"""Team velocity tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.team_velocity import (
    SprintHealth,
    VelocityMetric,
    VelocityTrend,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/team-velocity",
    tags=["Team Velocity"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Team velocity service unavailable")
    return _engine


class RecordVelocityRequest(BaseModel):
    team_name: str
    metric: VelocityMetric = VelocityMetric.STORY_POINTS
    trend: VelocityTrend = VelocityTrend.STABLE
    sprint_health: SprintHealth = SprintHealth.ADEQUATE
    velocity_score: float = 0.0
    details: str = ""


class AddDataPointRequest(BaseModel):
    team_name: str
    metric: VelocityMetric = VelocityMetric.STORY_POINTS
    sprint_health: SprintHealth = SprintHealth.ADEQUATE
    value: float = 0.0
    description: str = ""


@router.post("/velocities")
async def record_velocity(
    body: RecordVelocityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_velocity(**body.model_dump())
    return result.model_dump()


@router.get("/velocities")
async def list_velocities(
    team_name: str | None = None,
    metric: VelocityMetric | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_velocities(
            team_name=team_name,
            metric=metric,
            limit=limit,
        )
    ]


@router.get("/velocities/{record_id}")
async def get_velocity(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_velocity(record_id)
    if result is None:
        raise HTTPException(404, f"Velocity record '{record_id}' not found")
    return result.model_dump()


@router.post("/data-points")
async def add_data_point(
    body: AddDataPointRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_data_point(**body.model_dump())
    return result.model_dump()


@router.get("/team-analysis/{team_name}")
async def analyze_velocity_by_team(
    team_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_velocity_by_team(team_name)


@router.get("/underperforming")
async def identify_underperforming_teams(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_underperforming_teams()


@router.get("/rankings")
async def rank_by_velocity_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_velocity_score()


@router.get("/trends")
async def detect_velocity_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_velocity_trends()


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


tvt_route = router
