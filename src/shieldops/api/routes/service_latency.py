"""Service Latency Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.service_latency import (
    LatencyImpact,
    LatencySource,
    LatencyTier,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/service-latency", tags=["Service Latency"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Service latency service unavailable")
    return _engine


class RecordLatencyRequest(BaseModel):
    service: str
    latency_ms: float = 0.0
    latency_tier: LatencyTier = LatencyTier.ACCEPTABLE
    latency_source: LatencySource = LatencySource.APPLICATION
    impact: LatencyImpact = LatencyImpact.LOW
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddBaselineRequest(BaseModel):
    service_pattern: str
    latency_tier: LatencyTier = LatencyTier.ACCEPTABLE
    latency_source: LatencySource = LatencySource.APPLICATION
    baseline_ms: float = 0.0
    threshold_ms: float = 0.0
    reason: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_latency(
    body: RecordLatencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_latency(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_latencies(
    tier: LatencyTier | None = None,
    source: LatencySource | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_latencies(
            tier=tier,
            source=source,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_latency(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_latency(record_id)
    if result is None:
        raise HTTPException(404, f"Latency record '{record_id}' not found")
    return result.model_dump()


@router.post("/baselines")
async def add_baseline(
    body: AddBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_baseline(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_latency_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_latency_distribution()


@router.get("/slow-services")
async def identify_slow_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_services()


@router.get("/latency-rankings")
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


slt_route = router
