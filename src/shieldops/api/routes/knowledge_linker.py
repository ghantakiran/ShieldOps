"""Incident knowledge linker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.knowledge_linker import (
    KnowledgeSource,
    LinkRelevance,
    LinkType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/knowledge-linker",
    tags=["Knowledge Linker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Knowledge linker service unavailable")
    return _engine


class RecordLinkRequest(BaseModel):
    incident_id: str
    knowledge_resource_id: str = ""
    link_type: LinkType = LinkType.DOCUMENTATION
    relevance: LinkRelevance = LinkRelevance.SOMEWHAT_RELEVANT
    knowledge_source: KnowledgeSource = KnowledgeSource.INTERNAL_WIKI
    relevance_score_pct: float = 0.0
    notes: str = ""


class AddSuggestionRequest(BaseModel):
    incident_pattern: str
    suggested_resource_id: str = ""
    link_type: LinkType = LinkType.RUNBOOK
    knowledge_source: KnowledgeSource = KnowledgeSource.RUNBOOK_LIBRARY
    confidence_pct: float = 0.0
    auto_link: bool = False


@router.post("/links")
async def record_link(
    body: RecordLinkRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_link(**body.model_dump())
    return result.model_dump()


@router.get("/links")
async def list_links(
    incident_id: str | None = None,
    link_type: LinkType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_links(incident_id=incident_id, link_type=link_type, limit=limit)
    ]


@router.get("/links/{record_id}")
async def get_link(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_link(record_id)
    if result is None:
        raise HTTPException(404, f"Knowledge link record '{record_id}' not found")
    return result.model_dump()


@router.post("/suggestions")
async def add_suggestion(
    body: AddSuggestionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_suggestion(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{incident_id}")
async def analyze_link_effectiveness(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_link_effectiveness(incident_id)


@router.get("/unlinked-incidents")
async def identify_unlinked_incidents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unlinked_incidents()


@router.get("/rankings")
async def rank_by_relevance_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_relevance_score()


@router.get("/knowledge-gaps")
async def detect_knowledge_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_knowledge_gaps()


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


ikl_route = router
