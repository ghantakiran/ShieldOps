"""Cache effectiveness analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.cache_effectiveness import (
    CacheLayer,
    OptimizationAction,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cache-effectiveness",
    tags=["Cache Effectiveness"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cache effectiveness service unavailable")
    return _engine


class RecordMetricsRequest(BaseModel):
    cache_name: str
    layer: CacheLayer = CacheLayer.APPLICATION
    hit_rate_pct: float = 0.0
    miss_rate_pct: float = 0.0
    eviction_rate: float = 0.0
    avg_latency_ms: float = 0.0
    size_mb: float = 0.0
    details: str = ""


class AddRecommendationRequest(BaseModel):
    cache_name: str
    action: OptimizationAction = OptimizationAction.NO_ACTION
    expected_improvement_pct: float = 0.0
    reason: str = ""


@router.post("/metrics")
async def record_metrics(
    body: RecordMetricsRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_metrics(**body.model_dump())
    return result.model_dump()


@router.get("/metrics")
async def list_metrics(
    cache_name: str | None = None,
    layer: CacheLayer | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_metrics(cache_name=cache_name, layer=layer, limit=limit)
    ]


@router.get("/metrics/{record_id}")
async def get_metrics(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_metrics(record_id)
    if result is None:
        raise HTTPException(404, f"Cache metrics '{record_id}' not found")
    return result.model_dump()


@router.post("/recommendations")
async def add_recommendation(
    body: AddRecommendationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_recommendation(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{cache_name}")
async def analyze_cache_effectiveness(
    cache_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_cache_effectiveness(cache_name)


@router.get("/underperforming")
async def identify_underperforming_caches(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_underperforming_caches()


@router.get("/rankings")
async def rank_caches_by_hit_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_caches_by_hit_rate()


@router.get("/latency-impact")
async def estimate_latency_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.estimate_latency_impact()


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


ce_route = router
