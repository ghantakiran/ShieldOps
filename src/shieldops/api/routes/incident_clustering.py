"""Incident clustering API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/incident-clustering", tags=["Incident Clustering"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Incident clustering service unavailable")
    return _engine


class IngestIncidentRequest(BaseModel):
    service: str
    title: str
    symptoms: list[str] = Field(default_factory=list)
    error_pattern: str = ""
    severity: str = "medium"


class RunClusteringRequest(BaseModel):
    similarity_threshold: float = 0.4


@router.post("/incidents")
async def ingest_incident(
    body: IngestIncidentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.add_incident(
        title=body.title,
        service=body.service,
        symptoms=body.symptoms,
        error_pattern=body.error_pattern,
        severity=body.severity,
    )
    return record.model_dump()


@router.post("/cluster")
async def run_clustering(
    body: RunClusteringRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    prev_threshold = engine.similarity_threshold
    engine.similarity_threshold = body.similarity_threshold
    clusters = engine.auto_cluster()
    engine.similarity_threshold = prev_threshold
    return [c.model_dump() for c in clusters]


@router.get("/clusters")
async def list_clusters(
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [c.model_dump() for c in engine.list_clusters(status=status)]


@router.get("/clusters/{cluster_id}")
async def get_cluster(
    cluster_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    cluster = engine.get_cluster(cluster_id)
    if cluster is None:
        raise HTTPException(404, f"Cluster '{cluster_id}' not found")
    return cluster.model_dump()


@router.get("/incidents")
async def list_incidents(
    service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    all_incidents = list(engine._incidents.values())
    if service is not None:
        all_incidents = [i for i in all_incidents if i.service == service]
    return [i.model_dump() for i in all_incidents[:limit]]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
