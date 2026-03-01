"""Cost Forecast Validator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.forecast_validator import (
    CostDomain,
    ForecastAccuracy,
    ForecastPeriod,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/forecast-validator", tags=["Forecast Validator"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Forecast validator service unavailable")
    return _engine


class RecordForecastRequest(BaseModel):
    service_name: str
    forecast_period: ForecastPeriod = ForecastPeriod.MONTHLY
    forecast_accuracy: ForecastAccuracy = ForecastAccuracy.FAIR
    cost_domain: CostDomain = CostDomain.COMPUTE
    forecasted_amount: float = 0.0
    actual_amount: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    service_pattern: str
    forecast_period: ForecastPeriod = ForecastPeriod.MONTHLY
    cost_domain: CostDomain = CostDomain.COMPUTE
    max_deviation_pct: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_forecast(
    body: RecordForecastRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_forecast(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_forecasts(
    period: ForecastPeriod | None = None,
    accuracy: ForecastAccuracy | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_forecasts(
            period=period,
            accuracy=accuracy,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_forecast(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_forecast(record_id)
    if result is None:
        raise HTTPException(404, f"Forecast record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/accuracy")
async def analyze_forecast_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_forecast_accuracy()


@router.get("/inaccurate-forecasts")
async def identify_inaccurate_forecasts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_inaccurate_forecasts()


@router.get("/error-rankings")
async def rank_by_error(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_error()


@router.get("/trends")
async def detect_forecast_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_forecast_trends()


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


fvl_route = router
