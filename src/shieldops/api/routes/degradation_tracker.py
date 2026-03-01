"""Service Degradation Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.degradation_tracker import (
    DegradationSeverity,
    DegradationType,
    RecoveryMethod,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/degradation-tracker", tags=["Degradation Tracker"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Degradation tracker service unavailable")
    return _engine


class RecordDegradationRequest(BaseModel):
    degradation_id: str
    degradation_type: DegradationType = DegradationType.LATENCY_SPIKE
    degradation_severity: DegradationSeverity = DegradationSeverity.MINOR
    recovery_method: RecoveryMethod = RecoveryMethod.AUTO_HEAL
    duration_minutes: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddEventRequest(BaseModel):
    degradation_id: str
    degradation_type: DegradationType = DegradationType.LATENCY_SPIKE
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_degradation(
    body: RecordDegradationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_degradation(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_degradations(
    dtype: DegradationType | None = None,
    severity: DegradationSeverity | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_degradations(
            dtype=dtype,
            severity=severity,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_degradation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_degradation(record_id)
    if result is None:
        raise HTTPException(404, f"Degradation record '{record_id}' not found")
    return result.model_dump()


@router.post("/events")
async def add_event(
    body: AddEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_event(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_degradation_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_degradation_patterns()


@router.get("/frequent-degradations")
async def identify_frequent_degradations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_frequent_degradations()


@router.get("/duration-rankings")
async def rank_by_duration(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_duration()


@router.get("/trends")
async def detect_degradation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_degradation_trends()


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


sdg_route = router
