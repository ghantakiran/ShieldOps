"""Knowledge Feedback Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.feedback_loop import (
    ContentQuality,
    FeedbackSource,
    FeedbackType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/feedback-loop", tags=["Feedback Loop"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Knowledge feedback analyzer service unavailable")
    return _engine


class RecordFeedbackRequest(BaseModel):
    article_id: str
    feedback_type: FeedbackType = FeedbackType.HELPFUL
    feedback_source: FeedbackSource = FeedbackSource.SELF_SERVICE
    content_quality: ContentQuality = ContentQuality.ADEQUATE
    satisfaction_score: float = 0.0
    reviewer: str = ""
    model_config = {"extra": "forbid"}


class AddSummaryRequest(BaseModel):
    summary_name: str
    feedback_type: FeedbackType = FeedbackType.HELPFUL
    avg_satisfaction: float = 0.0
    total_feedbacks: int = 0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_feedback(
    body: RecordFeedbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_feedback(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_feedbacks(
    feedback_type: FeedbackType | None = None,
    feedback_source: FeedbackSource | None = None,
    reviewer: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_feedbacks(
            feedback_type=feedback_type,
            feedback_source=feedback_source,
            reviewer=reviewer,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_feedback(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_feedback(record_id)
    if result is None:
        raise HTTPException(404, f"Feedback record '{record_id}' not found")
    return result.model_dump()


@router.post("/summaries")
async def add_summary(
    body: AddSummaryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_summary(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_feedback_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_feedback_patterns()


@router.get("/poor-articles")
async def identify_poor_articles(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_poor_articles()


@router.get("/satisfaction-rankings")
async def rank_by_satisfaction(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_satisfaction()


@router.get("/trends")
async def detect_feedback_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_feedback_trends()


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


kfa_route = router
