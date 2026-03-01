"""Capacity Utilization Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.capacity_utilization_tracker import (
    AllocationStrategy,
    ResourceType,
    UtilizationLevel,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/capacity-utilization-tracker",
    tags=["Capacity Utilization Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Capacity utilization tracker service unavailable")
    return _engine


class RecordUtilizationRequest(BaseModel):
    resource_id: str
    resource_type: ResourceType = ResourceType.CPU
    utilization_level: UtilizationLevel = UtilizationLevel.UNKNOWN
    allocation_strategy: AllocationStrategy = AllocationStrategy.ON_DEMAND
    utilization_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    resource_id: str
    resource_type: ResourceType = ResourceType.CPU
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/utilizations")
async def record_utilization(
    body: RecordUtilizationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_utilization(**body.model_dump())
    return result.model_dump()


@router.get("/utilizations")
async def list_utilizations(
    resource_type: ResourceType | None = None,
    level: UtilizationLevel | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_utilizations(
            resource_type=resource_type,
            level=level,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/utilizations/{record_id}")
async def get_utilization(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_utilization(record_id)
    if result is None:
        raise HTTPException(404, f"Utilization '{record_id}' not found")
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
async def analyze_utilization_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_utilization_distribution()


@router.get("/wasteful-resources")
async def identify_wasteful_resources(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_wasteful_resources()


@router.get("/utilization-rankings")
async def rank_by_utilization(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_utilization()


@router.get("/trends")
async def detect_utilization_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_utilization_trends()


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


cux_route = router
