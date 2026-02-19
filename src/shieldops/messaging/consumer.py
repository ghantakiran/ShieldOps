"""Async Kafka consumer for processing ShieldOps events."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from aiokafka import AIOKafkaConsumer  # type: ignore[import-untyped]

from shieldops.messaging.dlq import DeadLetterQueue
from shieldops.messaging.topics import EventEnvelope, deserialize_event

logger = structlog.get_logger()


class EventConsumer:
    """Subscribes to Kafka topics and dispatches deserialized events.

    Call :meth:`start` to connect, then :meth:`consume` to enter the
    processing loop.  Call :meth:`stop` to tear down gracefully.

    If a :class:`DeadLetterQueue` is provided, failed messages are
    retried up to ``dlq.max_retries`` times before being routed to the
    dead letter topic.  When *dlq* is ``None`` the original
    log-and-continue behaviour is preserved.
    """

    def __init__(
        self,
        brokers: str,
        group_id: str,
        topics: list[str],
        dlq: DeadLetterQueue | None = None,
    ) -> None:
        self._brokers = brokers
        self._group_id = group_id
        self._topics = topics
        self._consumer: AIOKafkaConsumer | None = None
        self._dlq = dlq
        # In-memory retry tracker: event_id -> current retry count
        self._retry_counts: dict[str, int] = {}

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

        Processing errors for individual messages are logged but do
        **not** halt the consumer, ensuring one bad message cannot
        block the bus.

        When a :class:`DeadLetterQueue` is configured, failed messages
        are retried up to ``max_retries`` times.  After exhausting
        retries the message is sent to the DLQ topic.
        """
        if self._consumer is None:
            logger.warning("kafka_consumer_not_started")
            return
        async for message in self._consumer:
            try:
                event: EventEnvelope = message.value
                await handler(event)
                # Success — clear any tracked retries.
                self._retry_counts.pop(event.event_id, None)
                logger.debug(
                    "kafka_event_handled",
                    event_id=event.event_id,
                    event_type=event.event_type,
                )
            except Exception as exc:
                await self._handle_consume_error(
                    exc,
                    message.value,
                    message.topic,
                    message.offset,
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

        When the batch handler fails, each event in the batch is
        individually routed through the DLQ retry/send logic (if a
        :class:`DeadLetterQueue` is configured).
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
            topic_for_events: str = ""
            for _tp, messages in batch.items():
                for message in messages:
                    try:
                        events.append(message.value)
                        topic_for_events = message.topic
                    except Exception:
                        logger.exception(
                            "kafka_batch_deserialize_error",
                            topic=message.topic,
                            offset=message.offset,
                        )
            if events:
                try:
                    await handler(events)
                    # Success — clear retries for all events.
                    for ev in events:
                        self._retry_counts.pop(
                            ev.event_id,
                            None,
                        )
                    logger.debug(
                        "kafka_batch_handled",
                        count=len(events),
                    )
                except Exception as exc:
                    await self._handle_batch_error(
                        exc,
                        events,
                        topic_for_events,
                    )

    # ── DLQ helpers ───────────────────────────────────────────────────

    async def _handle_consume_error(
        self,
        exc: Exception,
        event: EventEnvelope,
        topic: str,
        offset: int,
    ) -> None:
        """Retry or route a single failed message to the DLQ."""
        if self._dlq is None:
            logger.exception(
                "kafka_event_handler_error",
                topic=topic,
                offset=offset,
            )
            return

        retry = self._retry_counts.get(event.event_id, 0) + 1
        self._retry_counts[event.event_id] = retry

        if await self._dlq.should_retry(retry):
            logger.warning(
                "kafka_event_retry",
                event_id=event.event_id,
                retry_count=retry,
                max_retries=self._dlq.max_retries,
            )
        else:
            await self._dlq.send_to_dlq(
                event=event,
                error=exc,
                source_topic=topic,
                retry_count=retry,
            )
            self._retry_counts.pop(event.event_id, None)

    async def _handle_batch_error(
        self,
        exc: Exception,
        events: list[EventEnvelope],
        topic: str,
    ) -> None:
        """Route each event in a failed batch through DLQ logic."""
        if self._dlq is None:
            logger.exception(
                "kafka_batch_handler_error",
                count=len(events),
            )
            return

        for event in events:
            await self._handle_consume_error(
                exc,
                event,
                topic,
                offset=0,
            )
