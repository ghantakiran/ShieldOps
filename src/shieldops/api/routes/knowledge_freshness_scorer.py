"""Knowledge Freshness Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.knowledge_freshness_scorer import (
    ArticleType,
    FreshnessLevel,
    UpdateFrequency,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/knowledge-freshness-scorer",
    tags=["Knowledge Freshness Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Knowledge freshness scorer service unavailable")
    return _engine


class RecordFreshnessRequest(BaseModel):
    article_id: str
    freshness_level: FreshnessLevel = FreshnessLevel.CURRENT
    article_type: ArticleType = ArticleType.RUNBOOK
    update_frequency: UpdateFrequency = UpdateFrequency.MONTHLY
    freshness_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    article_id: str
    freshness_level: FreshnessLevel = FreshnessLevel.CURRENT
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/freshness")
async def record_freshness(
    body: RecordFreshnessRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_freshness(**body.model_dump())
    return result.model_dump()


@router.get("/freshness")
async def list_freshness(
    level: FreshnessLevel | None = None,
    article_type: ArticleType | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_freshness(
            level=level,
            article_type=article_type,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/freshness/{record_id}")
async def get_freshness(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_freshness(record_id)
    if result is None:
        raise HTTPException(404, f"Freshness record '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_freshness_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_freshness_distribution()


@router.get("/stale-articles")
async def identify_stale_articles(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_stale_articles()


@router.get("/freshness-rankings")
async def rank_by_freshness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_freshness()


@router.get("/trends")
async def detect_freshness_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_freshness_trends()


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


kfx_route = router
