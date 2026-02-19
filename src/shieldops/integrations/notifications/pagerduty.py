"""PagerDuty notification channel via Events API v2."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

PAGERDUTY_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"

# PagerDuty enforces a 1 024-character limit on the summary field.
_PD_SUMMARY_LIMIT = 1024


class PagerDutyNotifier:
    """Send alerts to PagerDuty via Events API v2.

    Implements the :class:`NotificationChannel` protocol so it can be
    registered with :class:`NotificationDispatcher`.
    """

    def __init__(self, routing_key: str, *, timeout: float = 10.0) -> None:
        self._routing_key = routing_key
        self._timeout = timeout

    # ------------------------------------------------------------------
    # NotificationChannel protocol
    # ------------------------------------------------------------------

    async def send(
        self,
        message: str,
        severity: str = "info",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send an info/warning event to PagerDuty."""
        return await self._send_event(
            event_action="trigger",
            summary=message,
            severity=self._map_severity(severity),
            custom_details=details,
        )

    async def send_escalation(
        self,
        title: str,
        description: str,
        severity: str = "high",
        source: str = "shieldops",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Trigger a PagerDuty incident for escalation."""
        custom_details = {**(details or {}), "description": description}
        return await self._send_event(
            event_action="trigger",
            summary=title,
            severity=self._map_severity(severity),
            source=source,
            custom_details=custom_details,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send_event(
        self,
        event_action: str,
        summary: str,
        severity: str = "warning",
        source: str = "shieldops",
        custom_details: dict[str, Any] | None = None,
    ) -> bool:
        """Build and POST a PagerDuty Events API v2 payload."""
        payload: dict[str, Any] = {
            "routing_key": self._routing_key,
            "event_action": event_action,
            "payload": {
                "summary": summary[:_PD_SUMMARY_LIMIT],
                "severity": severity,
                "source": source,
                "custom_details": custom_details or {},
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(PAGERDUTY_EVENTS_URL, json=payload)
                success = resp.status_code in (200, 201, 202)
                if not success:
                    logger.warning(
                        "pagerduty_send_failed",
                        status=resp.status_code,
                        body=resp.text[:200],
                    )
                else:
                    logger.info(
                        "pagerduty_event_sent",
                        action=event_action,
                        summary=summary[:80],
                    )
                return success
        except httpx.HTTPError as exc:
            logger.error("pagerduty_http_error", error=str(exc))
            return False
        except Exception as exc:
            logger.error("pagerduty_error", error=str(exc))
            return False

    @staticmethod
    def _map_severity(severity: str) -> str:
        """Map ShieldOps severity labels to PagerDuty severity values."""
        mapping: dict[str, str] = {
            "low": "info",
            "info": "info",
            "medium": "warning",
            "warning": "warning",
            "high": "error",
            "critical": "critical",
        }
        return mapping.get(severity.lower(), "warning")
