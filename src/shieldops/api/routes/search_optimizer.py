"""Knowledge Search Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.search_optimizer import (
    ContentType,
    SearchQuality,
    UsageFrequency,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/search-optimizer",
    tags=["Knowledge Search Optimizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Knowledge search service unavailable")
    return _engine


class RecordSearchRequest(BaseModel):
    query: str
    content_type: ContentType = ContentType.RUNBOOK
    search_quality: SearchQuality = SearchQuality.ADEQUATE
    usage_frequency: UsageFrequency = UsageFrequency.MONTHLY
    relevance_score: float = 0.0
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddPatternRequest(BaseModel):
    query_pattern: str
    content_type: ContentType = ContentType.RUNBOOK
    search_quality: SearchQuality = SearchQuality.ADEQUATE
    hit_count: int = 0
    avg_relevance: float = 0.0
    model_config = {"extra": "forbid"}


@router.post("/searches")
async def record_search(
    body: RecordSearchRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_search(**body.model_dump())
    return result.model_dump()


@router.get("/searches")
async def list_searches(
    content_type: ContentType | None = None,
    quality: SearchQuality | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_searches(
            content_type=content_type,
            quality=quality,
            team=team,
            limit=limit,
        )
    ]


@router.get("/searches/{record_id}")
async def get_search(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_search(record_id)
    if result is None:
        raise HTTPException(404, f"Search '{record_id}' not found")
    return result.model_dump()


@router.post("/patterns")
async def add_pattern(
    body: AddPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/quality")
async def analyze_search_quality(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_search_quality()


@router.get("/poor-searches")
async def identify_poor_searches(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_poor_searches()


@router.get("/relevance-rankings")
async def rank_by_relevance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_relevance()


@router.get("/trends")
async def detect_search_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_search_trends()


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


kso_route = router
