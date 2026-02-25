"""Outage predictor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
op_route = APIRouter(
    prefix="/outage-predictor",
    tags=["Outage Predictor"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Outage predictor service unavailable",
        )
    return _instance


# -- Request models --


class RecordSignalRequest(BaseModel):
    service_name: str
    signal_type: str = "metric_drift"
    value: float = 0.0
    weight: float = 1.0


class ComputePredictionRequest(BaseModel):
    service_name: str


# -- Routes --


@op_route.post("/signals")
async def record_signal(
    body: RecordSignalRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    signal = engine.record_signal(**body.model_dump())
    return signal.model_dump()


@op_route.get("/signals")
async def list_signals(
    service_name: str | None = None,
    signal_type: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        s.model_dump()
        for s in engine.list_signals(
            service_name=service_name,
            signal_type=signal_type,
            limit=limit,
        )
    ]


@op_route.get("/signals/{signal_id}")
async def get_signal(
    signal_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    signal = engine.get_signal(signal_id)
    if signal is None:
        raise HTTPException(404, f"Signal '{signal_id}' not found")
    return signal.model_dump()


@op_route.post("/predictions")
async def compute_prediction(
    body: ComputePredictionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    pred = engine.compute_prediction(body.service_name)
    return pred.model_dump()


@op_route.get("/predictions")
async def list_predictions(
    service_name: str | None = None,
    probability: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        p.model_dump()
        for p in engine.list_predictions(
            service_name=service_name,
            probability=probability,
            limit=limit,
        )
    ]


@op_route.get("/predictions/{prediction_id}")
async def get_prediction(
    prediction_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    pred = engine.get_prediction(prediction_id)
    if pred is None:
        raise HTTPException(404, f"Prediction '{prediction_id}' not found")
    return pred.model_dump()


@op_route.get("/lead-time/{service_name}")
async def assess_lead_time(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.assess_lead_time(service_name)


@op_route.get("/mitigation/{service_name}")
async def recommend_mitigation(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.recommend_mitigation(service_name)


@op_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_prediction_report().model_dump()


@op_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
