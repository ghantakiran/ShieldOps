"""Cost anomaly predictor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
cap_route = APIRouter(
    prefix="/cost-anomaly-predictor",
    tags=["Cost Anomaly Predictor"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Cost anomaly predictor service unavailable",
        )
    return _instance


# -- Request models --


class RecordIndicatorRequest(BaseModel):
    service_name: str
    indicator: str = "resource_provisioning"
    value: float = 0.0
    baseline_value: float = 0.0


class PredictSpikeRequest(BaseModel):
    service_name: str


# -- Routes --


@cap_route.post("/indicators")
async def record_indicator(
    body: RecordIndicatorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    reading = engine.record_indicator(**body.model_dump())
    return reading.model_dump()


@cap_route.get("/indicators")
async def list_indicators(
    service_name: str | None = None,
    indicator: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        i.model_dump()
        for i in engine.list_indicators(
            service_name=service_name,
            indicator=indicator,
            limit=limit,
        )
    ]


@cap_route.get("/indicators/{indicator_id}")
async def get_indicator(
    indicator_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    reading = engine.get_indicator(indicator_id)
    if reading is None:
        raise HTTPException(404, f"Indicator '{indicator_id}' not found")
    return reading.model_dump()


@cap_route.post("/predictions")
async def predict_spike(
    body: PredictSpikeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    pred = engine.predict_cost_spike(body.service_name)
    return pred.model_dump()


@cap_route.get("/predictions")
async def list_predictions(
    service_name: str | None = None,
    risk_level: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        p.model_dump()
        for p in engine.list_predictions(
            service_name=service_name,
            risk_level=risk_level,
            limit=limit,
        )
    ]


@cap_route.get("/predictions/{prediction_id}")
async def get_prediction(
    prediction_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    pred = engine.get_prediction(prediction_id)
    if pred is None:
        raise HTTPException(404, f"Prediction '{prediction_id}' not found")
    return pred.model_dump()


@cap_route.get("/prevention/{service_name}")
async def suggest_prevention(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.suggest_prevention(service_name)


@cap_route.get("/preventable-spend")
async def get_preventable_spend(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.estimate_preventable_spend()


@cap_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_prediction_report().model_dump()


@cap_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
