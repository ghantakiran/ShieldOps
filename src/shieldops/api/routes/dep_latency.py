"""Dependency Latency Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.dep_latency import (
    LatencySource,
    LatencyTier,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/dep-latency", tags=["Dependency Latency"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Dependency latency service unavailable")
    return _engine


class RecordLatencyRequest(BaseModel):
    service: str
    dependency: str
    latency_ms: float = 0.0
    latency_tier: LatencyTier = LatencyTier.NORMAL
    latency_source: LatencySource = LatencySource.NETWORK
    details: str = ""
    model_config = {"extra": "forbid"}


class AddBreakdownRequest(BaseModel):
    record_id: str
    component: str
    component_latency_ms: float = 0.0
    percentage: float = 0.0
    model_config = {"extra": "forbid"}


@router.post("/latencies")
async def record_latency(
    body: RecordLatencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_latency(**body.model_dump())
    return result.model_dump()


@router.get("/latencies")
async def list_latencies(
    tier: LatencyTier | None = None,
    source: LatencySource | None = None,
    service: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_latencies(tier=tier, source=source, service=service, limit=limit)
    ]


@router.get("/latencies/{record_id}")
async def get_latency(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_latency(record_id)
    if result is None:
        raise HTTPException(404, f"Latency record '{record_id}' not found")
    return result.model_dump()


@router.post("/breakdowns")
async def add_breakdown(
    body: AddBreakdownRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_breakdown(**body.model_dump())
    return result.model_dump()


@router.get("/by-dependency")
async def analyze_latency_by_dependency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_latency_by_dependency()


@router.get("/slow-dependencies")
async def identify_slow_dependencies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_dependencies()


@router.get("/service-rankings")
async def rank_by_latency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_latency()


@router.get("/trends")
async def detect_latency_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_latency_trends()


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


dlt_route = router
