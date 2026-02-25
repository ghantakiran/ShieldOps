"""Knowledge decay detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.knowledge_decay import (
    ArticleType,
    DecayRisk,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/knowledge-decay",
    tags=["Knowledge Decay"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Knowledge decay service unavailable",
        )
    return _engine


class AssessDecayRequest(BaseModel):
    article_id: str
    article_title: str = ""
    article_type: ArticleType = ArticleType.RUNBOOK
    age_days: int = 0
    last_reviewed_days_ago: int = 0
    usage_count_30d: int = 0
    signals: list[str] | None = None


class SetThresholdRequest(BaseModel):
    article_type: ArticleType
    stale_days: int = 180
    obsolete_days: int = 365
    min_usage_30d: int = 1


@router.post("/assessments")
async def assess_decay(
    body: AssessDecayRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.assess_decay(**body.model_dump())
    return result.model_dump()


@router.get("/assessments")
async def list_assessments(
    article_type: ArticleType | None = None,
    decay_risk: DecayRisk | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_assessments(
            article_type=article_type, decay_risk=decay_risk, limit=limit
        )
    ]


@router.get("/assessments/{record_id}")
async def get_assessment(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_assessment(record_id)
    if result is None:
        raise HTTPException(404, f"Assessment '{record_id}' not found")
    return result.model_dump()


@router.post("/thresholds")
async def set_threshold(
    body: SetThresholdRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.set_threshold(**body.model_dump())
    return result.model_dump()


@router.get("/decay-score/{article_id}")
async def calculate_decay_score(
    article_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_decay_score(article_id)


@router.get("/obsolete")
async def identify_obsolete_articles(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_obsolete_articles()


@router.get("/review-priority")
async def prioritize_for_review(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.prioritize_for_review()


@router.get("/deprecated-references")
async def detect_deprecated_references(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_deprecated_references()


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


kd_route = router
