"""Incident Blast Radius Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.blast_radius import (
    BlastRadiusScope,
    ContainmentStatus,
    ImpactVector,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/blast-radius", tags=["Blast Radius"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Blast radius service unavailable")
    return _engine


class RecordBlastRadiusRequest(BaseModel):
    incident_id: str
    blast_radius_scope: BlastRadiusScope = BlastRadiusScope.SINGLE_SERVICE
    impact_vector: ImpactVector = ImpactVector.AVAILABILITY
    containment_status: ContainmentStatus = ContainmentStatus.CONTAINED
    blast_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddImpactZoneRequest(BaseModel):
    zone_name: str
    blast_radius_scope: BlastRadiusScope = BlastRadiusScope.SINGLE_SERVICE
    impact_threshold: float = 0.0
    avg_blast_score: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_blast_radius(
    body: RecordBlastRadiusRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_blast_radius(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_blast_radii(
    scope: BlastRadiusScope | None = None,
    vector: ImpactVector | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_blast_radii(
            scope=scope,
            vector=vector,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_blast_radius(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_blast_radius(record_id)
    if result is None:
        raise HTTPException(404, f"Blast radius record '{record_id}' not found")
    return result.model_dump()


@router.post("/zones")
async def add_impact_zone(
    body: AddImpactZoneRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_impact_zone(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_blast_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_blast_patterns()


@router.get("/high-radius")
async def identify_high_radius_incidents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_radius_incidents()


@router.get("/blast-rankings")
async def rank_by_blast_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_blast_score()


@router.get("/containment-failures")
async def detect_containment_failures(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_containment_failures()


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


ibr_route = router
