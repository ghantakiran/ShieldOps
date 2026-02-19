"""Notification integrations -- Slack, PagerDuty, Email, and unified dispatch."""

from shieldops.integrations.notifications.base import NotificationChannel
from shieldops.integrations.notifications.dispatcher import NotificationDispatcher
from shieldops.integrations.notifications.email import EmailNotifier

__all__ = ["EmailNotifier", "NotificationChannel", "NotificationDispatcher"]
