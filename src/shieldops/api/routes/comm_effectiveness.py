"""Communication effectiveness analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.comm_effectiveness import (
    AudienceType,
    ChannelType,
    DeliveryStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/comm-effectiveness",
    tags=["Communication Effectiveness"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Communication effectiveness service unavailable")
    return _engine


class RecordDeliveryRequest(BaseModel):
    incident_id: str
    channel: ChannelType = ChannelType.SLACK
    audience: AudienceType = AudienceType.ENGINEERING
    status: DeliveryStatus = DeliveryStatus.DELIVERED
    delivery_time_seconds: float = 0.0
    ack_time_seconds: float = 0.0
    details: str = ""


class RecordChannelMetricsRequest(BaseModel):
    channel: ChannelType = ChannelType.SLACK
    delivery_rate_pct: float = 0.0
    avg_ack_time_seconds: float = 0.0
    total_sent: int = 0
    total_missed: int = 0
    details: str = ""


@router.post("/deliveries")
async def record_delivery(
    body: RecordDeliveryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_delivery(**body.model_dump())
    return result.model_dump()


@router.get("/deliveries")
async def list_deliveries(
    incident_id: str | None = None,
    channel: ChannelType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_deliveries(incident_id=incident_id, channel=channel, limit=limit)
    ]


@router.get("/deliveries/{record_id}")
async def get_delivery(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_delivery(record_id)
    if result is None:
        raise HTTPException(404, f"Delivery record '{record_id}' not found")
    return result.model_dump()


@router.post("/channel-metrics")
async def record_channel_metrics(
    body: RecordChannelMetricsRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_channel_metrics(**body.model_dump())
    return result.model_dump()


@router.get("/channel/{channel}")
async def analyze_channel_effectiveness(
    channel: ChannelType,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_channel_effectiveness(channel)


@router.get("/underperforming")
async def identify_underperforming_channels(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_underperforming_channels()


@router.get("/ack-time")
async def rank_channels_by_ack_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_channels_by_ack_time()


@router.get("/gaps")
async def detect_communication_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_communication_gaps()


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


cef_route = router
