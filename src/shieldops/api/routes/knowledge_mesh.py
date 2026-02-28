"""Agent knowledge mesh API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.agents.knowledge_mesh import (
    FreshnessLevel,
    KnowledgeType,
    PropagationScope,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/knowledge-mesh",
    tags=["Knowledge Mesh"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Knowledge mesh service unavailable")
    return _engine


class RecordEntryRequest(BaseModel):
    source_agent: str
    knowledge_type: KnowledgeType = KnowledgeType.OBSERVATION
    propagation_scope: PropagationScope = PropagationScope.LOCAL
    freshness_level: FreshnessLevel = FreshnessLevel.REAL_TIME
    relevance_score: float = 0.0
    details: str = ""


class AddPropagationRequest(BaseModel):
    event_label: str
    knowledge_type: KnowledgeType = KnowledgeType.OBSERVATION
    propagation_scope: PropagationScope = PropagationScope.TEAM
    hop_count: int = 0


@router.post("/entries")
async def record_entry(
    body: RecordEntryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_entry(**body.model_dump())
    return result.model_dump()


@router.get("/entries")
async def list_entries(
    source_agent: str | None = None,
    knowledge_type: KnowledgeType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_entries(
            source_agent=source_agent,
            knowledge_type=knowledge_type,
            limit=limit,
        )
    ]


@router.get("/entries/{record_id}")
async def get_entry(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_entry(record_id)
    if result is None:
        raise HTTPException(404, f"Entry '{record_id}' not found")
    return result.model_dump()


@router.post("/propagations")
async def add_propagation(
    body: AddPropagationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_propagation(**body.model_dump())
    return result.model_dump()


@router.get("/freshness/{source_agent}")
async def analyze_knowledge_freshness(
    source_agent: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_knowledge_freshness(source_agent)


@router.get("/stale-knowledge")
async def identify_stale_knowledge(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_stale_knowledge()


@router.get("/rankings")
async def rank_by_propagation_reach(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_propagation_reach()


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


akm_route = router
