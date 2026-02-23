"""Infrastructure topology mapping API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/infrastructure-map", tags=["Infrastructure Map"])

_mapper: Any = None


def set_mapper(mapper: Any) -> None:
    global _mapper
    _mapper = mapper


def _get_mapper() -> Any:
    if _mapper is None:
        raise HTTPException(503, "Infrastructure map service unavailable")
    return _mapper


class AddNodeRequest(BaseModel):
    name: str
    node_type: str
    environment: str = "production"
    provider: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddRelationshipRequest(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str
    latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateHealthRequest(BaseModel):
    health_status: str


@router.post("/nodes")
async def add_node(
    body: AddNodeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    node = mapper.add_node(**body.model_dump())
    return node.model_dump()


@router.get("/nodes")
async def list_nodes(
    node_type: str | None = None,
    environment: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mapper = _get_mapper()
    return [n.model_dump() for n in mapper.list_nodes(node_type=node_type, environment=environment)]


@router.get("/nodes/{node_id}")
async def get_node(
    node_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    node = mapper.get_node(node_id)
    if node is None:
        raise HTTPException(404, f"Node '{node_id}' not found")
    return node.model_dump()


@router.put("/nodes/{node_id}/health")
async def update_node_health(
    node_id: str,
    body: UpdateHealthRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    node = mapper.update_node_health(node_id, body.health_status)
    if node is None:
        raise HTTPException(404, f"Node '{node_id}' not found")
    return node.model_dump()


@router.delete("/nodes/{node_id}")
async def remove_node(
    node_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    mapper = _get_mapper()
    if not mapper.remove_node(node_id):
        raise HTTPException(404, f"Node '{node_id}' not found")
    return {"status": "removed"}


@router.post("/relationships")
async def add_relationship(
    body: AddRelationshipRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    rel = mapper.add_relationship(**body.model_dump())
    return rel.model_dump()


@router.delete("/relationships/{relationship_id}")
async def remove_relationship(
    relationship_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    mapper = _get_mapper()
    if not mapper.remove_relationship(relationship_id):
        raise HTTPException(404, f"Relationship '{relationship_id}' not found")
    return {"status": "removed"}


@router.get("/nodes/{node_id}/dependencies")
async def get_node_dependencies(
    node_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mapper = _get_mapper()
    return [n.model_dump() for n in mapper.get_node_dependencies(node_id)]


@router.get("/nodes/{node_id}/dependents")
async def get_node_dependents(
    node_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mapper = _get_mapper()
    return [n.model_dump() for n in mapper.get_node_dependents(node_id)]


@router.get("/topology")
async def get_topology_view(
    environment: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    return mapper.get_topology_view(environment=environment).model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    return mapper.get_stats()
