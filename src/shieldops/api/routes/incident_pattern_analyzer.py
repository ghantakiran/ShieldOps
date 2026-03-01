"""Incident Pattern Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.incident_pattern_analyzer import (
    PatternConfidence,
    PatternScope,
    PatternType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/incident-pattern-analyzer",
    tags=["Incident Pattern Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Incident pattern analyzer service unavailable")
    return _engine


class RecordPatternRequest(BaseModel):
    pattern_id: str
    pattern_type: PatternType = PatternType.ISOLATED
    pattern_confidence: PatternConfidence = PatternConfidence.SPECULATIVE
    pattern_scope: PatternScope = PatternScope.SINGLE_SERVICE
    frequency_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    pattern_id: str
    pattern_type: PatternType = PatternType.ISOLATED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/patterns")
async def record_pattern(
    body: RecordPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def list_patterns(
    pattern_type: PatternType | None = None,
    pattern_confidence: PatternConfidence | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_patterns(
            pattern_type=pattern_type,
            pattern_confidence=pattern_confidence,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/patterns/{record_id}")
async def get_pattern(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_pattern(record_id)
    if result is None:
        raise HTTPException(404, f"Pattern '{record_id}' not found")
    return result.model_dump()


@router.post("/analyses")
async def add_analysis(
    body: AddAnalysisRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_analysis(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_pattern_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_pattern_distribution()


@router.get("/recurring-patterns")
async def identify_recurring_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_recurring_patterns()


@router.get("/frequency-rankings")
async def rank_by_frequency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_frequency()


@router.get("/trends")
async def detect_pattern_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_pattern_trends()


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


ipz_route = router
