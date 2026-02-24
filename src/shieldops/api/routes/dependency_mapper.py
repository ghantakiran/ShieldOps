"""Dependency mapper API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.dependency_mapper import (
    DependencyCriticality,
    DependencyType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dependency-mapper",
    tags=["Dependency Mapper"],
)

_mapper: Any = None


def set_mapper(mapper: Any) -> None:
    global _mapper
    _mapper = mapper


def _get_mapper() -> Any:
    if _mapper is None:
        raise HTTPException(
            503,
            "Dependency mapper service unavailable",
        )
    return _mapper


class RegisterDependencyRequest(BaseModel):
    source_service: str
    target_service: str
    dependency_type: DependencyType = DependencyType.SYNC_HTTP
    criticality: DependencyCriticality = DependencyCriticality.MEDIUM
    latency_ms: float = 0.0
    failure_rate_pct: float = 0.0


@router.post("/dependencies")
async def register_dependency(
    body: RegisterDependencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    edge = mapper.register_dependency(**body.model_dump())
    return edge.model_dump()


@router.get("/dependencies")
async def list_dependencies(
    source: str | None = None,
    target: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mapper = _get_mapper()
    return [
        e.model_dump() for e in mapper.list_dependencies(source=source, target=target, limit=limit)
    ]


@router.get("/dependencies/{edge_id}")
async def get_dependency(
    edge_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    edge = mapper.get_dependency(edge_id)
    if edge is None:
        raise HTTPException(404, f"Dependency '{edge_id}' not found")
    return edge.model_dump()


@router.post("/graph")
async def build_graph(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    return mapper.build_graph().model_dump()


@router.get("/cycles")
async def detect_cycles(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[list[str]]:
    mapper = _get_mapper()
    return mapper.detect_cycles()


@router.get("/critical-path/{service_name}")
async def get_critical_path(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[str]:
    mapper = _get_mapper()
    return mapper.find_critical_path(service_name)


@router.get("/single-points")
async def get_single_points(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[str]:
    mapper = _get_mapper()
    return mapper.identify_single_points()


@router.get("/blast-radius/{service_name}")
async def get_blast_radius(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    return mapper.calculate_blast_radius(service_name)


@router.get("/report")
async def get_map_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    return mapper.generate_map_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    return mapper.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    mapper = _get_mapper()
    return mapper.clear_data()
