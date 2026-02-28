"""Deployment impact predictor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.impact_predictor import (
    ImpactCategory,
    ImpactScope,
    PredictionBasis,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/impact-predictor",
    tags=["Impact Predictor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Impact predictor service unavailable")
    return _engine


class RecordPredictionRequest(BaseModel):
    deployment_name: str
    scope: ImpactScope = ImpactScope.MINIMAL
    category: ImpactCategory = ImpactCategory.PERFORMANCE
    basis: PredictionBasis = PredictionBasis.HISTORICAL_DATA
    impact_score: float = 0.0
    details: str = ""


class AddDetailRequest(BaseModel):
    detail_name: str
    scope: ImpactScope = ImpactScope.MINIMAL
    category: ImpactCategory = ImpactCategory.PERFORMANCE
    impact_score: float = 0.0
    description: str = ""


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
    scope: ImpactScope | None = None,
    category: ImpactCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_predictions(scope=scope, category=category, limit=limit)
    ]


@router.get("/predictions/{record_id}")
async def get_prediction(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_prediction(record_id)
    if result is None:
        raise HTTPException(404, f"Prediction record '{record_id}' not found")
    return result.model_dump()


@router.post("/details")
async def add_detail(
    body: AddDetailRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_detail(**body.model_dump())
    return result.model_dump()


@router.get("/accuracy/{deployment_name}")
async def analyze_prediction_accuracy(
    deployment_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_prediction_accuracy(deployment_name)


@router.get("/high-impact")
async def identify_high_impact_deploys(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_impact_deploys()


@router.get("/rankings")
async def rank_by_impact_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact_score()


@router.get("/patterns")
async def detect_impact_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_impact_patterns()


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


dip_route = router
