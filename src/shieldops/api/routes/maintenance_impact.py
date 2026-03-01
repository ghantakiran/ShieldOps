"""Maintenance Impact Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.maintenance_impact import (
    ImpactLevel,
    MaintenanceOutcome,
    MaintenanceType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/maintenance-impact", tags=["Maintenance Impact"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Maintenance impact service unavailable")
    return _engine


class RecordMaintenanceRequest(BaseModel):
    window_id: str
    maintenance_type: MaintenanceType = MaintenanceType.PLANNED
    impact_level: ImpactLevel = ImpactLevel.NO_IMPACT
    maintenance_outcome: MaintenanceOutcome = MaintenanceOutcome.SUCCESSFUL
    impact_minutes: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAttributionRequest(BaseModel):
    window_id: str
    maintenance_type: MaintenanceType = MaintenanceType.PLANNED
    downtime_minutes: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_maintenance(
    body: RecordMaintenanceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_maintenance(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_maintenances(
    maintenance_type: MaintenanceType | None = None,
    impact_level: ImpactLevel | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_maintenances(
            maintenance_type=maintenance_type,
            impact_level=impact_level,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_maintenance(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_maintenance(record_id)
    if result is None:
        raise HTTPException(404, f"Maintenance record '{record_id}' not found")
    return result.model_dump()


@router.post("/attributions")
async def add_attribution(
    body: AddAttributionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_attribution(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_maintenance_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_maintenance_impact()


@router.get("/high-impact")
async def identify_high_impact_windows(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_impact_windows()


@router.get("/impact-rankings")
async def rank_by_impact_minutes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact_minutes()


@router.get("/trends")
async def detect_impact_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_impact_trends()


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


mia_route = router
