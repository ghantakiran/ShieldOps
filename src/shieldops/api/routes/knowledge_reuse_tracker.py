"""Knowledge Reuse Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.knowledge_reuse_tracker import (
    ContentType,
    ReuseContext,
    ReuseOutcome,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/knowledge-reuse-tracker",
    tags=["Knowledge Reuse Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Knowledge reuse tracker service unavailable")
    return _engine


class RecordReuseRequest(BaseModel):
    content_id: str
    content_type: ContentType = ContentType.ARTICLE
    reuse_outcome: ReuseOutcome = ReuseOutcome.RESOLVED_ISSUE
    reuse_context: ReuseContext = ReuseContext.INCIDENT_RESPONSE
    reuse_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    content_id: str
    content_type: ContentType = ContentType.ARTICLE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/reuse-records")
async def record_reuse(
    body: RecordReuseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_reuse(**body.model_dump())
    return result.model_dump()


@router.get("/reuse-records")
async def list_reuse_records(
    content_type: ContentType | None = None,
    reuse_outcome: ReuseOutcome | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_reuse_records(
            content_type=content_type,
            reuse_outcome=reuse_outcome,
            team=team,
            limit=limit,
        )
    ]


@router.get("/reuse-records/{record_id}")
async def get_reuse(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_reuse(record_id)
    if result is None:
        raise HTTPException(404, f"Reuse record '{record_id}' not found")
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
async def analyze_reuse_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_reuse_distribution()


@router.get("/low-reuse")
async def identify_low_reuse_content(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_reuse_content()


@router.get("/reuse-rankings")
async def rank_by_reuse(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_reuse()


@router.get("/trends")
async def detect_reuse_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_reuse_trends()


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


kru_route = router
