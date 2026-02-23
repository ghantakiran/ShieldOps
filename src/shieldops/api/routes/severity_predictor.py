"""Incident severity prediction API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/severity-predictor",
    tags=["Severity Predictor"],
)

_predictor: Any = None


def set_predictor(predictor: Any) -> None:
    global _predictor
    _predictor = predictor


def _get_predictor() -> Any:
    if _predictor is None:
        raise HTTPException(503, "Severity predictor service unavailable")
    return _predictor


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterServiceRequest(BaseModel):
    service_name: str
    criticality: int = 3
    tags: list[str] = Field(default_factory=list)


class PredictRequest(BaseModel):
    service: str
    signals: list[dict[str, Any]]


class RecordActualRequest(BaseModel):
    actual_severity: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/services")
async def register_service(
    body: RegisterServiceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    profile = predictor.register_service(
        service_name=body.service_name,
        criticality=body.criticality,
        tags=body.tags,
    )
    return profile.model_dump()


@router.get("/services")
async def list_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    return [p.model_dump() for p in predictor.list_profiles()]


@router.post("/predict")
async def predict(
    body: PredictRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    prediction = predictor.predict(service=body.service, signals=body.signals)
    return prediction.model_dump()


@router.put("/predictions/{prediction_id}/actual")
async def record_actual(
    prediction_id: str,
    body: RecordActualRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    prediction = predictor.record_actual(prediction_id, body.actual_severity)
    if prediction is None:
        raise HTTPException(404, f"Prediction '{prediction_id}' not found")
    return prediction.model_dump()


@router.get("/predictions")
async def list_predictions(
    service: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    preds = predictor.list_predictions(service=service, outcome=outcome)
    return [p.model_dump() for p in preds[-limit:]]


@router.get("/predictions/{prediction_id}")
async def get_prediction(
    prediction_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    prediction = predictor.get_prediction(prediction_id)
    if prediction is None:
        raise HTTPException(404, f"Prediction '{prediction_id}' not found")
    return prediction.model_dump()


@router.get("/accuracy")
async def get_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    return predictor.get_accuracy()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    return predictor.get_stats()
