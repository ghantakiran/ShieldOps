"""Operational Metric Aggregator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.metric_aggregator import (
    AggregationLevel,
    MetricDomain,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/metric-aggregator",
    tags=["Metric Aggregator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Metric aggregator service unavailable")
    return _engine


class RecordMetricRequest(BaseModel):
    metric_name: str
    domain: MetricDomain = MetricDomain.RELIABILITY
    aggregation_level: AggregationLevel = AggregationLevel.PLATFORM
    value: float = 0.0
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddThresholdRequest(BaseModel):
    metric_pattern: str
    domain: MetricDomain = MetricDomain.RELIABILITY
    aggregation_level: AggregationLevel = AggregationLevel.PLATFORM
    min_value: float = 0.0
    max_value: float = 0.0
    reason: str = ""
    model_config = {"extra": "forbid"}


@router.post("/metrics")
async def record_metric(
    body: RecordMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_metric(**body.model_dump())
    return result.model_dump()


@router.get("/metrics")
async def list_metrics(
    domain: MetricDomain | None = None,
    aggregation_level: AggregationLevel | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_metrics(
            domain=domain,
            aggregation_level=aggregation_level,
            team=team,
            limit=limit,
        )
    ]


@router.get("/metrics/{record_id}")
async def get_metric(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_metric(record_id)
    if result is None:
        raise HTTPException(404, f"Metric '{record_id}' not found")
    return result.model_dump()


@router.post("/thresholds")
async def add_threshold(
    body: AddThresholdRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_threshold(**body.model_dump())
    return result.model_dump()


@router.get("/health")
async def analyze_metric_health(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_metric_health()


@router.get("/breached")
async def identify_breached_thresholds(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_breached_thresholds()


@router.get("/value-rankings")
async def rank_by_metric_value(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_metric_value()


@router.get("/trends")
async def detect_metric_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_metric_trends()


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


oma_route = router
