"""Change Impact Predictor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.change_impact_predictor import (
    BlastRadius,
    ImpactCategory,
    PredictionConfidence,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/change-impact-predictor",
    tags=["Change Impact Predictor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Change impact predictor service unavailable")
    return _engine


class RecordPredictionRequest(BaseModel):
    prediction_id: str
    impact_category: ImpactCategory = ImpactCategory.PERFORMANCE
    prediction_confidence: PredictionConfidence = PredictionConfidence.UNCERTAIN
    blast_radius: BlastRadius = BlastRadius.ISOLATED
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAccuracyRequest(BaseModel):
    prediction_id: str
    impact_category: ImpactCategory = ImpactCategory.PERFORMANCE
    accuracy_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


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
    category: ImpactCategory | None = None,
    confidence: PredictionConfidence | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_predictions(
            category=category,
            confidence=confidence,
            service=service,
            team=team,
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


@router.post("/accuracy")
async def add_accuracy(
    body: AddAccuracyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_accuracy(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_impact_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_impact_distribution()


@router.get("/high-impact")
async def identify_high_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_impact()


@router.get("/impact-rankings")
async def rank_by_impact_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact_score()


@router.get("/trends")
async def detect_prediction_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_prediction_trends()


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


cpx_route = router
