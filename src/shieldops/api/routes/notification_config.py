"""CRUD endpoints for team notification configuration."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from shieldops.db.models import TeamNotificationConfigRecord

router = APIRouter()
logger = structlog.get_logger()

_session_factory = None


def set_session_factory(sf: Any) -> None:
    global _session_factory
    _session_factory = sf


class NotificationConfigCreate(BaseModel):
    channel_type: str = Field(description="slack, pagerduty, email, webhook")
    channel_name: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class NotificationConfigUpdate(BaseModel):
    channel_name: str | None = None
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class NotificationConfigResponse(BaseModel):
    id: str
    channel_type: str
    channel_name: str
    enabled: bool
    config: dict[str, Any]
    created_at: str
    updated_at: str


def _record_to_response(r: TeamNotificationConfigRecord) -> dict[str, Any]:
    return {
        "id": r.id,
        "channel_type": r.channel_type,
        "channel_name": r.channel_name,
        "enabled": r.enabled,
        "config": r.config or {},
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
    }


@router.get("/notification-configs")
async def list_notification_configs() -> list[dict[str, Any]]:
    """List all notification channel configurations."""
    if _session_factory is None:
        return []
    async with _session_factory() as session:
        stmt = select(TeamNotificationConfigRecord).order_by(
            TeamNotificationConfigRecord.created_at.desc()
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        return [_record_to_response(r) for r in records]


@router.post("/notification-configs", status_code=201)
async def create_notification_config(body: NotificationConfigCreate) -> dict[str, Any]:
    """Create a new notification channel configuration."""
    if _session_factory is None:
        raise HTTPException(status_code=503, detail="Database not available")
    async with _session_factory() as session:
        record = TeamNotificationConfigRecord(
            channel_type=body.channel_type,
            channel_name=body.channel_name,
            enabled=body.enabled,
            config=body.config,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        logger.info("notification_config_created", id=record.id, type=body.channel_type)
        return _record_to_response(record)


@router.put("/notification-configs/{config_id}")
async def update_notification_config(
    config_id: str, body: NotificationConfigUpdate
) -> dict[str, Any]:
    """Update an existing notification configuration."""
    if _session_factory is None:
        raise HTTPException(status_code=503, detail="Database not available")
    async with _session_factory() as session:
        record = await session.get(TeamNotificationConfigRecord, config_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Config not found")
        if body.channel_name is not None:
            record.channel_name = body.channel_name
        if body.enabled is not None:
            record.enabled = body.enabled
        if body.config is not None:
            record.config = body.config
        await session.commit()
        await session.refresh(record)
        logger.info("notification_config_updated", id=config_id)
        return _record_to_response(record)


@router.delete("/notification-configs/{config_id}")
async def delete_notification_config(config_id: str) -> dict[str, str]:
    """Delete a notification configuration."""
    if _session_factory is None:
        raise HTTPException(status_code=503, detail="Database not available")
    async with _session_factory() as session:
        record = await session.get(TeamNotificationConfigRecord, config_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Config not found")
        await session.delete(record)
        await session.commit()
        logger.info("notification_config_deleted", id=config_id)
        return {"status": "deleted", "id": config_id}
