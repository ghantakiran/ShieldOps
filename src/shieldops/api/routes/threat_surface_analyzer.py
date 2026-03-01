"""Threat Surface Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.threat_surface_analyzer import (
    MitigationStatus,
    SurfaceVector,
    ThreatLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/threat-surface-analyzer",
    tags=["Threat Surface Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Threat surface analyzer service unavailable")
    return _engine


class RecordSurfaceRequest(BaseModel):
    surface_id: str
    surface_vector: SurfaceVector = SurfaceVector.NETWORK_EXPOSURE
    threat_level: ThreatLevel = ThreatLevel.MODERATE
    mitigation_status: MitigationStatus = MitigationStatus.UNMITIGATED
    exposure_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    surface_id: str
    surface_vector: SurfaceVector = SurfaceVector.NETWORK_EXPOSURE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/surfaces")
async def record_surface(
    body: RecordSurfaceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_surface(**body.model_dump())
    return result.model_dump()


@router.get("/surfaces")
async def list_surfaces(
    surface_vector: SurfaceVector | None = None,
    threat_level: ThreatLevel | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_surfaces(
            surface_vector=surface_vector,
            threat_level=threat_level,
            team=team,
            limit=limit,
        )
    ]


@router.get("/surfaces/{record_id}")
async def get_surface(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_surface(record_id)
    if result is None:
        raise HTTPException(404, f"Surface '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_surface_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_surface_distribution()


@router.get("/exposed-surfaces")
async def identify_exposed_surfaces(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_exposed_surfaces()


@router.get("/exposure-rankings")
async def rank_by_exposure(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_exposure()


@router.get("/trends")
async def detect_surface_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_surface_trends()


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


tsx_route = router
