"""Cost optimization planner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.optimization_planner import (
    ImplementationEffort,
    OptimizationPriority,
    OptimizationType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/optimization-planner",
    tags=["Optimization Planner"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Optimization planner service unavailable")
    return _engine


class RecordOptimizationRequest(BaseModel):
    resource_id: str = ""
    optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING
    priority: OptimizationPriority = OptimizationPriority.MEDIUM
    effort: ImplementationEffort = ImplementationEffort.MODERATE
    savings_pct: float = 0.0
    estimated_savings_usd: float = 0.0
    details: str = ""


class AddActionRequest(BaseModel):
    resource_id: str = ""
    optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING
    action_description: str = ""
    effort: ImplementationEffort = ImplementationEffort.LOW
    estimated_savings_usd: float = 0.0
    notes: str = ""


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
    priority: OptimizationPriority | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_optimizations(
            optimization_type=optimization_type,
            priority=priority,
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


@router.post("/actions")
async def add_action(
    body: AddActionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_action(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/type/{optimization_type}")
async def analyze_optimization_by_type(
    optimization_type: OptimizationType,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_optimization_by_type(optimization_type)


@router.get("/quick-wins")
async def identify_quick_wins(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_quick_wins()


@router.get("/rankings")
async def rank_by_savings_potential(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_savings_potential()


@router.get("/trends")
async def detect_optimization_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
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


cop_route = router
