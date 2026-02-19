"""Async Kafka consumer for processing ShieldOps events."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from aiokafka import AIOKafkaConsumer  # type: ignore[import-untyped]

from shieldops.messaging.topics import EventEnvelope, deserialize_event

logger = structlog.get_logger()


class EventConsumer:
    """Subscribes to Kafka topics and dispatches deserialized events.

    Call :meth:`start` to connect, then :meth:`consume` to enter the
    processing loop.  Call :meth:`stop` to tear down gracefully.
    """

    def __init__(
        self,
        brokers: str,
        group_id: str,
        topics: list[str],
    ) -> None:
        self._brokers = brokers
        self._group_id = group_id
        self._topics = topics
        self._consumer: AIOKafkaConsumer | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Create the underlying ``AIOKafkaConsumer``, subscribe, and start."""
        self._consumer = AIOKafkaConsumer(
            *self._topics,
            bootstrap_servers=self._brokers,
            group_id=self._group_id,
            value_deserializer=lambda raw: deserialize_event(raw),
        )
        await self._consumer.start()
        logger.info(
            "kafka_consumer_started",
            brokers=self._brokers,
            group_id=self._group_id,
            topics=self._topics,
        )

    async def stop(self) -> None:
        """Commit offsets and stop the consumer."""
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
            logger.info("kafka_consumer_stopped")

    # ── Processing loops ─────────────────────────────────────────────────

    async def consume(
        self,
        handler: Callable[[EventEnvelope], Awaitable[None]],
    ) -> None:
        """Iterate over incoming messages and dispatch each to *handler*.

        Processing errors for individual messages are logged but do **not**
        halt the consumer, ensuring one bad message cannot block the bus.
        """
        if self._consumer is None:
            logger.warning("kafka_consumer_not_started")
            return
        async for message in self._consumer:
            try:
                event: EventEnvelope = message.value
                await handler(event)
                logger.debug(
                    "kafka_event_handled",
                    event_id=event.event_id,
                    event_type=event.event_type,
                )
            except Exception:
                logger.exception(
                    "kafka_event_handler_error",
                    topic=message.topic,
                    offset=message.offset,
                )

    async def consume_batch(
        self,
        handler: Callable[[list[EventEnvelope]], Awaitable[None]],
        max_records: int = 100,
        timeout_ms: int = 1000,
    ) -> None:
        """Fetch messages in batches and dispatch the batch to *handler*.

        The consumer calls ``getmany`` in a loop, yielding batches up to
        *max_records* messages or after *timeout_ms* of inactivity.
        """
        if self._consumer is None:
            logger.warning("kafka_consumer_not_started")
            return
        while True:
            batch = await self._consumer.getmany(
                timeout_ms=timeout_ms,
                max_records=max_records,
            )
            events: list[EventEnvelope] = []
            for _tp, messages in batch.items():
                for message in messages:
                    try:
                        events.append(message.value)
                    except Exception:
                        logger.exception(
                            "kafka_batch_deserialize_error",
                            topic=message.topic,
                            offset=message.offset,
                        )
            if events:
                try:
                    await handler(events)
                    logger.debug("kafka_batch_handled", count=len(events))
                except Exception:
                    logger.exception(
                        "kafka_batch_handler_error",
                        count=len(events),
                    )
