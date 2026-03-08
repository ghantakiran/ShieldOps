"""API routes for dispatching notifications to configured channels.

Connects the unified :class:`NotificationDispatcher` to pipeline and
workflow events via a RESTful interface.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException

from shieldops.api.routes.notification_models import (
    ChannelStatus,
    NotificationChannel,
    NotificationPreferences,
    NotificationRecord,
    NotificationRequest,
    NotificationSeverity,
)
from shieldops.integrations.notifications.dispatcher import (
    NotificationDispatcher,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = structlog.get_logger()

# -----------------------------------------------------------------
# Module-level state — wired at application startup
# -----------------------------------------------------------------

_dispatcher: NotificationDispatcher | None = None
_preferences: dict[NotificationSeverity, list[NotificationChannel]] = {
    NotificationSeverity.critical: [
        NotificationChannel.pagerduty,
        NotificationChannel.slack,
    ],
    NotificationSeverity.high: [NotificationChannel.slack],
    NotificationSeverity.medium: [NotificationChannel.email],
    NotificationSeverity.low: [NotificationChannel.email],
    NotificationSeverity.info: [NotificationChannel.webhook],
}
_history: list[dict[str, Any]] = []


def set_dispatcher(dispatcher: NotificationDispatcher) -> None:
    """Inject a :class:`NotificationDispatcher` at startup."""
    global _dispatcher
    _dispatcher = dispatcher
    logger.info("notification_dispatch_router_configured")


def _get_dispatcher() -> NotificationDispatcher:
    if _dispatcher is None:
        raise HTTPException(
            status_code=503,
            detail="Notification dispatcher not configured",
        )
    return _dispatcher


def _record_history(
    channel: NotificationChannel,
    severity: NotificationSeverity,
    title: str,
    status: str,
) -> None:
    """Append a notification to the in-memory history buffer."""
    _history.append(
        {
            "id": uuid.uuid4().hex,
            "channel": channel,
            "severity": severity,
            "title": title,
            "sent_at": datetime.now(tz=UTC).isoformat(),
            "status": status,
        }
    )
    # Keep only the last 200 entries
    if len(_history) > 200:
        _history[:] = _history[-200:]


# -----------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------


@router.post("/send")
async def send_notification(
    body: NotificationRequest,
) -> dict[str, Any]:
    """Send a notification to the specified channel.

    Delegates to the underlying :class:`NotificationDispatcher` which
    routes to the registered channel implementation (Slack, PagerDuty,
    email, webhook, Teams, SMS, etc.).
    """
    dispatcher = _get_dispatcher()

    logger.info(
        "notification_send_requested",
        channel=body.channel.value,
        severity=body.severity.value,
        title=body.title,
    )

    details = {
        "title": body.title,
        "severity": body.severity.value,
        **body.metadata,
    }

    ok = await dispatcher.send(
        channel=body.channel.value,
        message=f"[{body.severity.value.upper()}] {body.title}\n\n{body.message}",
        severity=body.severity.value,
        details=details,
    )

    status = "sent" if ok else "failed"
    _record_history(body.channel, body.severity, body.title, status)

    if not ok:
        logger.warning(
            "notification_send_failed",
            channel=body.channel.value,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to deliver notification via {body.channel.value}",
        )

    return {
        "status": "sent",
        "channel": body.channel.value,
        "severity": body.severity.value,
        "title": body.title,
    }


@router.get("/channels")
async def list_channels() -> list[ChannelStatus]:
    """List available notification channels with their status."""
    dispatcher = _get_dispatcher()
    registered = dispatcher.channels

    statuses: list[ChannelStatus] = []
    for ch in NotificationChannel:
        # Find last history entry for this channel
        last_sent: datetime | None = None
        error_count = 0
        for entry in reversed(_history):
            if entry["channel"] == ch:
                if last_sent is None:
                    last_sent = datetime.fromisoformat(entry["sent_at"])
                if entry["status"] == "failed":
                    error_count += 1

        statuses.append(
            ChannelStatus(
                channel=ch,
                configured=ch.value in registered,
                last_sent_at=last_sent,
                error_count=error_count,
            )
        )

    return statuses


@router.post("/test")
async def test_channel(
    body: NotificationRequest,
) -> dict[str, Any]:
    """Send a test notification to verify channel configuration.

    Uses the same dispatch path as ``/send`` but marks the message as a
    connectivity test.
    """
    dispatcher = _get_dispatcher()

    test_message = (
        f"[TEST] {body.title}\n\n"
        "This is a test notification from ShieldOps to verify "
        f"channel configuration for {body.channel.value}."
    )

    logger.info(
        "notification_test_requested",
        channel=body.channel.value,
    )

    ok = await dispatcher.send(
        channel=body.channel.value,
        message=test_message,
        severity=body.severity.value,
        details={"test": True, **body.metadata},
    )

    status = "sent" if ok else "failed"
    _record_history(body.channel, body.severity, f"[TEST] {body.title}", status)

    return {
        "status": status,
        "channel": body.channel.value,
        "message": (
            "Test notification delivered successfully"
            if ok
            else "Test notification failed — check channel configuration"
        ),
    }


@router.get("/history")
async def list_history(
    limit: int = 50,
    channel: NotificationChannel | None = None,
    severity: NotificationSeverity | None = None,
) -> list[NotificationRecord]:
    """Return recent notification history.

    Results are ordered newest-first. Use query params to filter by
    *channel* and/or *severity*.
    """
    items = list(reversed(_history))

    if channel is not None:
        items = [i for i in items if i["channel"] == channel]
    if severity is not None:
        items = [i for i in items if i["severity"] == severity]

    items = items[:limit]

    return [
        NotificationRecord(
            id=i["id"],
            channel=i["channel"],
            severity=i["severity"],
            title=i["title"],
            sent_at=datetime.fromisoformat(i["sent_at"]),
            status=i["status"],
        )
        for i in items
    ]


@router.put("/preferences")
async def update_preferences(
    body: NotificationPreferences,
) -> dict[str, Any]:
    """Update notification routing preferences per severity.

    When a pipeline or workflow event fires, the platform uses these
    preferences to decide which channels receive the notification.
    """
    global _preferences
    _preferences = dict(body.preferences)

    logger.info(
        "notification_preferences_updated",
        preferences={
            sev.value: [ch.value for ch in channels] for sev, channels in _preferences.items()
        },
    )

    return {
        "status": "updated",
        "preferences": {
            sev.value: [ch.value for ch in channels] for sev, channels in _preferences.items()
        },
    }
