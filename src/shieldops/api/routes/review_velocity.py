"""Code review velocity tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.review_velocity import (
    ReviewBottleneck,
    ReviewSize,
    ReviewStage,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/review-velocity",
    tags=["Review Velocity"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Review velocity service unavailable")
    return _engine


class RecordReviewCycleRequest(BaseModel):
    pr_number: str
    author: str = ""
    reviewer: str = ""
    stage: ReviewStage = ReviewStage.AWAITING_REVIEW
    size: ReviewSize = ReviewSize.MEDIUM
    cycle_time_hours: float = 0.0
    lines_changed: int = 0
    details: str = ""


class RecordReviewerLoadRequest(BaseModel):
    reviewer: str
    active_reviews: int = 0
    avg_turnaround_hours: float = 0.0
    bottleneck: ReviewBottleneck = ReviewBottleneck.REVIEWER_AVAILABILITY
    details: str = ""


@router.post("/reviews")
async def record_review_cycle(
    body: RecordReviewCycleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_review_cycle(**body.model_dump())
    return result.model_dump()


@router.get("/reviews")
async def list_reviews(
    author: str | None = None,
    stage: ReviewStage | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.list_reviews(author=author, stage=stage, limit=limit)]


@router.get("/reviews/{record_id}")
async def get_review(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_review(record_id)
    if result is None:
        raise HTTPException(404, f"Review record '{record_id}' not found")
    return result.model_dump()


@router.post("/reviewer-loads")
async def record_reviewer_load(
    body: RecordReviewerLoadRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_reviewer_load(**body.model_dump())
    return result.model_dump()


@router.get("/velocity/{author}")
async def analyze_review_velocity(
    author: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_review_velocity(author)


@router.get("/slow-reviews")
async def identify_slow_reviews(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_reviews()


@router.get("/reviewer-rankings")
async def rank_reviewers_by_load(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_reviewers_by_load()


@router.get("/bottlenecks")
async def detect_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_bottlenecks()


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


rv_route = router
