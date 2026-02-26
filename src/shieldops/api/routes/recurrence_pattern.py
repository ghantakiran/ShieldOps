"""Recurrence pattern detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.recurrence_pattern import (
    PatternStrength,
    RecurrenceFrequency,
    RecurrenceType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/recurrence-pattern",
    tags=["Recurrence Pattern"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Recurrence pattern service unavailable")
    return _engine


class RecordRecurrenceRequest(BaseModel):
    incident_id: str
    service_name: str
    recurrence_type: RecurrenceType = RecurrenceType.TIME_BASED
    frequency: RecurrenceFrequency = RecurrenceFrequency.IRREGULAR
    occurrence_count: int = 1
    pattern_strength: PatternStrength | None = None
    details: str = ""


class AddClusterRequest(BaseModel):
    cluster_name: str
    service_name: str
    incident_count: int = 0
    recurrence_type: RecurrenceType = RecurrenceType.TIME_BASED
    pattern_strength: PatternStrength = PatternStrength.INCONCLUSIVE


@router.post("/recurrences")
async def record_recurrence(
    body: RecordRecurrenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_recurrence(**body.model_dump())
    return result.model_dump()


@router.get("/recurrences")
async def list_recurrences(
    service_name: str | None = None,
    recurrence_type: RecurrenceType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_recurrences(
            service_name=service_name,
            recurrence_type=recurrence_type,
            limit=limit,
        )
    ]


@router.get("/recurrences/{record_id}")
async def get_recurrence(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_recurrence(record_id)
    if result is None:
        raise HTTPException(404, f"Recurrence '{record_id}' not found")
    return result.model_dump()


@router.post("/clusters")
async def add_cluster(
    body: AddClusterRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_cluster(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{service_name}")
async def analyze_incident_recurrence(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_incident_recurrence(service_name)


@router.get("/strong-patterns")
async def identify_strong_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_strong_patterns()


@router.get("/rankings")
async def rank_by_incident_count(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_incident_count()


@router.get("/emerging")
async def detect_emerging_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_emerging_patterns()


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


rpa_route = router
