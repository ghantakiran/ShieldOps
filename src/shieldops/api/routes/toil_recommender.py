"""Toil recommender API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/toil-recommender", tags=["Toil Recommender"])

_recommender: Any = None


def set_recommender(recommender: Any) -> None:
    global _recommender
    _recommender = recommender


def _get_recommender() -> Any:
    if _recommender is None:
        raise HTTPException(503, "Toil recommender service unavailable")
    return _recommender


class RecordPatternRequest(BaseModel):
    task_name: str
    team: str
    frequency_per_week: float = 0.0
    time_per_occurrence_minutes: float = 0.0
    automation_difficulty: str = "MODERATE"
    is_automatable: bool = True


@router.post("/patterns")
async def record_toil_pattern(
    body: RecordPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    recommender = _get_recommender()
    pattern = recommender.record_toil_pattern(**body.model_dump())
    return pattern.model_dump()


@router.get("/patterns")
async def list_patterns(
    team: str | None = None,
    is_automatable: bool | None = None,
    difficulty: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    recommender = _get_recommender()
    return [
        p.model_dump()
        for p in recommender.list_patterns(
            team=team, is_automatable=is_automatable, difficulty=difficulty, limit=limit
        )
    ]


@router.get("/patterns/{pattern_id}")
async def get_pattern(
    pattern_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    recommender = _get_recommender()
    pattern = recommender.get_pattern(pattern_id)
    if pattern is None:
        raise HTTPException(404, f"Pattern '{pattern_id}' not found")
    return pattern.model_dump()


@router.post("/patterns/{pattern_id}/recommend")
async def recommend_automation(
    pattern_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    recommender = _get_recommender()
    result = recommender.recommend_automation(pattern_id)
    if result is None:
        raise HTTPException(404, f"Pattern '{pattern_id}' not found")
    return result.model_dump()


@router.post("/patterns/{pattern_id}/roi")
async def estimate_roi(
    pattern_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    recommender = _get_recommender()
    result = recommender.estimate_roi(pattern_id)
    return result.model_dump()


@router.get("/ranking")
async def rank_by_roi(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    recommender = _get_recommender()
    return [r.model_dump() for r in recommender.rank_by_roi()]


@router.get("/time-saved")
async def calculate_time_saved(
    team: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    recommender = _get_recommender()
    result = recommender.calculate_time_saved(team=team)
    return result.model_dump()


@router.get("/quick-wins")
async def identify_quick_wins(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    recommender = _get_recommender()
    return [w.model_dump() for w in recommender.identify_quick_wins()]


@router.get("/report")
async def generate_recommender_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    recommender = _get_recommender()
    return recommender.generate_recommender_report()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    recommender = _get_recommender()
    return recommender.get_stats()
