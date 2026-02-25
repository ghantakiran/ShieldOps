"""Anomaly forecast API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
afc_route = APIRouter(
    prefix="/anomaly-forecast",
    tags=["Anomaly Forecast"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Anomaly forecast service unavailable",
        )
    return _instance


# -- Request models --


class CreateForecastRequest(BaseModel):
    service_name: str
    metric_name: str
    current_value: float = 0.0
    predicted_value: float = 0.0
    anomaly_likelihood: str = "very_low"
    horizon: str = "hour_1"
    confidence: float = 0.0
    model: str = "arima"


class PredictAnomalyRequest(BaseModel):
    service_name: str
    metric_name: str
    values: list[float]


class CreateAlertRequest(BaseModel):
    forecast_id: str
    severity: str = "warning"


# -- Routes --


@afc_route.post("/forecasts")
async def create_forecast(
    body: CreateForecastRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    forecast = engine.create_forecast(**body.model_dump())
    return forecast.model_dump()  # type: ignore[no-any-return]


@afc_route.get("/forecasts")
async def list_forecasts(
    service_name: str | None = None,
    anomaly_likelihood: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [  # type: ignore[no-any-return]
        f.model_dump()
        for f in engine.list_forecasts(
            service_name=service_name,
            anomaly_likelihood=anomaly_likelihood,
            limit=limit,
        )
    ]


@afc_route.get("/forecasts/{forecast_id}")
async def get_forecast(
    forecast_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    forecast = engine.get_forecast(forecast_id)
    if forecast is None:
        raise HTTPException(
            404,
            f"Forecast '{forecast_id}' not found",
        )
    return forecast.model_dump()  # type: ignore[no-any-return]


@afc_route.post("/predict")
async def predict_anomaly(
    body: PredictAnomalyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.predict_anomaly(
        body.service_name,
        body.metric_name,
        body.values,
    )
    return result.model_dump()  # type: ignore[no-any-return]


@afc_route.post("/alerts")
async def create_alert(
    body: CreateAlertRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    alert = engine.create_alert(
        body.forecast_id,
        body.severity,
    )
    if alert is None:
        raise HTTPException(
            404,
            f"Forecast '{body.forecast_id}' not found",
        )
    return alert.model_dump()  # type: ignore[no-any-return]


@afc_route.get("/accuracy")
async def get_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return {"accuracy_pct": engine.evaluate_accuracy()}  # type: ignore[no-any-return]


@afc_route.get("/trending")
async def get_trending(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_trending_metrics()  # type: ignore[no-any-return]


@afc_route.get("/risk-ranking")
async def get_risk_ranking(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [  # type: ignore[no-any-return]
        p.model_dump() for p in engine.rank_by_risk()
    ]


@afc_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_forecast_report().model_dump()  # type: ignore[no-any-return]


@afc_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()  # type: ignore[no-any-return]
