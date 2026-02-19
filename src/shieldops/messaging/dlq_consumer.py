"""Consumer for replaying and inspecting dead letter queue messages."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from aiokafka import AIOKafkaConsumer  # type: ignore[import-untyped]

from shieldops.messaging.producer import EventProducer
from shieldops.messaging.topics import (
    DLQ_TOPIC,
    DLQEnvelope,
    EventEnvelope,
    deserialize_event,
)

logger = structlog.get_logger()


class DLQConsumer:
    """Consumes DLQ messages for inspection and replay.

    Messages on the DLQ topic are ``EventEnvelope`` instances whose
    ``payload`` contains a serialised :class:`DLQEnvelope`.  This
    consumer deserialises the inner envelope and hands it to the
    caller-supplied handler.
    """

    def __init__(
        self,
        brokers: str,
        group_id: str = "shieldops-dlq",
    ) -> None:
        self._brokers = brokers
        self._group_id = group_id
        self._consumer: AIOKafkaConsumer | None = None

    # ── Lifecycle ────────────────────────────────────────────────────

    async def start(self) -> None:
        """Create and start the underlying Kafka consumer."""
        self._consumer = AIOKafkaConsumer(
            DLQ_TOPIC,
            bootstrap_servers=self._brokers,
            group_id=self._group_id,
            value_deserializer=lambda raw: deserialize_event(raw),
        )
        await self._consumer.start()
        logger.info(
            "dlq_consumer_started",
            brokers=self._brokers,
            group_id=self._group_id,
        )

    async def stop(self) -> None:
        """Stop the consumer and release resources."""
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
            logger.info("dlq_consumer_stopped")

    # ── Processing ───────────────────────────────────────────────────

    async def consume(
        self,
        handler: Callable[[DLQEnvelope], Awaitable[None]],
    ) -> None:
        """Iterate over DLQ messages and dispatch each to *handler*.

        Each Kafka message is an ``EventEnvelope`` whose ``payload``
        is deserialised into a :class:`DLQEnvelope` before being
        handed to the handler.
        """
        if self._consumer is None:
            logger.warning("dlq_consumer_not_started")
            return
        async for message in self._consumer:
            try:
                carrier: EventEnvelope = message.value
                dlq_envelope = DLQEnvelope.model_validate(
                    carrier.payload,
                )
                await handler(dlq_envelope)
                logger.debug(
                    "dlq_message_handled",
                    dlq_id=dlq_envelope.dlq_id,
                    event_id=(dlq_envelope.original_event.event_id),
                )
            except Exception:
                logger.exception(
                    "dlq_handler_error",
                    topic=message.topic,
                    offset=message.offset,
                )

    async def replay(
        self,
        producer: EventProducer,
        filter_fn: Callable[[DLQEnvelope], bool] | None = None,
    ) -> int:
        """Replay DLQ messages back to their original topics.

        If *filter_fn* is provided, only messages for which it returns
        ``True`` are replayed.  Returns the count of replayed messages.
        """
        if self._consumer is None:
            logger.warning("dlq_consumer_not_started")
            return 0

        replayed = 0
        async for message in self._consumer:
            try:
                carrier: EventEnvelope = message.value
                dlq_envelope = DLQEnvelope.model_validate(
                    carrier.payload,
                )

                if filter_fn and not filter_fn(dlq_envelope):
                    logger.debug(
                        "dlq_replay_skipped",
                        dlq_id=dlq_envelope.dlq_id,
                    )
                    continue

                await producer.publish(
                    dlq_envelope.source_topic,
                    dlq_envelope.original_event,
                )
                replayed += 1
                logger.info(
                    "dlq_message_replayed",
                    dlq_id=dlq_envelope.dlq_id,
                    source_topic=dlq_envelope.source_topic,
                    event_id=(dlq_envelope.original_event.event_id),
                )
            except Exception:
                logger.exception(
                    "dlq_replay_error",
                    topic=message.topic,
                    offset=message.offset,
                )
        return replayed
