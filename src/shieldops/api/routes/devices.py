"""API routes for mobile device registration and push notifications."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()
router = APIRouter()

_push_notifier: Any | None = None


def set_push_notifier(notifier: Any) -> None:
    global _push_notifier
    _push_notifier = notifier


class RegisterDeviceRequest(BaseModel):
    token: str
    platform: str = "ios"  # ios, android, web
    topics: list[str] = Field(default_factory=lambda: ["alerts"])


class UpdateTopicsRequest(BaseModel):
    topics: list[str]


@router.post("/devices/register")
async def register_device(
    request: RegisterDeviceRequest,
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Register a device for push notifications."""
    if not _push_notifier:
        raise HTTPException(status_code=503, detail="Push notifications not configured")

    valid_platforms = {"ios", "android", "web"}
    if request.platform not in valid_platforms:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform. Must be one of: {valid_platforms}",
        )

    device = _push_notifier.register_device(
        user_id=user.id,
        token=request.token,
        platform=request.platform,
        topics=request.topics,
    )
    return {"device": device.to_dict()}


@router.delete("/devices/{device_id}")
async def unregister_device(
    device_id: str,
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Unregister a device."""
    if not _push_notifier:
        raise HTTPException(status_code=503, detail="Push notifications not configured")

    device = _push_notifier.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your device")

    _push_notifier.unregister_device(device_id)
    return {"deleted": True}


@router.get("/devices")
async def list_devices(
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List devices registered to the current user."""
    if not _push_notifier:
        return {"devices": [], "total": 0}
    devices = _push_notifier.list_devices(user_id=user.id)
    return {
        "devices": [d.to_dict() for d in devices],
        "total": len(devices),
    }


@router.put("/devices/{device_id}/topics")
async def update_device_topics(
    device_id: str,
    request: UpdateTopicsRequest,
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Update topic subscriptions for a device."""
    if not _push_notifier:
        raise HTTPException(status_code=503, detail="Push notifications not configured")

    device = _push_notifier.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your device")

    updated = _push_notifier.update_topics(device_id, request.topics)
    return {"device": updated.to_dict() if updated else {}}
