"""Microsoft Teams notifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.integrations.notifications.teams import (
    CardType,
    ChannelPriority,
    DeliveryOutcome,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/teams-notifier",
    tags=["Teams Notifier"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Teams Notifier service unavailable")
    return _engine


class RecordMessageRequest(BaseModel):
    channel_name: str
    card_type: CardType = CardType.ALERT
    channel_priority: ChannelPriority = ChannelPriority.NORMAL
    delivery_outcome: DeliveryOutcome = DeliveryOutcome.DELIVERED
    message_size_bytes: int = 0
    details: str = ""


class AddCardRequest(BaseModel):
    card_label: str
    card_type: CardType = CardType.ALERT
    delivery_outcome: DeliveryOutcome = DeliveryOutcome.DELIVERED
    render_time_ms: float = 0.0


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
    channel_name: str | None = None,
    card_type: CardType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_messages(channel_name=channel_name, card_type=card_type, limit=limit)
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


@router.post("/cards")
async def add_card(
    body: AddCardRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_card(**body.model_dump())
    return result.model_dump()


@router.get("/channel-delivery/{channel_name}")
async def analyze_channel_delivery(
    channel_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_channel_delivery(channel_name)


@router.get("/failed-notifications")
async def identify_failed_notifications(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_notifications()


@router.get("/rankings")
async def rank_by_channel_volume(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_channel_volume()


@router.get("/throttling-patterns")
async def detect_throttling_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_throttling_patterns()


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


mtn_route = router
