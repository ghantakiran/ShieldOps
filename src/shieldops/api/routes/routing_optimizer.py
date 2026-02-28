"""Routing optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.agents.routing_optimizer import (
    ModelTier,
    RoutingCriteria,
    RoutingOutcome,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/routing-optimizer",
    tags=["Routing Optimizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Routing optimizer service unavailable")
    return _engine


class RecordRoutingRequest(BaseModel):
    task_name: str
    model_tier: ModelTier = ModelTier.STANDARD
    routing_criteria: RoutingCriteria = RoutingCriteria.COMPLEXITY
    routing_outcome: RoutingOutcome = RoutingOutcome.OPTIMAL
    cost_dollars: float = 0.0
    details: str = ""


class AddDecisionRequest(BaseModel):
    decision_label: str
    model_tier: ModelTier = ModelTier.STANDARD
    routing_outcome: RoutingOutcome = RoutingOutcome.OPTIMAL
    latency_ms: float = 0.0


@router.post("/records")
async def record_routing(
    body: RecordRoutingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_routing(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_routings(
    task_name: str | None = None,
    model_tier: ModelTier | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_routings(task_name=task_name, model_tier=model_tier, limit=limit)
    ]


@router.get("/records/{record_id}")
async def get_routing(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_routing(record_id)
    if result is None:
        raise HTTPException(404, f"Routing record '{record_id}' not found")
    return result.model_dump()


@router.post("/decisions")
async def add_decision(
    body: AddDecisionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_decision(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{task_name}")
async def analyze_routing_efficiency(
    task_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_routing_efficiency(task_name)


@router.get("/identify")
async def identify_suboptimal_routings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_suboptimal_routings()


@router.get("/rankings")
async def rank_by_cost_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_cost_efficiency()


@router.get("/detect")
async def detect_routing_failures(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_routing_failures()


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


aro_route = router
