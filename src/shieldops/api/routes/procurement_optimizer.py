"""Procurement Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.procurement_optimizer import (
    OptimizationAction,
    ProcurementStatus,
    ProcurementType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/procurement-optimizer", tags=["Procurement Optimizer"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Procurement optimizer service unavailable")
    return _engine


class RecordProcurementRequest(BaseModel):
    resource_name: str
    procurement_type: ProcurementType = ProcurementType.ON_DEMAND
    procurement_status: ProcurementStatus = ProcurementStatus.NEEDS_REVIEW
    optimization_action: OptimizationAction = OptimizationAction.RIGHTSIZE
    waste_pct: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddOpportunityRequest(BaseModel):
    opportunity_name: str
    procurement_type: ProcurementType = ProcurementType.ON_DEMAND
    estimated_savings: float = 0.0
    avg_waste_pct: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_procurement(
    body: RecordProcurementRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_procurement(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_procurements(
    procurement_type: ProcurementType | None = None,
    status: ProcurementStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_procurements(
            procurement_type=procurement_type,
            status=status,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_procurement(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_procurement(record_id)
    if result is None:
        raise HTTPException(404, f"Procurement record '{record_id}' not found")
    return result.model_dump()


@router.post("/opportunities")
async def add_opportunity(
    body: AddOpportunityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_opportunity(**body.model_dump())
    return result.model_dump()


@router.get("/efficiency")
async def analyze_procurement_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_procurement_efficiency()


@router.get("/waste")
async def identify_waste(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_waste()


@router.get("/savings-rankings")
async def rank_by_savings_potential(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_savings_potential()


@router.get("/trends")
async def detect_procurement_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_procurement_trends()


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


pro_route = router
