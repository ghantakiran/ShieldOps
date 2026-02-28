"""Twilio voice alert system API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.integrations.notifications.twilio_voice import (
    CallPriority,
    CallStatus,
    IVRAction,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/twilio-voice",
    tags=["Twilio Voice"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Twilio Voice service unavailable")
    return _engine


class RecordCallRequest(BaseModel):
    recipient_number: str
    call_priority: CallPriority = CallPriority.HIGH
    call_status: CallStatus = CallStatus.COMPLETED
    ivr_action: IVRAction = IVRAction.ACKNOWLEDGE
    duration_seconds: float = 0.0
    details: str = ""


class AddIVRResponseRequest(BaseModel):
    response_label: str
    ivr_action: IVRAction = IVRAction.ACKNOWLEDGE
    call_status: CallStatus = CallStatus.COMPLETED
    confidence_score: float = 0.0


@router.post("/calls")
async def record_call(
    body: RecordCallRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_call(**body.model_dump())
    return result.model_dump()


@router.get("/calls")
async def list_calls(
    recipient_number: str | None = None,
    call_priority: CallPriority | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_calls(
            recipient_number=recipient_number, call_priority=call_priority, limit=limit
        )
    ]


@router.get("/calls/{record_id}")
async def get_call(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_call(record_id)
    if result is None:
        raise HTTPException(404, f"Call '{record_id}' not found")
    return result.model_dump()


@router.post("/ivr-responses")
async def add_ivr_response(
    body: AddIVRResponseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_ivr_response(**body.model_dump())
    return result.model_dump()


@router.get("/answer-rates/{recipient_number}")
async def analyze_answer_rates(
    recipient_number: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_answer_rates(recipient_number)


@router.get("/unanswered-calls")
async def identify_unanswered_calls(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unanswered_calls()


@router.get("/rankings")
async def rank_by_call_volume(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_call_volume()


@router.get("/escalation-patterns")
async def detect_escalation_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_escalation_patterns()


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


tva_route = router
