"""Knowledge Graph Manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.knowledge_graph import (
    GraphHealth,
    NodeType,
    RelationshipType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/knowledge-graph",
    tags=["Knowledge Graph"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Knowledge graph service unavailable")
    return _engine


class RecordNodeRequest(BaseModel):
    node_id: str
    node_type: NodeType = NodeType.SERVICE
    relationship_type: RelationshipType = RelationshipType.DEPENDS_ON
    graph_health: GraphHealth = GraphHealth.EMPTY
    connectivity_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddEdgeRequest(BaseModel):
    node_id: str
    node_type: NodeType = NodeType.SERVICE
    edge_weight: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/nodes")
async def record_node(
    body: RecordNodeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_node(**body.model_dump())
    return result.model_dump()


@router.get("/nodes")
async def list_nodes(
    node_type: NodeType | None = None,
    relationship: RelationshipType | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_nodes(
            node_type=node_type,
            relationship=relationship,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/nodes/{record_id}")
async def get_node(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_node(record_id)
    if result is None:
        raise HTTPException(404, f"Node record '{record_id}' not found")
    return result.model_dump()


@router.post("/edges")
async def add_edge(
    body: AddEdgeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_edge(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_graph_connectivity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_graph_connectivity()


@router.get("/orphan-nodes")
async def identify_orphan_nodes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_orphan_nodes()


@router.get("/connectivity-rankings")
async def rank_by_connectivity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_connectivity()


@router.get("/trends")
async def detect_graph_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_graph_trends()


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


kgm_route = router
