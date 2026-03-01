"""Alert Correlation Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.alert_correlation_opt import (
    CorrelationStrength,
    CorrelationType,
    OptimizationStatus,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/alert-correlation-opt", tags=["Alert Correlation Optimizer"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Alert correlation optimizer service unavailable")
    return _engine


class RecordCorrelationRequest(BaseModel):
    alert_pair: str
    correlation_type: CorrelationType = CorrelationType.TEMPORAL
    correlation_strength: CorrelationStrength = CorrelationStrength.NONE
    optimization_status: OptimizationStatus = OptimizationStatus.PENDING
    confidence_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    alert_pattern: str
    correlation_type: CorrelationType = CorrelationType.TEMPORAL
    min_confidence: float = 0.0
    auto_merge: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_correlation(
    body: RecordCorrelationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_correlation(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_correlations(
    correlation_type: CorrelationType | None = None,
    strength: CorrelationStrength | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_correlations(
            correlation_type=correlation_type,
            strength=strength,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_correlation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_correlation(record_id)
    if result is None:
        raise HTTPException(404, f"Correlation record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_correlation_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_correlation_patterns()


@router.get("/weak-correlations")
async def identify_weak_correlations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_weak_correlations()


@router.get("/confidence-rankings")
async def rank_by_confidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_confidence()


@router.get("/trends")
async def detect_correlation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_correlation_trends()


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


aco_route = router
