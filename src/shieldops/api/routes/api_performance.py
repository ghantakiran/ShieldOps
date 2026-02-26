"""API performance profiler API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.api_performance import (
    LatencyPercentile,
    PerformanceTier,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/api-performance",
    tags=["API Performance"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "API performance service unavailable")
    return _engine


class RecordPerformanceRequest(BaseModel):
    endpoint_name: str
    tier: PerformanceTier = PerformanceTier.ACCEPTABLE
    percentile: LatencyPercentile = LatencyPercentile.P50
    latency_ms: float = 0.0
    details: str = ""


class AddEndpointProfileRequest(BaseModel):
    profile_name: str
    tier: PerformanceTier = PerformanceTier.ACCEPTABLE
    percentile: LatencyPercentile = LatencyPercentile.P50
    avg_latency_ms: float = 0.0
    description: str = ""


@router.post("/performances")
async def record_performance(
    body: RecordPerformanceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_performance(**body.model_dump())
    return result.model_dump()


@router.get("/performances")
async def list_performances(
    endpoint_name: str | None = None,
    tier: PerformanceTier | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_performances(
            endpoint_name=endpoint_name,
            tier=tier,
            limit=limit,
        )
    ]


@router.get("/performances/{record_id}")
async def get_performance(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_performance(record_id)
    if result is None:
        raise HTTPException(404, f"Performance record '{record_id}' not found")
    return result.model_dump()


@router.post("/profiles")
async def add_endpoint_profile(
    body: AddEndpointProfileRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_endpoint_profile(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{endpoint_name}")
async def analyze_endpoint_performance(
    endpoint_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_endpoint_performance(endpoint_name)


@router.get("/slow-endpoints")
async def identify_slow_endpoints(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_endpoints()


@router.get("/rankings")
async def rank_by_latency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_latency()


@router.get("/degradation")
async def detect_performance_degradation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_performance_degradation()


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


apf_route = router
