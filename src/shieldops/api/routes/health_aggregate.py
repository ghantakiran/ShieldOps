"""Health check aggregation API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.health_aggregator import HealthStatus

logger = structlog.get_logger()
router = APIRouter(prefix="/health/aggregate", tags=["Health Aggregate"])

_aggregator: Any = None


def set_aggregator(aggregator: Any) -> None:
    global _aggregator
    _aggregator = aggregator


def _get_aggregator() -> Any:
    if _aggregator is None:
        raise HTTPException(503, "Health aggregation service unavailable")
    return _aggregator


class UpdateComponentRequest(BaseModel):
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""


@router.get("")
async def get_aggregate_health() -> dict[str, Any]:
    agg = _get_aggregator()
    return agg.compute().model_dump()


@router.get("/history")
async def get_health_history(
    limit: int = 50,
) -> list[dict[str, Any]]:
    agg = _get_aggregator()
    return [s.model_dump() for s in agg.get_history(limit)]


@router.get("/components/{name}")
async def get_component_health(
    name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    comp = agg.get_component(name)
    if comp is None:
        raise HTTPException(404, f"Component '{name}' not found")
    return comp.model_dump()


@router.post("/check")
async def trigger_health_check(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    return agg.compute().model_dump()


@router.put("/components/{name}")
async def update_component_health(
    name: str,
    body: UpdateComponentRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    comp = agg.update_component(name, body.status, body.latency_ms, body.message)
    if comp is None:
        raise HTTPException(404, f"Component '{name}' not found")
    return comp.model_dump()
