"""Change risk predictor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.risk_predictor import (
    PredictionAccuracy,
    RiskFactor,
    RiskLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/risk-predictor",
    tags=["Risk Predictor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Risk predictor service unavailable")
    return _engine


class RecordPredictionRequest(BaseModel):
    change_id: str = ""
    risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_factor: RiskFactor = RiskFactor.CODE_COMPLEXITY
    accuracy: PredictionAccuracy = PredictionAccuracy.MODERATE
    risk_score: float = 0.0
    details: str = ""


class AddFactorRequest(BaseModel):
    change_id: str = ""
    risk_factor: RiskFactor = RiskFactor.CODE_COMPLEXITY
    factor_score: float = 0.0
    weight: float = 1.0
    notes: str = ""


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
    risk_level: RiskLevel | None = None,
    risk_factor: RiskFactor | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_predictions(
            risk_level=risk_level,
            risk_factor=risk_factor,
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
        raise HTTPException(404, f"Prediction '{record_id}' not found")
    return result.model_dump()


@router.post("/factors")
async def add_factor(
    body: AddFactorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_factor(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/accuracy/{accuracy}")
async def analyze_prediction_accuracy(
    accuracy: PredictionAccuracy,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_prediction_accuracy(accuracy)


@router.get("/high-risk")
async def identify_high_risk_changes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_changes()


@router.get("/rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/patterns")
async def detect_risk_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_risk_patterns()


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


crp_route = router
