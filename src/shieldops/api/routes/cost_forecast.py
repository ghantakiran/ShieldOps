"""Cost forecast API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/cost-forecast", tags=["Cost Forecast"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cost forecast service unavailable")
    return _engine


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordCostRequest(BaseModel):
    service: str
    amount: float
    currency: str = "USD"
    category: str = "compute"


class GenerateForecastRequest(BaseModel):
    periods_ahead: int = 3
    method: str = "linear"


class SetBudgetRequest(BaseModel):
    service: str
    monthly_budget: float
    alert_threshold: float = 0.9


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/datapoints")
async def record_cost(
    body: RecordCostRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    dp = engine.record_cost(
        service=body.service,
        amount=body.amount,
        currency=body.currency,
    )
    return dp.model_dump()


@router.post("/forecast/{service}")
async def generate_forecast(
    service: str,
    body: GenerateForecastRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    fc = engine.forecast(
        service=service,
        periods_ahead=body.periods_ahead,
        method=body.method,
    )
    return fc.model_dump()


@router.post("/budgets")
async def set_budget(
    body: SetBudgetRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    engine.set_budget(service=body.service, limit=body.monthly_budget)
    return {
        "service": body.service,
        "monthly_budget": body.monthly_budget,
        "alert_threshold": body.alert_threshold,
    }


@router.get("/forecasts")
async def list_forecasts(
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [f.model_dump() for f in engine.list_forecasts(service=service)]


@router.get("/forecasts/{forecast_id}")
async def get_forecast(
    forecast_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    fc = engine.get_forecast(forecast_id)
    if fc is None:
        raise HTTPException(404, f"Forecast '{forecast_id}' not found")
    return fc.model_dump()


@router.get("/alerts")
async def list_alerts(
    service: str | None = None,
    acknowledged: bool | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    alerts = engine.get_alerts(service=service)
    return [a.model_dump() for a in alerts]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
