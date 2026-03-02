"""SLO Cross-Correlation API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_cross_correlation import (
    CorrelationStrength,
    CorrelationType,
    SLOCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-cross-correlation",
    tags=["SLO Cross-Correlation"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO cross-correlation service unavailable")
    return _engine


class RecordCorrelationRequest(BaseModel):
    slo_pair_name: str
    correlation_type: CorrelationType = CorrelationType.POSITIVE
    correlation_strength: CorrelationStrength = CorrelationStrength.VERY_STRONG
    slo_category: SLOCategory = SLOCategory.AVAILABILITY
    correlation_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    slo_pair_name: str
    correlation_type: CorrelationType = CorrelationType.POSITIVE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
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
    correlation_strength: CorrelationStrength | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_correlations(
            correlation_type=correlation_type,
            correlation_strength=correlation_strength,
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
    found = engine.get_correlation(record_id)
    if found is None:
        raise HTTPException(404, f"Correlation '{record_id}' not found")
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
async def analyze_correlation_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_correlation_distribution()


@router.get("/weak-correlations")
async def identify_weak_correlations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_weak_correlations()


@router.get("/correlation-rankings")
async def rank_by_correlation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_correlation()


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


sxc_route = router
