"""Notification integrations -- Slack, PagerDuty, and unified dispatch."""

from shieldops.integrations.notifications.base import NotificationChannel
from shieldops.integrations.notifications.dispatcher import NotificationDispatcher

__all__ = ["NotificationChannel", "NotificationDispatcher"]
