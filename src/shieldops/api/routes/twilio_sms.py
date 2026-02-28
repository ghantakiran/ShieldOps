"""Twilio SMS gateway API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.integrations.notifications.twilio_sms import (
    DeliveryStatus,
    MessageType,
    SMSPriority,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/twilio-sms",
    tags=["Twilio SMS"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Twilio SMS service unavailable")
    return _engine


class RecordMessageRequest(BaseModel):
    recipient_number: str
    priority: SMSPriority = SMSPriority.MEDIUM
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    message_type: MessageType = MessageType.ALERT
    character_count: int = 0
    details: str = ""


class AddReceiptRequest(BaseModel):
    receipt_id: str
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    message_type: MessageType = MessageType.ALERT
    latency_ms: float = 0.0


@router.post("/messages")
async def record_message(
    body: RecordMessageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_message(**body.model_dump())
    return result.model_dump()


@router.get("/messages")
async def list_messages(
    recipient_number: str | None = None,
    priority: SMSPriority | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_messages(
            recipient_number=recipient_number, priority=priority, limit=limit
        )
    ]


@router.get("/messages/{record_id}")
async def get_message(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_message(record_id)
    if result is None:
        raise HTTPException(404, f"Message '{record_id}' not found")
    return result.model_dump()


@router.post("/receipts")
async def add_receipt(
    body: AddReceiptRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_receipt(**body.model_dump())
    return result.model_dump()


@router.get("/delivery-performance/{recipient_number}")
async def analyze_delivery_performance(
    recipient_number: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_delivery_performance(recipient_number)


@router.get("/failed-deliveries")
async def identify_failed_deliveries(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_deliveries()


@router.get("/rankings")
async def rank_by_message_volume(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_message_volume()


@router.get("/opt-out-patterns")
async def detect_opt_out_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_opt_out_patterns()


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


tsg_route = router
