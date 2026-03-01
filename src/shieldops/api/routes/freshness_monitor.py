"""Knowledge freshness monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.freshness_monitor import (
    ContentType,
    FreshnessLevel,
    UpdatePriority,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/freshness-monitor",
    tags=["Freshness Monitor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Freshness monitor service unavailable")
    return _engine


class RecordFreshnessRequest(BaseModel):
    model_config = {"extra": "forbid"}

    article_id: str
    freshness: FreshnessLevel = FreshnessLevel.CURRENT
    content_type: ContentType = ContentType.DOCUMENTATION
    priority: UpdatePriority = UpdatePriority.MEDIUM
    age_days: float = 0.0
    team: str = ""
    details: str = ""


class AddAlertRequest(BaseModel):
    model_config = {"extra": "forbid"}

    record_id: str
    alert_reason: str = ""
    priority: UpdatePriority = UpdatePriority.MEDIUM
    recommended_action: str = ""


@router.post("/records")
async def record_freshness(
    body: RecordFreshnessRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_freshness(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_freshness_records(
    freshness: FreshnessLevel | None = None,
    content_type: ContentType | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_freshness_records(
            freshness=freshness,
            content_type=content_type,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_freshness(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_freshness(record_id)
    if result is None:
        raise HTTPException(404, f"Freshness record '{record_id}' not found")
    return result.model_dump()


@router.post("/alerts")
async def add_alert(
    body: AddAlertRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_alert(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_freshness_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_freshness_distribution()


@router.get("/stale")
async def identify_stale_content(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_stale_content()


@router.get("/rankings")
async def rank_by_age(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_age()


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


kfm_route = router
