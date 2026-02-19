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

    def __init__(
        self,
        channels: dict[str, Any] | None = None,
    ) -> None:
        self._channels: dict[str, NotificationChannel] = {}
        if channels:
            for name, ch in channels.items():
                if isinstance(ch, NotificationChannel):
                    self._channels[name] = ch

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

    async def send_notification(
        self,
        channel: str,
        subject: str,
        body: str,
        recipients: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """High-level send used by newsletter and escalation services.

        Routes to the named channel with subject/body semantics.
        Falls back to ``send`` if the channel has no ``send_notification``.
        """
        notifier = self._channels.get(channel)
        if notifier is None:
            logger.warning("notification_channel_not_found", channel=channel)
            return False

        # Try the richer send_notification if the channel supports it
        if hasattr(notifier, "send_notification"):
            return await notifier.send_notification(
                subject=subject,
                body=body,
                recipients=recipients,
                metadata=metadata,
            )

        # Fallback to basic send
        message = f"{subject}\n\n{body}"
        return await notifier.send(message=message, severity="info", details=metadata)

    async def send_to_team(
        self,
        team_id: str,
        message: str,
        severity: str = "info",
        channel: str | None = None,
    ) -> bool:
        """Send notification to a specific team's preferred channel.

        If *channel* is not specified, broadcasts to all channels.
        """
        logger.info(
            "send_to_team",
            team_id=team_id,
            severity=severity,
            channel=channel or "all",
        )
        if channel:
            return await self.send(
                channel=channel,
                message=f"[Team: {team_id}] {message}",
                severity=severity,
                details={"team_id": team_id},
            )
        results = await self.broadcast(
            message=f"[Team: {team_id}] {message}",
            severity=severity,
            details={"team_id": team_id},
        )
        return any(results.values())
