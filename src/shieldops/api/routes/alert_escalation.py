"""Alert escalation analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.escalation_analyzer import (
    EscalationLevel,
    EscalationOutcome,
    EscalationReason,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/alert-escalation",
    tags=["Alert Escalation"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Alert escalation service unavailable")
    return _engine


class RecordEscalationRequest(BaseModel):
    alert_id: str
    from_level: EscalationLevel = EscalationLevel.L1_INITIAL
    to_level: EscalationLevel = EscalationLevel.L2_ENGINEERING
    reason: EscalationReason = EscalationReason.TIMEOUT
    outcome: EscalationOutcome = EscalationOutcome.RESOLVED
    team: str = ""
    escalation_time_minutes: float = 0.0
    details: str = ""

    model_config = {"extra": "forbid"}


class AddPatternRequest(BaseModel):
    alert_type: str
    avg_escalation_time: float = 0.0
    escalation_count: int = 0
    resolution_level: EscalationLevel = EscalationLevel.L1_INITIAL

    model_config = {"extra": "forbid"}


@router.post("/escalations")
async def record_escalation(
    body: RecordEscalationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_escalation(**body.model_dump())
    return result.model_dump()


@router.get("/escalations")
async def list_escalations(
    level: EscalationLevel | None = None,
    reason: EscalationReason | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_escalations(level=level, reason=reason, team=team, limit=limit)
    ]


@router.get("/escalations/{record_id}")
async def get_escalation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_escalation(record_id)
    if result is None:
        raise HTTPException(404, f"Escalation '{record_id}' not found")
    return result.model_dump()


@router.post("/patterns")
async def add_pattern(
    body: AddPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/by-level")
async def analyze_by_level(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_escalation_by_level()


@router.get("/frequent")
async def identify_frequent(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_frequent_escalations()


@router.get("/rankings")
async def rank_by_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_escalation_time()


@router.get("/trends")
async def detect_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_escalation_trends()


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


ean_route = router
