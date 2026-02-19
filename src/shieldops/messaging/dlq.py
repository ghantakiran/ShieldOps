"""Dead letter queue for failed Kafka messages."""

from __future__ import annotations

import structlog

from shieldops.messaging.producer import EventProducer
from shieldops.messaging.topics import (
    DLQ_TOPIC,
    DLQEnvelope,
    EventEnvelope,
)

logger = structlog.get_logger()


class DeadLetterQueue:
    """Routes failed messages to the DLQ topic after max retries.

    When a consumer handler fails repeatedly, the original event is
    wrapped in a :class:`DLQEnvelope` with error metadata and published
    to :data:`DLQ_TOPIC` for later inspection or replay.
    """

    def __init__(
        self,
        producer: EventProducer,
        max_retries: int = 3,
    ) -> None:
        self._producer = producer
        self._max_retries = max_retries

    @property
    def max_retries(self) -> int:
        """Return the configured maximum retry count."""
        return self._max_retries

    async def send_to_dlq(
        self,
        event: EventEnvelope,
        error: Exception,
        source_topic: str,
        retry_count: int = 0,
    ) -> DLQEnvelope:
        """Wrap *event* with error metadata and publish to DLQ topic.

        Returns the :class:`DLQEnvelope` that was published.
        """
        envelope = DLQEnvelope(
            original_event=event,
            error_message=str(error),
            error_type=type(error).__name__,
            source_topic=source_topic,
            retry_count=retry_count,
            max_retries=self._max_retries,
        )

        # Wrap the DLQ envelope inside an EventEnvelope so it goes
        # through the standard Kafka serializer.
        carrier = EventEnvelope(
            event_type="dlq.failed",
            source="shieldops.dlq",
            payload=envelope.model_dump(mode="json"),
            correlation_id=event.correlation_id,
        )
        await self._producer.publish(DLQ_TOPIC, carrier)

        logger.warning(
            "message_sent_to_dlq",
            event_id=event.event_id,
            error_type=envelope.error_type,
            error_message=envelope.error_message,
            source_topic=source_topic,
            retry_count=retry_count,
            dlq_id=envelope.dlq_id,
        )
        return envelope

    async def should_retry(self, retry_count: int) -> bool:
        """Return ``True`` if the message should be retried."""
        return retry_count < self._max_retries
