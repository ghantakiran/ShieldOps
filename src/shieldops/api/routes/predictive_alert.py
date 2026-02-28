"""Predictive alert engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.predictive_alert import (
    AlertConfidence,
    PredictionType,
    PreventionOutcome,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/predictive-alert",
    tags=["Predictive Alert"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Predictive alert service unavailable")
    return _engine


class RecordAlertRequest(BaseModel):
    service_name: str
    prediction_type: PredictionType = PredictionType.TREND_BREACH
    alert_confidence: AlertConfidence = AlertConfidence.MODERATE
    prevention_outcome: PreventionOutcome = PreventionOutcome.PREVENTED
    lead_time_minutes: float = 0.0
    details: str = ""


class AddTrendRequest(BaseModel):
    trend_label: str
    prediction_type: PredictionType = PredictionType.TREND_BREACH
    alert_confidence: AlertConfidence = AlertConfidence.HIGH
    slope_value: float = 0.0


@router.post("/records")
async def record_alert(
    body: RecordAlertRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_alert(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_alerts(
    service_name: str | None = None,
    prediction_type: PredictionType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_alerts(
            service_name=service_name, prediction_type=prediction_type, limit=limit
        )
    ]


@router.get("/records/{record_id}")
async def get_alert(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_alert(record_id)
    if result is None:
        raise HTTPException(404, f"Alert '{record_id}' not found")
    return result.model_dump()


@router.post("/trends")
async def add_trend(
    body: AddTrendRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_trend(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{service_name}")
async def analyze_prediction_accuracy(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_prediction_accuracy(service_name)


@router.get("/identify")
async def identify_false_positives(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_false_positives()


@router.get("/rankings")
async def rank_by_lead_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_lead_time()


@router.get("/detect")
async def detect_prediction_drift(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_prediction_drift()


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


pae_route = router
