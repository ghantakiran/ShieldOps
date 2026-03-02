"""Service Routing Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.service_routing_optimizer import (
    OptimizationAction,
    RouteHealth,
    RouteType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/service-routing-optimizer",
    tags=["Service Routing Optimizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Service routing optimizer service unavailable")
    return _engine


class RecordRoutingRequest(BaseModel):
    route_name: str
    route_health: RouteHealth = RouteHealth.OPTIMAL
    optimization_action: OptimizationAction = OptimizationAction.CONSOLIDATE
    route_type: RouteType = RouteType.SYNCHRONOUS
    latency_ms: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddOptimizationRequest(BaseModel):
    route_name: str
    route_health: RouteHealth = RouteHealth.OPTIMAL
    optimization_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/routings")
async def record_routing(
    body: RecordRoutingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_routing(**body.model_dump())
    return result.model_dump()


@router.get("/routings")
async def list_routings(
    route_health: RouteHealth | None = None,
    optimization_action: OptimizationAction | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_routings(
            route_health=route_health,
            optimization_action=optimization_action,
            team=team,
            limit=limit,
        )
    ]


@router.get("/routings/{record_id}")
async def get_routing(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_routing(record_id)
    if result is None:
        raise HTTPException(404, f"Routing '{record_id}' not found")
    return result.model_dump()


@router.post("/optimizations")
async def add_optimization(
    body: AddOptimizationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_optimization(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_routing_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_routing_distribution()


@router.get("/high-latency")
async def identify_high_latency_routes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_latency_routes()


@router.get("/latency-rankings")
async def rank_by_latency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_latency()


@router.get("/trends")
async def detect_routing_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_routing_trends()


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


sro_route = router
