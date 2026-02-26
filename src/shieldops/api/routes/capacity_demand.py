"""Capacity demand modeler API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.capacity_demand import (
    DemandPattern,
    ResourceType,
    SupplyStatus,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/capacity-demand",
    tags=["Capacity Demand"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Capacity demand service unavailable")
    return _engine


class RecordDemandRequest(BaseModel):
    service_name: str
    resource_type: ResourceType = ResourceType.COMPUTE
    demand_pattern: DemandPattern = DemandPattern.STEADY
    current_usage_pct: float = 0.0
    peak_usage_pct: float = 0.0
    supply_status: SupplyStatus | None = None
    details: str = ""


class RecordSupplyGapRequest(BaseModel):
    service_name: str
    resource_type: ResourceType = ResourceType.COMPUTE
    gap_pct: float = 0.0
    projected_deficit_date: str = ""
    mitigation: str = ""


@router.post("/demands")
async def record_demand(
    body: RecordDemandRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_demand(**body.model_dump())
    return result.model_dump()


@router.get("/demands")
async def list_demands(
    service_name: str | None = None,
    resource_type: ResourceType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_demands(
            service_name=service_name,
            resource_type=resource_type,
            limit=limit,
        )
    ]


@router.get("/demands/{record_id}")
async def get_demand(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_demand(record_id)
    if result is None:
        raise HTTPException(404, f"Demand '{record_id}' not found")
    return result.model_dump()


@router.post("/supply-gaps")
async def record_supply_gap(
    body: RecordSupplyGapRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_supply_gap(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{service_name}")
async def analyze_demand_pattern(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_demand_pattern(service_name)


@router.get("/deficits")
async def identify_supply_deficits(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_supply_deficits()


@router.get("/rankings")
async def rank_by_peak_usage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_peak_usage()


@router.get("/growth-forecast")
async def forecast_demand_growth(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.forecast_demand_growth()


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


cdm_route = router
