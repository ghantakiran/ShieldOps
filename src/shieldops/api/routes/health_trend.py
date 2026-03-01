"""Service Health Trend Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.health_trend import (
    HealthDimension,
    HealthGrade,
    TrendDirection,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/health-trend", tags=["Health Trend"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Health trend service unavailable")
    return _engine


class RecordTrendRequest(BaseModel):
    service_id: str
    health_dimension: HealthDimension = HealthDimension.AVAILABILITY
    trend_direction: TrendDirection = TrendDirection.STABLE
    health_grade: HealthGrade = HealthGrade.GOOD
    health_score: float = 0.0
    service: str = ""
    model_config = {"extra": "forbid"}


class AddDataPointRequest(BaseModel):
    data_label: str
    health_dimension: HealthDimension = HealthDimension.AVAILABILITY
    score_threshold: float = 0.0
    avg_health_score: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_trend(
    body: RecordTrendRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_trend(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_trends(
    dimension: HealthDimension | None = None,
    direction: TrendDirection | None = None,
    service: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_trends(
            dimension=dimension,
            direction=direction,
            service=service,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_trend(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_trend(record_id)
    if result is None:
        raise HTTPException(404, f"Health trend record '{record_id}' not found")
    return result.model_dump()


@router.post("/data-points")
async def add_data_point(
    body: AddDataPointRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_data_point(**body.model_dump())
    return result.model_dump()


@router.get("/health-trends")
async def analyze_health_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_health_trends()


@router.get("/degrading-services")
async def identify_degrading_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_degrading_services()


@router.get("/health-rankings")
async def rank_by_health_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_health_score()


@router.get("/anomalies")
async def detect_trend_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_trend_anomalies()


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


sht_route = router
