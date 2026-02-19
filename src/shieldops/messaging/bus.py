"""High-level event bus that composes a producer and consumer."""

from __future__ import annotations

from typing import Any

import structlog

from shieldops.messaging.consumer import EventConsumer
from shieldops.messaging.dlq import DeadLetterQueue
from shieldops.messaging.producer import EventProducer
from shieldops.messaging.topics import ALL_TOPICS, EventEnvelope

logger = structlog.get_logger()


class EventBus:
    """Facade that owns a matched :class:`EventProducer` / :class:`EventConsumer`.

    Typical usage::

        bus = EventBus(brokers="localhost:9092", group_id="shieldops-agents")
        await bus.start()
        try:
            envelope = await bus.publish("alert.fired", {"alert_id": "a1"})
            await bus.consumer.consume(my_handler)
        finally:
            await bus.stop()

    Set *enable_dlq* to ``True`` (the default) to route failed
    consumer messages to a dead letter queue after retry exhaustion.
    """

    def __init__(
        self,
        brokers: str,
        group_id: str,
        *,
        enable_dlq: bool = True,
    ) -> None:
        self._producer = EventProducer(brokers=brokers)
        self._dlq: DeadLetterQueue | None = DeadLetterQueue(self._producer) if enable_dlq else None
        self._consumer = EventConsumer(
            brokers=brokers,
            group_id=group_id,
            topics=ALL_TOPICS,
            dlq=self._dlq,
        )

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def producer(self) -> EventProducer:
        """Return the underlying :class:`EventProducer`."""
        return self._producer

    @property
    def consumer(self) -> EventConsumer:
        """Return the underlying :class:`EventConsumer`."""
        return self._consumer

    @property
    def dlq(self) -> DeadLetterQueue | None:
        """Return the :class:`DeadLetterQueue`, or ``None``."""
        return self._dlq

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start both the producer and the consumer."""
        await self._producer.start()
        await self._consumer.start()
        logger.info("event_bus_started")

    async def stop(self) -> None:
        """Stop the consumer first (drain in-flight), then the producer."""
        await self._consumer.stop()
        await self._producer.stop()
        logger.info("event_bus_stopped")

    # ── Convenience ──────────────────────────────────────────────────────

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        """Create an event envelope and publish it via the producer."""
        return await self._producer.publish_event(event_type=event_type, payload=payload)
