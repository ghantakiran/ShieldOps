"""Reliability Metrics Collector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.reliability_metrics import (
    MetricSource,
    MetricType,
    ReliabilityTier,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/reliability-metrics", tags=["Reliability Metrics"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Reliability metrics service unavailable")
    return _engine


class RecordMetricRequest(BaseModel):
    service_id: str
    metric_type: MetricType = MetricType.MTTR
    reliability_tier: ReliabilityTier = ReliabilityTier.UNRELIABLE
    metric_source: MetricSource = MetricSource.INCIDENT_DATA
    reliability_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddDataPointRequest(BaseModel):
    data_point_name: str
    metric_type: MetricType = MetricType.MTTR
    value: float = 0.0
    samples_count: int = 0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_metric(
    body: RecordMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_metric(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_metrics(
    metric_type: MetricType | None = None,
    reliability_tier: ReliabilityTier | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_metrics(
            metric_type=metric_type,
            reliability_tier=reliability_tier,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_metric(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_metric(record_id)
    if result is None:
        raise HTTPException(404, f"Reliability record '{record_id}' not found")
    return result.model_dump()


@router.post("/data-points")
async def add_data_point(
    body: AddDataPointRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_data_point(**body.model_dump())
    return result.model_dump()


@router.get("/reliability-trends")
async def analyze_reliability_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_reliability_trends()


@router.get("/low-reliability")
async def identify_low_reliability_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_reliability_services()


@router.get("/reliability-rankings")
async def rank_by_reliability_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_reliability_score()


@router.get("/regression")
async def detect_reliability_regression(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_reliability_regression()


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


rmc_route = router
