"""SLA breach predictor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.breach_predictor import (
    BreachCategory,
    BreachRisk,
    MitigationAction,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/breach-predictor",
    tags=["Breach Predictor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Breach predictor service unavailable")
    return _engine


class RecordPredictionRequest(BaseModel):
    service_name: str
    risk: BreachRisk = BreachRisk.LOW
    category: BreachCategory = BreachCategory.AVAILABILITY
    action: MitigationAction = MitigationAction.NO_ACTION
    confidence_pct: float = 0.0
    details: str = ""


class AddThresholdRequest(BaseModel):
    threshold_name: str
    category: BreachCategory = BreachCategory.AVAILABILITY
    risk: BreachRisk = BreachRisk.MODERATE
    warning_hours: float = 24.0
    critical_hours: float = 4.0


@router.post("/predictions")
async def record_prediction(
    body: RecordPredictionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_prediction(**body.model_dump())
    return result.model_dump()


@router.get("/predictions")
async def list_predictions(
    service_name: str | None = None,
    risk: BreachRisk | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_predictions(
            service_name=service_name,
            risk=risk,
            limit=limit,
        )
    ]


@router.get("/predictions/{record_id}")
async def get_prediction(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_prediction(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Prediction '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/thresholds")
async def add_threshold(
    body: AddThresholdRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_threshold(**body.model_dump())
    return result.model_dump()


@router.get("/risk/{service_name}")
async def analyze_breach_risk(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_breach_risk(service_name)


@router.get("/imminent-breaches")
async def identify_imminent_breaches(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_imminent_breaches()


@router.get("/rankings")
async def rank_by_confidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_confidence()


@router.get("/breach-patterns")
async def detect_breach_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_breach_patterns()


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


sbp_route = router
