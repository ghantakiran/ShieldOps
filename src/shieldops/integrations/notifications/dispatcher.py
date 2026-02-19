"""Unified notification dispatcher -- routes to channels by name."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from shieldops.integrations.notifications.base import NotificationChannel

logger = structlog.get_logger()


class NotificationDispatcher:
    """Routes notifications to registered channels (slack, pagerduty, etc.).

    Provides single-channel ``send`` / ``send_escalation`` as well as
    ``broadcast`` to fan-out to every registered channel concurrently.
    """

    def __init__(self) -> None:
        self._channels: dict[str, NotificationChannel] = {}

    # ------------------------------------------------------------------
    # Channel management
    # ------------------------------------------------------------------

    def register(self, name: str, channel: NotificationChannel) -> None:
        """Register a notification channel under *name*."""
        self._channels[name] = channel
        logger.info("notification_channel_registered", channel=name)

    def unregister(self, name: str) -> bool:
        """Remove a channel by name. Returns True if it existed."""
        removed = self._channels.pop(name, None) is not None
        if removed:
            logger.info("notification_channel_unregistered", channel=name)
        return removed

    @property
    def channels(self) -> list[str]:
        """Return the list of registered channel names."""
        return list(self._channels.keys())

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def send(
        self,
        channel: str,
        message: str,
        severity: str = "info",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send a notification to a single *channel*."""
        notifier = self._channels.get(channel)
        if notifier is None:
            logger.warning("notification_channel_not_found", channel=channel)
            return False
        return await notifier.send(message=message, severity=severity, details=details)

    async def send_escalation(
        self,
        channel: str,
        title: str,
        description: str,
        severity: str = "high",
        source: str = "shieldops",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send an escalation notification to a single *channel*."""
        notifier = self._channels.get(channel)
        if notifier is None:
            logger.warning("notification_channel_not_found", channel=channel)
            return False
        return await notifier.send_escalation(
            title=title,
            description=description,
            severity=severity,
            source=source,
            details=details,
        )

    async def broadcast(
        self,
        message: str,
        severity: str = "info",
        details: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """Fan-out *message* to every registered channel concurrently.

        Returns a mapping of channel name to delivery success.
        """
        if not self._channels:
            return {}

        async def _send_one(name: str, ch: NotificationChannel) -> tuple[str, bool]:
            try:
                ok = await ch.send(message=message, severity=severity, details=details)
            except Exception as exc:
                logger.error("broadcast_channel_error", channel=name, error=str(exc))
                ok = False
            return name, ok

        tasks = [_send_one(name, ch) for name, ch in self._channels.items()]
        results = await asyncio.gather(*tasks)
        return dict(results)
