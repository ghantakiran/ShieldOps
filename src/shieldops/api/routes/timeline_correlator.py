"""Timeline correlator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.timeline_correlator import (
    CorrelationStrength,
    EventType,
    TimelinePhase,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/timeline-correlator",
    tags=["Timeline Correlator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Timeline correlator service unavailable",
        )
    return _engine


class RecordCorrelationRequest(BaseModel):
    incident_name: str
    event_type: EventType = EventType.ALERT_FIRED
    strength: CorrelationStrength = CorrelationStrength.MODERATE
    phase: TimelinePhase = TimelinePhase.DETECTION
    confidence_pct: float = 0.0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    event_type: EventType = EventType.ALERT_FIRED
    phase: TimelinePhase = TimelinePhase.DETECTION
    min_confidence_pct: float = 60.0
    time_window_minutes: float = 30.0


@router.post("/correlations")
async def record_correlation(
    body: RecordCorrelationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_correlation(**body.model_dump())
    return result.model_dump()


@router.get("/correlations")
async def list_correlations(
    incident_name: str | None = None,
    event_type: EventType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_correlations(
            incident_name=incident_name,
            event_type=event_type,
            limit=limit,
        )
    ]


@router.get("/correlations/{record_id}")
async def get_correlation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_correlation(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Correlation '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/quality/{incident_name}")
async def analyze_correlation_quality(
    incident_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_correlation_quality(incident_name)


@router.get("/weak-correlations")
async def identify_weak_correlations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_weak_correlations()


@router.get("/rankings")
async def rank_by_confidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_confidence()


@router.get("/correlation-gaps")
async def detect_correlation_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_correlation_gaps()


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


itc_route = router
