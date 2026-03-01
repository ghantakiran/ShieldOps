"""Capacity utilization optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.capacity_utilizer import (
    OptimizationAction,
    ResourceType,
    UtilizationBand,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/capacity-utilizer",
    tags=["Capacity Utilizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Capacity utilizer service unavailable")
    return _engine


class RecordUtilizationRequest(BaseModel):
    resource_id: str
    resource_type: ResourceType = ResourceType.COMPUTE
    utilization_pct: float = 0.0
    band: UtilizationBand = UtilizationBand.OPTIMAL
    team: str = ""
    recommended_action: OptimizationAction = OptimizationAction.RIGHTSIZE
    potential_savings: float = 0.0
    details: str = ""


class AddSuggestionRequest(BaseModel):
    resource_id: str
    action: OptimizationAction = OptimizationAction.RIGHTSIZE
    current_size: str = ""
    recommended_size: str = ""
    estimated_savings: float = 0.0
    confidence_pct: float = 0.0


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
    band: UtilizationBand | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_utilizations(
            resource_type=resource_type, band=band, team=team, limit=limit
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
        raise HTTPException(404, f"Utilization record '{record_id}' not found")
    return result.model_dump()


@router.post("/suggestions")
async def add_suggestion(
    body: AddSuggestionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_suggestion(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/by-type")
async def analyze_utilization_by_type(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_utilization_by_type()


@router.get("/opportunities")
async def identify_optimization_opportunities(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_optimization_opportunities()


@router.get("/rankings")
async def rank_by_savings_potential(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_savings_potential()


@router.get("/trends")
async def detect_utilization_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
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


cup_route = router
