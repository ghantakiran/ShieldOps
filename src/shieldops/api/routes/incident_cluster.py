"""Incident Cluster Engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.incident_cluster import (
    ClusterMethod,
    ClusterSize,
    ClusterStatus,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/incident-cluster", tags=["Incident Cluster"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Incident cluster service unavailable")
    return _engine


class RecordClusterRequest(BaseModel):
    incident_id: str
    cluster_method: ClusterMethod = ClusterMethod.SYMPTOM
    cluster_size: ClusterSize = ClusterSize.SINGLE
    cluster_status: ClusterStatus = ClusterStatus.FORMING
    confidence_score: float = 0.0
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddMemberRequest(BaseModel):
    cluster_id: str
    incident_id: str
    similarity_score: float = 0.0
    model_config = {"extra": "forbid"}


@router.post("/clusters")
async def record_cluster(
    body: RecordClusterRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_cluster(**body.model_dump())
    return result.model_dump()


@router.get("/clusters")
async def list_clusters(
    method: ClusterMethod | None = None,
    size: ClusterSize | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_clusters(method=method, size=size, team=team, limit=limit)
    ]


@router.get("/clusters/{record_id}")
async def get_cluster(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_cluster(record_id)
    if result is None:
        raise HTTPException(404, f"Cluster '{record_id}' not found")
    return result.model_dump()


@router.post("/members")
async def add_member(
    body: AddMemberRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_member(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_cluster_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_cluster_patterns()


@router.get("/storms")
async def identify_incident_storms(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_incident_storms()


@router.get("/confidence-rankings")
async def rank_by_confidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_confidence()


@router.get("/trends")
async def detect_cluster_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_cluster_trends()


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


icr_route = router
