"""SLO Error Budget Forecaster API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_error_budget_forecaster import (
    BudgetForecast,
    DepletionRate,
    ForecastHorizon,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-error-budget-forecaster",
    tags=["SLO Error Budget Forecaster"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO error budget forecaster service unavailable")
    return _engine


class RecordForecastRequest(BaseModel):
    forecast_id: str
    budget_forecast: BudgetForecast = BudgetForecast.SAFE
    depletion_rate: DepletionRate = DepletionRate.STABLE
    forecast_horizon: ForecastHorizon = ForecastHorizon.ONE_MONTH
    remaining_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    forecast_id: str
    budget_forecast: BudgetForecast = BudgetForecast.SAFE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/forecasts")
async def record_forecast(
    body: RecordForecastRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_forecast(**body.model_dump())
    return result.model_dump()


@router.get("/forecasts")
async def list_forecasts(
    budget_forecast: BudgetForecast | None = None,
    depletion_rate: DepletionRate | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_forecasts(
            budget_forecast=budget_forecast,
            depletion_rate=depletion_rate,
            team=team,
            limit=limit,
        )
    ]


@router.get("/forecasts/{record_id}")
async def get_forecast(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_forecast(record_id)
    if result is None:
        raise HTTPException(404, f"Forecast '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_forecast_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_forecast_distribution()


@router.get("/critical-forecasts")
async def identify_critical_forecasts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_forecasts()


@router.get("/remaining-rankings")
async def rank_by_remaining(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_remaining()


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


ebx_route = router
