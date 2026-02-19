"""Alert event handler — routes Kafka alert events to the Investigation Agent.

Subscribes to ``alert.triggered`` events on the event bus and automatically
kicks off an investigation via :class:`InvestigationRunner`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from shieldops.messaging.topics import EventEnvelope
from shieldops.models.base import AlertContext

if TYPE_CHECKING:
    from datetime import datetime

    from shieldops.agents.investigation.runner import InvestigationRunner

logger = structlog.get_logger()


class AlertEventHandler:
    """Handles ``alert.triggered`` events from the Kafka event bus.

    Routes each alert to the investigation runner for automated
    root-cause analysis.  Unknown event types are logged and skipped.
    """

    def __init__(self, investigation_runner: InvestigationRunner) -> None:
        self._runner = investigation_runner

    async def handle(self, event: EventEnvelope) -> None:
        """Dispatch a single event envelope."""
        if event.event_type == "alert.triggered":
            await self._handle_alert(event)
        else:
            logger.debug(
                "alert_handler_skip",
                event_type=event.event_type,
                event_id=event.event_id,
            )

    async def _handle_alert(self, event: EventEnvelope) -> None:
        """Convert an alert event payload to AlertContext and investigate."""
        payload: dict[str, Any] = event.payload

        logger.info(
            "alert_event_received",
            event_id=event.event_id,
            alert_id=payload.get("alert_id", ""),
            alert_name=payload.get("alert_name", ""),
        )

        triggered_at = event.timestamp or datetime.now(UTC)

        alert = AlertContext(
            alert_id=payload.get("alert_id", event.event_id),
            alert_name=payload.get("alert_name", "unknown"),
            severity=payload.get("severity", "warning"),
            source=payload.get("source", event.source),
            resource_id=payload.get("resource_id", ""),
            labels=payload.get("labels", {}),
            triggered_at=triggered_at,
            description=payload.get("description", ""),
        )

        try:
            result = await self._runner.investigate(alert)
            logger.info(
                "alert_investigation_completed",
                event_id=event.event_id,
                alert_id=alert.alert_id,
                confidence=result.confidence_score,
                hypotheses=len(result.hypotheses),
            )
        except Exception as e:
            logger.error(
                "alert_investigation_failed",
                event_id=event.event_id,
                alert_id=alert.alert_id,
                error=str(e),
            )
