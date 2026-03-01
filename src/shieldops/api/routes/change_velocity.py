"""Change Velocity Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.change_velocity import (
    ChangeScope,
    VelocityRisk,
    VelocityTrend,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/change-velocity",
    tags=["Change Velocity"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Change velocity service unavailable")
    return _engine


class RecordVelocityRequest(BaseModel):
    period_id: str
    velocity_trend: VelocityTrend = VelocityTrend.STABLE
    change_scope: ChangeScope = ChangeScope.PATCH
    velocity_risk: VelocityRisk = VelocityRisk.NONE
    changes_per_day: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    period_id: str
    velocity_trend: VelocityTrend = VelocityTrend.STABLE
    metric_value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


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
    trend: VelocityTrend | None = None,
    scope: ChangeScope | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_velocities(
            trend=trend,
            scope=scope,
            service=service,
            team=team,
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


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_velocity_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_velocity_distribution()


@router.get("/high-velocity")
async def identify_high_velocity_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_velocity_services()


@router.get("/velocity-rankings")
async def rank_by_velocity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_velocity()


@router.get("/trends")
async def detect_velocity_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
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


cvl_route = router
