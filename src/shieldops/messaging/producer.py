"""Async Kafka producer for publishing ShieldOps events."""

from __future__ import annotations

from typing import Any

import structlog
from aiokafka import AIOKafkaProducer

from shieldops.messaging.topics import (
    AGENT_RESULTS_TOPIC,
    AUDIT_TOPIC,
    EVENTS_TOPIC,
    EventEnvelope,
    serialize_event,
)

logger = structlog.get_logger()


class EventProducer:
    """Publishes ``EventEnvelope`` messages to Kafka topics.

    The producer is **not** started automatically.  Call :meth:`start` before
    publishing and :meth:`stop` when shutting down.
    """

    def __init__(self, brokers: str) -> None:
        self._brokers = brokers
        self._producer: AIOKafkaProducer | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Create the underlying ``AIOKafkaProducer`` and start it."""
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._brokers,
            value_serializer=serialize_event,
        )
        await self._producer.start()
        logger.info("kafka_producer_started", brokers=self._brokers)

    async def stop(self) -> None:
        """Flush pending messages and stop the producer."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            logger.info("kafka_producer_stopped")

    # ── Core publish ─────────────────────────────────────────────────────

    async def publish(self, topic: str, event: EventEnvelope) -> None:
        """Serialize *event* and send it to *topic*.

        If the producer has not been started, the call is silently skipped
        with a warning log so that callers do not need to guard every call.
        """
        if self._producer is None:
            logger.warning("kafka_producer_not_started", topic=topic)
            return
        await self._producer.send_and_wait(topic, value=event)
        logger.debug(
            "kafka_event_published",
            topic=topic,
            event_id=event.event_id,
            event_type=event.event_type,
        )

    # ── Convenience publishers ───────────────────────────────────────────

    async def publish_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        source: str = "shieldops",
    ) -> EventEnvelope:
        """Build an envelope and publish it to the main events topic."""
        envelope = EventEnvelope(
            event_type=event_type,
            source=source,
            payload=payload,
        )
        await self.publish(EVENTS_TOPIC, envelope)
        return envelope

    async def publish_result(
        self,
        agent_type: str,
        result: dict[str, Any],
        correlation_id: str | None = None,
    ) -> EventEnvelope:
        """Publish an agent result to the results topic."""
        envelope = EventEnvelope(
            event_type=f"agent.result.{agent_type}",
            source=f"agent.{agent_type}",
            payload=result,
            correlation_id=correlation_id,
        )
        await self.publish(AGENT_RESULTS_TOPIC, envelope)
        return envelope

    async def publish_audit(
        self,
        action: str,
        details: dict[str, Any],
    ) -> EventEnvelope:
        """Publish an audit entry to the immutable audit topic."""
        envelope = EventEnvelope(
            event_type=f"audit.{action}",
            source="shieldops.audit",
            payload=details,
        )
        await self.publish(AUDIT_TOPIC, envelope)
        return envelope
