"""Platform reliability scorecard API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.reliability_scorecard import (
    ScoreCategory,
    ScoreGrade,
    ScoreTrend,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/reliability-scorecard",
    tags=["Reliability Scorecard"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Reliability scorecard service unavailable")
    return _engine


class RecordScorecardRequest(BaseModel):
    service_name: str
    category: ScoreCategory = ScoreCategory.SLO_COMPLIANCE
    grade: ScoreGrade = ScoreGrade.C_ADEQUATE
    trend: ScoreTrend = ScoreTrend.NEW
    overall_score: float = 0.0
    details: str = ""


class AddCategoryScoreRequest(BaseModel):
    category_name: str
    category: ScoreCategory = ScoreCategory.SLO_COMPLIANCE
    grade: ScoreGrade = ScoreGrade.C_ADEQUATE
    score: float = 0.0
    description: str = ""


@router.post("/scorecards")
async def record_scorecard(
    body: RecordScorecardRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_scorecard(**body.model_dump())
    return result.model_dump()


@router.get("/scorecards")
async def list_scorecards(
    service_name: str | None = None,
    category: ScoreCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_scorecards(service_name=service_name, category=category, limit=limit)
    ]


@router.get("/scorecards/{record_id}")
async def get_scorecard(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_scorecard(record_id)
    if result is None:
        raise HTTPException(404, f"Scorecard '{record_id}' not found")
    return result.model_dump()


@router.post("/category-scores")
async def add_category_score(
    body: AddCategoryScoreRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_category_score(**body.model_dump())
    return result.model_dump()


@router.get("/reliability/{service_name}")
async def analyze_service_reliability(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_service_reliability(service_name)


@router.get("/low-scoring")
async def identify_low_scoring_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_scoring_services()


@router.get("/rankings")
async def rank_by_overall_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_overall_score()


@router.get("/trends")
async def detect_score_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_score_trends()


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


prs_route = router
