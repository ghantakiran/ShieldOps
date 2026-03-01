"""Change Correlation Engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.change_correlator import (
    ChangeOutcome,
    CorrelationStrength,
    CorrelationType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/change-correlator",
    tags=["Change Correlator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Change correlator service unavailable")
    return _engine


class RecordCorrelationRequest(BaseModel):
    change_id: str
    incident_id: str = ""
    correlation_type: CorrelationType = CorrelationType.CAUSAL
    strength: CorrelationStrength = CorrelationStrength.UNKNOWN
    outcome: ChangeOutcome = ChangeOutcome.PENDING
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddPatternRequest(BaseModel):
    pattern_name: str
    correlation_type: CorrelationType = CorrelationType.CAUSAL
    occurrence_count: int = 0
    avg_strength_score: float = 0.0
    model_config = {"extra": "forbid"}


@router.post("/correlations")
async def record_correlation(
    body: RecordCorrelationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_correlation(**body.model_dump())
    return result.model_dump()


@router.get("/correlations")
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


@router.get("/correlations/{record_id}")
async def get_correlation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_correlation(record_id)
    if result is None:
        raise HTTPException(404, f"Correlation '{record_id}' not found")
    return result.model_dump()


@router.post("/patterns")
async def add_pattern(
    body: AddPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_correlation_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_correlation_distribution()


@router.get("/strong-correlations")
async def identify_strong_correlations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_strong_correlations()


@router.get("/incident-impact-rankings")
async def rank_by_incident_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_incident_impact()


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


ccr_route = router
