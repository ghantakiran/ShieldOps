"""Cost Forecast Precision API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.cost_forecast_precision import (
    BiasDirection,
    ForecastAccuracy,
    ForecastPeriod,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cost-forecast-precision",
    tags=["Cost Forecast Precision"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cost forecast precision service unavailable")
    return _engine


class RecordPrecisionRequest(BaseModel):
    forecast_name: str
    forecast_accuracy: ForecastAccuracy = ForecastAccuracy.EXCELLENT
    bias_direction: BiasDirection = BiasDirection.CALIBRATED
    forecast_period: ForecastPeriod = ForecastPeriod.MONTHLY
    precision_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    forecast_name: str
    forecast_accuracy: ForecastAccuracy = ForecastAccuracy.EXCELLENT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/precisions")
async def record_precision(
    body: RecordPrecisionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_precision(**body.model_dump())
    return result.model_dump()


@router.get("/precisions")
async def list_precisions(
    forecast_accuracy: ForecastAccuracy | None = None,
    bias_direction: BiasDirection | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_precisions(
            forecast_accuracy=forecast_accuracy,
            bias_direction=bias_direction,
            team=team,
            limit=limit,
        )
    ]


@router.get("/precisions/{record_id}")
async def get_precision(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_precision(record_id)
    if result is None:
        raise HTTPException(404, f"Precision '{record_id}' not found")
    return result.model_dump()


@router.post("/analyses")
async def add_analysis(
    body: AddAnalysisRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_analysis(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_precision_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_precision_distribution()


@router.get("/low-precision-forecasts")
async def identify_low_precision_forecasts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_precision_forecasts()


@router.get("/precision-rankings")
async def rank_by_precision(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_precision()


@router.get("/trends")
async def detect_precision_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_precision_trends()


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


cfp_route = router
