"""SLO Threshold Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_threshold_optimizer import (
    OptimizationBasis,
    ThresholdConfidence,
    ThresholdDirection,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-threshold-optimizer",
    tags=["SLO Threshold Optimizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO threshold optimizer service unavailable")
    return _engine


class RecordThresholdRequest(BaseModel):
    slo_name: str
    threshold_direction: ThresholdDirection = ThresholdDirection.TIGHTEN
    optimization_basis: OptimizationBasis = OptimizationBasis.HISTORICAL_P99
    threshold_confidence: ThresholdConfidence = ThresholdConfidence.VERY_HIGH
    adjustment_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    slo_name: str
    threshold_direction: ThresholdDirection = ThresholdDirection.TIGHTEN
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/thresholds")
async def record_threshold(
    body: RecordThresholdRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_threshold(**body.model_dump())
    return result.model_dump()


@router.get("/thresholds")
async def list_thresholds(
    threshold_direction: ThresholdDirection | None = None,
    optimization_basis: OptimizationBasis | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_thresholds(
            threshold_direction=threshold_direction,
            optimization_basis=optimization_basis,
            team=team,
            limit=limit,
        )
    ]


@router.get("/thresholds/{record_id}")
async def get_threshold(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    found = engine.get_threshold(record_id)
    if found is None:
        raise HTTPException(404, f"Threshold '{record_id}' not found")
    return found.model_dump()


@router.post("/analyses")
async def add_analysis(
    body: AddAnalysisRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_analysis(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_threshold_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_threshold_distribution()


@router.get("/low-confidence-thresholds")
async def identify_low_confidence_thresholds(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_confidence_thresholds()


@router.get("/adjustment-rankings")
async def rank_by_adjustment(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_adjustment()


@router.get("/trends")
async def detect_threshold_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_threshold_trends()


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


sto_route = router
