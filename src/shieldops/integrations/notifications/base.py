"""Protocol definition for notification channels."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class NotificationChannel(Protocol):
    """Protocol for notification channel implementations.

    Any class that implements ``send`` and ``send_escalation`` with the
    signatures below satisfies this protocol -- no inheritance required.
    """

    async def send(
        self,
        message: str,
        severity: str = "info",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send a notification. Returns True if successful."""
        ...

    async def send_escalation(
        self,
        title: str,
        description: str,
        severity: str = "high",
        source: str = "shieldops",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send an escalation notification. Returns True if successful."""
        ...
