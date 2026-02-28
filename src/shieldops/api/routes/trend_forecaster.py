"""Incident trend forecaster API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.trend_forecaster import (
    ForecastConfidence,
    IncidentCategory,
    TrendDirection,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/trend-forecaster",
    tags=["Trend Forecaster"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Trend forecaster service unavailable")
    return _engine


class RecordTrendRequest(BaseModel):
    category: IncidentCategory = IncidentCategory.INFRASTRUCTURE
    direction: TrendDirection = TrendDirection.STABLE
    confidence: ForecastConfidence = ForecastConfidence.MODERATE
    incident_count: int = 0
    growth_rate_pct: float = 0.0
    details: str = ""


class AddDataPointRequest(BaseModel):
    category: IncidentCategory = IncidentCategory.INFRASTRUCTURE
    period_label: str = ""
    incident_count: int = 0
    forecast_count: int = 0
    notes: str = ""


@router.post("/trends")
async def record_trend(
    body: RecordTrendRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_trend(**body.model_dump())
    return result.model_dump()


@router.get("/trends")
async def list_trends(
    category: IncidentCategory | None = None,
    direction: TrendDirection | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_trends(
            category=category,
            direction=direction,
            limit=limit,
        )
    ]


@router.get("/trends/{record_id}")
async def get_trend(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_trend(record_id)
    if result is None:
        raise HTTPException(404, f"Trend record '{record_id}' not found")
    return result.model_dump()


@router.post("/data-points")
async def add_data_point(
    body: AddDataPointRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_data_point(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/category/{category}")
async def analyze_trend_by_category(
    category: IncidentCategory,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_trend_by_category(category)


@router.get("/rising")
async def identify_rising_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_rising_trends()


@router.get("/rankings")
async def rank_by_growth_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_growth_rate()


@router.get("/anomalies")
async def detect_trend_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
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


itf_route = router
