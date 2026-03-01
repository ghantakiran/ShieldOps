"""Knowledge Usage Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.usage_analyzer import (
    ContentCategory,
    UsageTrend,
    UsageType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/usage-analyzer", tags=["Usage Analyzer"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Usage analyzer service unavailable")
    return _engine


class RecordUsageRequest(BaseModel):
    article_id: str
    usage_type: UsageType = UsageType.VIEW
    content_category: ContentCategory = ContentCategory.RUNBOOK
    usage_trend: UsageTrend = UsageTrend.NEW
    view_count: int = 0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    category_pattern: str
    content_category: ContentCategory = ContentCategory.RUNBOOK
    min_views: int = 0
    stale_after_days: int = 90
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_usage(
    body: RecordUsageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_usage(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_usages(
    usage_type: UsageType | None = None,
    content_category: ContentCategory | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_usages(
            usage_type=usage_type,
            content_category=content_category,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_usage(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_usage(record_id)
    if result is None:
        raise HTTPException(404, f"Usage record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_usage_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_usage_patterns()


@router.get("/underused")
async def identify_underused(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_underused()


@router.get("/view-rankings")
async def rank_by_views(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_views()


@router.get("/trends")
async def detect_usage_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_usage_trends()


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


kua_route = router
