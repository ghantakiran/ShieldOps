"""Pydantic models for the notification dispatch API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class NotificationChannel(StrEnum):
    """Supported notification channels."""

    slack = "slack"
    pagerduty = "pagerduty"
    email = "email"
    webhook = "webhook"
    teams = "teams"
    sms = "sms"


class NotificationSeverity(StrEnum):
    """Notification severity levels."""

    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class NotificationRequest(BaseModel):
    """Payload for sending a notification."""

    channel: NotificationChannel
    severity: NotificationSeverity = NotificationSeverity.info
    title: str = Field(..., min_length=1, max_length=256)
    message: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelStatus(BaseModel):
    """Status of a single notification channel."""

    channel: NotificationChannel
    configured: bool = False
    last_sent_at: datetime | None = None
    error_count: int = 0


class NotificationRecord(BaseModel):
    """A historical notification entry."""

    id: str
    channel: NotificationChannel
    severity: NotificationSeverity
    title: str
    sent_at: datetime
    status: str = Field(
        default="sent",
        description="Delivery status: sent, failed, or pending.",
    )


class NotificationPreferences(BaseModel):
    """Mapping of severity to the channels that should be notified."""

    preferences: dict[NotificationSeverity, list[NotificationChannel]] = Field(
        default_factory=lambda: {
            NotificationSeverity.critical: [
                NotificationChannel.pagerduty,
                NotificationChannel.slack,
            ],
            NotificationSeverity.high: [NotificationChannel.slack],
            NotificationSeverity.medium: [NotificationChannel.email],
            NotificationSeverity.low: [NotificationChannel.email],
            NotificationSeverity.info: [NotificationChannel.webhook],
        },
    )
