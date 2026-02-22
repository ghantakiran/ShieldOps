"""Service topology API endpoints.

Provides routes for querying the service dependency graph,
ingesting topology data from traces, K8s, and manual config,
and running graph analysis (cycles, paths).
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from shieldops.topology.graph import ServiceGraphBuilder

logger = structlog.get_logger()

router = APIRouter(prefix="/topology", tags=["Topology"])

_builder: ServiceGraphBuilder | None = None


def set_builder(builder: ServiceGraphBuilder | None) -> None:
    """Wire the ServiceGraphBuilder instance into this route module."""
    global _builder
    _builder = builder


def _get_builder() -> ServiceGraphBuilder:
    if _builder is None:
        raise HTTPException(503, "Topology service unavailable")
    return _builder


# ── Request Models ───────────────────────────────────────────────


class TraceIngestRequest(BaseModel):
    """Request body for ingesting OpenTelemetry trace data."""

    traces: list[dict[str, Any]]


class K8sIngestRequest(BaseModel):
    """Request body for ingesting Kubernetes service data."""

    services: list[dict[str, Any]]


class DeclareRequest(BaseModel):
    """Request body for manually declaring dependencies."""

    declarations: list[dict[str, Any]]


# ── Endpoints ────────────────────────────────────────────────────


@router.get("/map")
async def get_service_map() -> dict[str, Any]:
    """Return the full service dependency map."""
    builder = _get_builder()
    smap = builder.get_map()
    return smap.model_dump(mode="json")


@router.get("/service/{service_id}/dependencies")
async def get_service_dependencies(
    service_id: str,
    transitive: bool = Query(default=False),
) -> dict[str, Any]:
    """Return dependencies for a specific service."""
    builder = _get_builder()
    view = builder.get_dependencies(service_id, include_transitive=transitive)
    return view.model_dump(mode="json")


@router.post("/traces")
async def ingest_traces(body: TraceIngestRequest) -> dict[str, Any]:
    """Ingest OpenTelemetry trace data and update the topology graph."""
    builder = _get_builder()
    new_edges = builder.merge_from_traces(body.traces)
    logger.info("traces_ingested_via_api", new_edges=new_edges)
    return {"new_edges": new_edges}


@router.post("/k8s")
async def ingest_k8s(body: K8sIngestRequest) -> dict[str, Any]:
    """Ingest Kubernetes service discovery data."""
    builder = _get_builder()
    new_nodes = builder.merge_from_k8s(body.services)
    logger.info("k8s_ingested_via_api", new_nodes=new_nodes)
    return {"new_nodes": new_nodes}


@router.post("/declare")
async def declare_dependencies(body: DeclareRequest) -> dict[str, Any]:
    """Manually declare service dependencies."""
    builder = _get_builder()
    new_edges = builder.merge_from_config(body.declarations)
    logger.info("declarations_ingested_via_api", new_edges=new_edges)
    return {"new_edges": new_edges}


@router.get("/cycles")
async def detect_cycles() -> dict[str, Any]:
    """Detect circular dependencies in the service graph."""
    builder = _get_builder()
    cycles = builder.detect_cycles()
    return {"cycles": cycles, "count": len(cycles)}


@router.get("/path")
async def find_path(
    source: str = Query(..., description="Source service ID"),
    target: str = Query(..., description="Target service ID"),
) -> dict[str, Any]:
    """Find the shortest path between two services."""
    builder = _get_builder()
    path = builder.get_critical_path(source, target)
    if path is None:
        return {"path": None, "hops": 0, "found": False}
    return {"path": path, "hops": len(path) - 1, "found": True}
