"""Escalation effectiveness tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.escalation_effectiveness import (
    EscalationResult,
    ResponderTier,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/escalation-effectiveness",
    tags=["Escalation Effectiveness"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Escalation effectiveness service unavailable",
        )
    return _engine


class RecordEscalationRequest(BaseModel):
    incident_id: str
    responder_id: str
    responder_tier: ResponderTier = ResponderTier.TIER_1
    result: EscalationResult = EscalationResult.RESOLVED
    ack_time_minutes: float = 5.0
    resolution_time_minutes: float = 30.0
    was_correct_target: bool = True


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
    responder_id: str | None = None,
    result: EscalationResult | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_escalations(responder_id=responder_id, result=result, limit=limit)
    ]


@router.get("/escalations/{record_id}")
async def get_escalation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rec = engine.get_escalation(record_id)
    if rec is None:
        raise HTTPException(404, f"Escalation '{record_id}' not found")
    return rec.model_dump()


@router.get("/profiles/{responder_id}")
async def build_responder_profile(
    responder_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.build_responder_profile(responder_id).model_dump()


@router.get("/effectiveness/{responder_id}")
async def calculate_effectiveness_score(
    responder_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_effectiveness_score(responder_id)


@router.get("/false-escalations")
async def identify_false_escalations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_false_escalations()


@router.get("/rankings")
async def rank_responders_by_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_responders_by_effectiveness()


@router.get("/re-escalation-patterns")
async def detect_re_escalation_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_re_escalation_patterns()


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


ee_route = router
