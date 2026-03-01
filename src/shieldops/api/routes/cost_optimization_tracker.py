"""Cost Optimization Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.cost_optimization_tracker import (
    OptimizationStatus,
    OptimizationType,
    SavingsCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cost-optimization-tracker",
    tags=["Cost Optimization Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cost optimization tracker service unavailable")
    return _engine


class RecordOptimizationRequest(BaseModel):
    optimization_id: str
    optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING
    optimization_status: OptimizationStatus = OptimizationStatus.IDENTIFIED
    savings_category: SavingsCategory = SavingsCategory.COMPUTE
    savings_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    optimization_id: str
    optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/optimizations")
async def record_optimization(
    body: RecordOptimizationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_optimization(**body.model_dump())
    return result.model_dump()


@router.get("/optimizations")
async def list_optimizations(
    optimization_type: OptimizationType | None = None,
    optimization_status: OptimizationStatus | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_optimizations(
            optimization_type=optimization_type,
            optimization_status=optimization_status,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/optimizations/{record_id}")
async def get_optimization(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_optimization(record_id)
    if result is None:
        raise HTTPException(404, f"Optimization '{record_id}' not found")
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
async def analyze_optimization_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_optimization_distribution()


@router.get("/pending-optimizations")
async def identify_pending_optimizations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_pending_optimizations()


@router.get("/savings-rankings")
async def rank_by_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_savings()


@router.get("/trends")
async def detect_optimization_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_optimization_trends()


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


cox_route = router
