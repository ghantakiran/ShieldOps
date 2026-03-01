"""Capacity Headroom Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.capacity_headroom import (
    GrowthRate,
    HeadroomLevel,
    ResourceType,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/capacity-headroom",
    tags=["Capacity Headroom"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Capacity headroom service unavailable")
    return _engine


class RecordHeadroomRequest(BaseModel):
    resource_id: str
    resource_type: ResourceType = ResourceType.CPU
    headroom_level: HeadroomLevel = HeadroomLevel.AMPLE
    growth_rate: GrowthRate = GrowthRate.STABLE
    headroom_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddProjectionRequest(BaseModel):
    resource_id: str
    resource_type: ResourceType = ResourceType.CPU
    projected_days: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/headroom")
async def record_headroom(
    body: RecordHeadroomRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_headroom(**body.model_dump())
    return result.model_dump()


@router.get("/headroom")
async def list_headroom(
    resource_type: ResourceType | None = None,
    level: HeadroomLevel | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_headroom(
            resource_type=resource_type,
            level=level,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/headroom/{record_id}")
async def get_headroom(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_headroom(record_id)
    if result is None:
        raise HTTPException(404, f"Headroom record '{record_id}' not found")
    return result.model_dump()


@router.post("/projections")
async def add_projection(
    body: AddProjectionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_projection(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_headroom_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_headroom_distribution()


@router.get("/critical-resources")
async def identify_critical_resources(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_resources()


@router.get("/headroom-rankings")
async def rank_by_headroom(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_headroom()


@router.get("/trends")
async def detect_headroom_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_headroom_trends()


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


chm_route = router
