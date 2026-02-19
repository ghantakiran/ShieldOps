"""Comprehensive tests for the Kafka dead letter queue (DLQ) layer."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.messaging.bus import EventBus
from shieldops.messaging.consumer import EventConsumer
from shieldops.messaging.dlq import DeadLetterQueue
from shieldops.messaging.dlq_consumer import DLQConsumer
from shieldops.messaging.producer import EventProducer
from shieldops.messaging.topics import (
    ALL_TOPICS,
    DLQ_TOPIC,
    DLQEnvelope,
    EventEnvelope,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


class _AsyncIter:
    """Wraps a sync iterable into a proper async iterator."""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration from None


def _make_event(**kwargs) -> EventEnvelope:
    """Build a test EventEnvelope with sensible defaults."""
    defaults = {"event_type": "test.event", "source": "unit"}
    defaults.update(kwargs)
    return EventEnvelope(**defaults)


def _make_message(event: EventEnvelope, topic: str = "shieldops.events"):
    """Create a mock Kafka message carrying *event*."""
    msg = MagicMock()
    msg.value = event
    msg.topic = topic
    msg.offset = 0
    return msg


# ── DLQ_TOPIC constant ──────────────────────────────────────────────────────


class TestDLQTopicConstant:
    def test_dlq_topic_value(self):
        assert DLQ_TOPIC == "shieldops.dlq"

    def test_dlq_topic_in_all_topics(self):
        assert DLQ_TOPIC in ALL_TOPICS

    def test_all_topics_contains_four_entries(self):
        assert len(ALL_TOPICS) == 4


# ── DLQEnvelope model ───────────────────────────────────────────────────────


class TestDLQEnvelope:
    def test_create_with_all_fields(self):
        event = _make_event()
        env = DLQEnvelope(
            original_event=event,
            error_message="something broke",
            error_type="RuntimeError",
            source_topic="shieldops.events",
            retry_count=2,
            max_retries=3,
        )
        assert env.original_event == event
        assert env.error_message == "something broke"
        assert env.error_type == "RuntimeError"
        assert env.source_topic == "shieldops.events"
        assert env.retry_count == 2
        assert env.max_retries == 3

    def test_default_retry_count_is_zero(self):
        env = DLQEnvelope(
            original_event=_make_event(),
            error_message="err",
            error_type="ValueError",
            source_topic="t",
        )
        assert env.retry_count == 0

    def test_default_max_retries_is_three(self):
        env = DLQEnvelope(
            original_event=_make_event(),
            error_message="err",
            error_type="ValueError",
            source_topic="t",
        )
        assert env.max_retries == 3

    def test_auto_generates_dlq_id(self):
        env = DLQEnvelope(
            original_event=_make_event(),
            error_message="err",
            error_type="ValueError",
            source_topic="t",
        )
        assert env.dlq_id is not None
        assert len(env.dlq_id) == 36  # UUID format

    def test_auto_generates_failed_at(self):
        before = datetime.now(UTC)
        env = DLQEnvelope(
            original_event=_make_event(),
            error_message="err",
            error_type="ValueError",
            source_topic="t",
        )
        after = datetime.now(UTC)
        assert before <= env.failed_at <= after

    def test_unique_dlq_ids(self):
        kwargs = dict(
            original_event=_make_event(),
            error_message="err",
            error_type="ValueError",
            source_topic="t",
        )
        env1 = DLQEnvelope(**kwargs)
        env2 = DLQEnvelope(**kwargs)
        assert env1.dlq_id != env2.dlq_id

    def test_serialization_round_trip(self):
        event = _make_event(
            payload={"key": "value"},
            correlation_id="corr-1",
        )
        original = DLQEnvelope(
            original_event=event,
            error_message="timeout",
            error_type="TimeoutError",
            source_topic="shieldops.events",
            retry_count=3,
            max_retries=3,
        )
        data = original.model_dump_json()
        restored = DLQEnvelope.model_validate_json(data)
        assert restored.dlq_id == original.dlq_id
        assert restored.error_message == original.error_message
        assert restored.error_type == original.error_type
        assert restored.original_event.event_id == original.original_event.event_id
        assert restored.retry_count == original.retry_count

    def test_serialization_to_dict(self):
        env = DLQEnvelope(
            original_event=_make_event(),
            error_message="err",
            error_type="ValueError",
            source_topic="t",
        )
        data = env.model_dump(mode="json")
        assert isinstance(data, dict)
        assert "original_event" in data
        assert "dlq_id" in data
        assert "failed_at" in data


# ── DeadLetterQueue ──────────────────────────────────────────────────────────


class TestDeadLetterQueue:
    def test_init_stores_producer_and_max_retries(self):
        producer = AsyncMock(spec=EventProducer)
        dlq = DeadLetterQueue(producer, max_retries=5)
        assert dlq._producer is producer
        assert dlq.max_retries == 5

    def test_default_max_retries_is_three(self):
        producer = AsyncMock(spec=EventProducer)
        dlq = DeadLetterQueue(producer)
        assert dlq.max_retries == 3

    @pytest.mark.asyncio
    async def test_send_to_dlq_creates_correct_envelope(self):
        producer = AsyncMock(spec=EventProducer)
        dlq = DeadLetterQueue(producer, max_retries=3)
        event = _make_event()

        result = await dlq.send_to_dlq(
            event=event,
            error=RuntimeError("boom"),
            source_topic="shieldops.events",
            retry_count=3,
        )

        assert isinstance(result, DLQEnvelope)
        assert result.original_event == event
        assert result.error_message == "boom"
        assert result.error_type == "RuntimeError"
        assert result.source_topic == "shieldops.events"
        assert result.retry_count == 3

    @pytest.mark.asyncio
    async def test_send_to_dlq_publishes_to_dlq_topic(self):
        producer = AsyncMock(spec=EventProducer)
        dlq = DeadLetterQueue(producer)
        event = _make_event()

        await dlq.send_to_dlq(
            event=event,
            error=ValueError("bad"),
            source_topic="shieldops.events",
        )

        producer.publish.assert_awaited_once()
        call_args = producer.publish.call_args
        assert call_args[0][0] == DLQ_TOPIC
        carrier = call_args[0][1]
        assert isinstance(carrier, EventEnvelope)
        assert carrier.event_type == "dlq.failed"
        assert carrier.source == "shieldops.dlq"

    @pytest.mark.asyncio
    async def test_send_to_dlq_carrier_contains_dlq_payload(self):
        producer = AsyncMock(spec=EventProducer)
        dlq = DeadLetterQueue(producer)
        event = _make_event(correlation_id="corr-99")

        await dlq.send_to_dlq(
            event=event,
            error=TypeError("wrong"),
            source_topic="shieldops.events",
        )

        carrier = producer.publish.call_args[0][1]
        assert carrier.correlation_id == "corr-99"
        # Payload should be a dict that can be parsed back
        restored = DLQEnvelope.model_validate(carrier.payload)
        assert restored.error_type == "TypeError"

    @pytest.mark.asyncio
    async def test_should_retry_true_when_under_max(self):
        dlq = DeadLetterQueue(AsyncMock(), max_retries=3)
        assert await dlq.should_retry(0) is True
        assert await dlq.should_retry(1) is True
        assert await dlq.should_retry(2) is True

    @pytest.mark.asyncio
    async def test_should_retry_false_at_max(self):
        dlq = DeadLetterQueue(AsyncMock(), max_retries=3)
        assert await dlq.should_retry(3) is False

    @pytest.mark.asyncio
    async def test_should_retry_false_above_max(self):
        dlq = DeadLetterQueue(AsyncMock(), max_retries=3)
        assert await dlq.should_retry(5) is False

    @pytest.mark.asyncio
    async def test_send_to_dlq_returns_envelope(self):
        producer = AsyncMock(spec=EventProducer)
        dlq = DeadLetterQueue(producer)
        event = _make_event()

        result = await dlq.send_to_dlq(
            event=event,
            error=RuntimeError("x"),
            source_topic="t",
        )

        assert isinstance(result, DLQEnvelope)
        assert result.dlq_id is not None


# ── Consumer DLQ integration ────────────────────────────────────────────────


class TestConsumerDLQIntegration:
    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_consume_retries_on_failure(self, mock_kafka_cls):
        """Messages that fail should increment retry count."""
        event = _make_event()
        messages = [_make_message(event)] * 4  # 4 attempts

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter(messages)
        mock_kafka_cls.return_value = mock_instance

        dlq = DeadLetterQueue(
            AsyncMock(spec=EventProducer),
            max_retries=3,
        )
        consumer = EventConsumer(
            brokers="broker:9092",
            group_id="grp",
            topics=["t"],
            dlq=dlq,
        )
        await consumer.start()

        handler = AsyncMock(
            side_effect=RuntimeError("fail"),
        )
        await consumer.consume(handler)

        # Handler called 4 times (3 retries + 1 final fail)
        assert handler.await_count == 4

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_consume_sends_to_dlq_after_max_retries(
        self,
        mock_kafka_cls,
    ):
        """After max_retries the message should be sent to DLQ."""
        event = _make_event()
        # max_retries=2, so 3 failures total sends to DLQ
        messages = [_make_message(event)] * 3

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter(messages)
        mock_kafka_cls.return_value = mock_instance

        mock_producer = AsyncMock(spec=EventProducer)
        dlq = DeadLetterQueue(mock_producer, max_retries=2)
        consumer = EventConsumer(
            brokers="broker:9092",
            group_id="grp",
            topics=["t"],
            dlq=dlq,
        )
        await consumer.start()

        handler = AsyncMock(
            side_effect=RuntimeError("fail"),
        )
        await consumer.consume(handler)

        # Should have published to DLQ topic
        mock_producer.publish.assert_awaited_once()
        call_args = mock_producer.publish.call_args
        assert call_args[0][0] == DLQ_TOPIC

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_consume_without_dlq_logs_exception(
        self,
        mock_kafka_cls,
    ):
        """Without DLQ, errors are logged but processing continues."""
        event = _make_event()
        msg1 = _make_message(event)
        event2 = _make_event(event_type="good")
        msg2 = _make_message(event2)

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter(
            [msg1, msg2],
        )
        mock_kafka_cls.return_value = mock_instance

        consumer = EventConsumer(
            brokers="broker:9092",
            group_id="grp",
            topics=["t"],
            dlq=None,
        )
        await consumer.start()

        handler = AsyncMock(
            side_effect=[RuntimeError("fail"), None],
        )
        await consumer.consume(handler)

        # Both messages processed despite first failure
        assert handler.await_count == 2

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_consume_clears_retry_count_on_success(
        self,
        mock_kafka_cls,
    ):
        """Successful processing should clear the retry counter."""
        event = _make_event()
        msg = _make_message(event)

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter([msg])
        mock_kafka_cls.return_value = mock_instance

        dlq = DeadLetterQueue(
            AsyncMock(spec=EventProducer),
            max_retries=3,
        )
        consumer = EventConsumer(
            brokers="broker:9092",
            group_id="grp",
            topics=["t"],
            dlq=dlq,
        )
        await consumer.start()

        handler = AsyncMock()  # succeeds
        await consumer.consume(handler)

        assert event.event_id not in consumer._retry_counts

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_retry_count_increments_correctly(
        self,
        mock_kafka_cls,
    ):
        """Each failure should increment the per-event retry count."""
        event = _make_event()
        # 2 failures for the same event
        messages = [_make_message(event)] * 2

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter(messages)
        mock_kafka_cls.return_value = mock_instance

        dlq = DeadLetterQueue(
            AsyncMock(spec=EventProducer),
            max_retries=5,
        )
        consumer = EventConsumer(
            brokers="broker:9092",
            group_id="grp",
            topics=["t"],
            dlq=dlq,
        )
        await consumer.start()

        handler = AsyncMock(
            side_effect=RuntimeError("fail"),
        )
        await consumer.consume(handler)

        assert consumer._retry_counts[event.event_id] == 2

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_consume_batch_sends_failed_to_dlq(
        self,
        mock_kafka_cls,
    ):
        """When batch handler fails, each event routes through DLQ."""
        events = [_make_event(event_type=f"ev-{i}") for i in range(3)]
        tp = MagicMock()
        batch_messages = [_make_message(e) for e in events]

        mock_instance = AsyncMock()

        call_count = 0

        async def fake_getmany(timeout_ms, max_records):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {tp: batch_messages}
            # Stop the loop on second call by returning empty
            # and then raising to break out
            raise StopAsyncIteration

        mock_instance.getmany = AsyncMock(side_effect=fake_getmany)
        mock_kafka_cls.return_value = mock_instance

        mock_producer = AsyncMock(spec=EventProducer)
        dlq = DeadLetterQueue(mock_producer, max_retries=0)
        consumer = EventConsumer(
            brokers="broker:9092",
            group_id="grp",
            topics=["t"],
            dlq=dlq,
        )
        await consumer.start()

        handler = AsyncMock(side_effect=RuntimeError("batch fail"))

        # The loop will break on StopAsyncIteration
        with pytest.raises(StopAsyncIteration):
            await consumer.consume_batch(handler)

        # With max_retries=0, first failure sends all to DLQ
        # Each event gets its own send_to_dlq call
        assert mock_producer.publish.await_count == 3

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_consume_batch_without_dlq_logs(
        self,
        mock_kafka_cls,
    ):
        """Without DLQ, batch errors are logged only."""
        events = [_make_event()]
        tp = MagicMock()
        batch_messages = [_make_message(e) for e in events]

        mock_instance = AsyncMock()
        call_count = 0

        async def fake_getmany(timeout_ms, max_records):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {tp: batch_messages}
            raise StopAsyncIteration

        mock_instance.getmany = AsyncMock(side_effect=fake_getmany)
        mock_kafka_cls.return_value = mock_instance

        consumer = EventConsumer(
            brokers="broker:9092",
            group_id="grp",
            topics=["t"],
            dlq=None,
        )
        await consumer.start()

        handler = AsyncMock(side_effect=RuntimeError("batch fail"))

        with pytest.raises(StopAsyncIteration):
            await consumer.consume_batch(handler)

        # No DLQ, so handler was called but no publish
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_consume_dlq_cleared_after_send(
        self,
        mock_kafka_cls,
    ):
        """After sending to DLQ, retry counter is cleaned up."""
        event = _make_event()
        # max_retries=1, so 2 failures => DLQ
        messages = [_make_message(event)] * 2

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter(messages)
        mock_kafka_cls.return_value = mock_instance

        mock_producer = AsyncMock(spec=EventProducer)
        dlq = DeadLetterQueue(mock_producer, max_retries=1)
        consumer = EventConsumer(
            brokers="broker:9092",
            group_id="grp",
            topics=["t"],
            dlq=dlq,
        )
        await consumer.start()

        handler = AsyncMock(
            side_effect=RuntimeError("fail"),
        )
        await consumer.consume(handler)

        # Retry count should be cleared after DLQ send
        assert event.event_id not in consumer._retry_counts

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_consume_backward_compat_no_dlq_param(
        self,
        mock_kafka_cls,
    ):
        """EventConsumer without dlq param works like before."""
        event = _make_event()
        msg = _make_message(event)

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter([msg])
        mock_kafka_cls.return_value = mock_instance

        # No dlq parameter at all
        consumer = EventConsumer(
            brokers="broker:9092",
            group_id="grp",
            topics=["t"],
        )
        await consumer.start()

        handler = AsyncMock()
        await consumer.consume(handler)

        handler.assert_awaited_once_with(event)


# ── DLQConsumer ──────────────────────────────────────────────────────────────


class TestDLQConsumer:
    def test_init_stores_config(self):
        consumer = DLQConsumer(brokers="broker:9092", group_id="grp")
        assert consumer._brokers == "broker:9092"
        assert consumer._group_id == "grp"
        assert consumer._consumer is None

    def test_default_group_id(self):
        consumer = DLQConsumer(brokers="broker:9092")
        assert consumer._group_id == "shieldops-dlq"

    @pytest.mark.asyncio
    @patch("shieldops.messaging.dlq_consumer.AIOKafkaConsumer")
    async def test_start_creates_consumer(self, mock_kafka_cls):
        mock_instance = AsyncMock()
        mock_kafka_cls.return_value = mock_instance

        consumer = DLQConsumer(brokers="broker:9092")
        await consumer.start()

        mock_kafka_cls.assert_called_once()
        call_args = mock_kafka_cls.call_args
        assert DLQ_TOPIC in call_args[0]
        mock_instance.start.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("shieldops.messaging.dlq_consumer.AIOKafkaConsumer")
    async def test_stop_stops_consumer(self, mock_kafka_cls):
        mock_instance = AsyncMock()
        mock_kafka_cls.return_value = mock_instance

        consumer = DLQConsumer(brokers="broker:9092")
        await consumer.start()
        await consumer.stop()

        mock_instance.stop.assert_awaited_once()
        assert consumer._consumer is None

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self):
        consumer = DLQConsumer(brokers="broker:9092")
        await consumer.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_consume_when_not_started(self):
        consumer = DLQConsumer(brokers="broker:9092")
        handler = AsyncMock()
        await consumer.consume(handler)
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("shieldops.messaging.dlq_consumer.AIOKafkaConsumer")
    async def test_consume_deserializes_dlq_envelope(
        self,
        mock_kafka_cls,
    ):
        """consume() should unwrap the carrier and pass DLQEnvelope."""
        inner_event = _make_event()
        dlq_env = DLQEnvelope(
            original_event=inner_event,
            error_message="timeout",
            error_type="TimeoutError",
            source_topic="shieldops.events",
        )
        carrier = EventEnvelope(
            event_type="dlq.failed",
            source="shieldops.dlq",
            payload=dlq_env.model_dump(mode="json"),
        )

        msg = MagicMock()
        msg.value = carrier
        msg.topic = DLQ_TOPIC
        msg.offset = 0

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter([msg])
        mock_kafka_cls.return_value = mock_instance

        consumer = DLQConsumer(brokers="broker:9092")
        await consumer.start()

        handler = AsyncMock()
        await consumer.consume(handler)

        handler.assert_awaited_once()
        received = handler.call_args[0][0]
        assert isinstance(received, DLQEnvelope)
        assert received.error_type == "TimeoutError"
        assert received.original_event.event_id == inner_event.event_id

    @pytest.mark.asyncio
    @patch("shieldops.messaging.dlq_consumer.AIOKafkaConsumer")
    async def test_replay_republishes_to_original_topic(
        self,
        mock_kafka_cls,
    ):
        """replay() should publish events back to source_topic."""
        inner_event = _make_event()
        dlq_env = DLQEnvelope(
            original_event=inner_event,
            error_message="err",
            error_type="RuntimeError",
            source_topic="shieldops.events",
        )
        carrier = EventEnvelope(
            event_type="dlq.failed",
            source="shieldops.dlq",
            payload=dlq_env.model_dump(mode="json"),
        )

        msg = MagicMock()
        msg.value = carrier
        msg.topic = DLQ_TOPIC
        msg.offset = 0

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter([msg])
        mock_kafka_cls.return_value = mock_instance

        consumer = DLQConsumer(brokers="broker:9092")
        await consumer.start()

        mock_producer = AsyncMock(spec=EventProducer)
        count = await consumer.replay(mock_producer)

        assert count == 1
        mock_producer.publish.assert_awaited_once()
        call_args = mock_producer.publish.call_args
        assert call_args[0][0] == "shieldops.events"
        assert call_args[0][1].event_id == inner_event.event_id

    @pytest.mark.asyncio
    @patch("shieldops.messaging.dlq_consumer.AIOKafkaConsumer")
    async def test_replay_with_filter_fn(self, mock_kafka_cls):
        """replay() with filter_fn only replays matching messages."""
        event1 = _make_event(event_type="good")
        event2 = _make_event(event_type="bad")

        dlq1 = DLQEnvelope(
            original_event=event1,
            error_message="err",
            error_type="RuntimeError",
            source_topic="shieldops.events",
        )
        dlq2 = DLQEnvelope(
            original_event=event2,
            error_message="err",
            error_type="RuntimeError",
            source_topic="shieldops.events",
        )

        carriers = []
        for dlq_env in [dlq1, dlq2]:
            carrier = EventEnvelope(
                event_type="dlq.failed",
                source="shieldops.dlq",
                payload=dlq_env.model_dump(mode="json"),
            )
            carriers.append(carrier)

        messages = []
        for c in carriers:
            msg = MagicMock()
            msg.value = c
            msg.topic = DLQ_TOPIC
            msg.offset = 0
            messages.append(msg)

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter(messages)
        mock_kafka_cls.return_value = mock_instance

        consumer = DLQConsumer(brokers="broker:9092")
        await consumer.start()

        mock_producer = AsyncMock(spec=EventProducer)

        # Only replay events where original type is "good"
        count = await consumer.replay(
            mock_producer,
            filter_fn=lambda env: env.original_event.event_type == "good",
        )

        assert count == 1
        mock_producer.publish.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("shieldops.messaging.dlq_consumer.AIOKafkaConsumer")
    async def test_replay_returns_correct_count(
        self,
        mock_kafka_cls,
    ):
        """replay() returns the number of successfully replayed msgs."""
        messages = []
        for i in range(5):
            event = _make_event(event_type=f"ev-{i}")
            dlq_env = DLQEnvelope(
                original_event=event,
                error_message="err",
                error_type="RuntimeError",
                source_topic="shieldops.events",
            )
            carrier = EventEnvelope(
                event_type="dlq.failed",
                source="shieldops.dlq",
                payload=dlq_env.model_dump(mode="json"),
            )
            msg = MagicMock()
            msg.value = carrier
            msg.topic = DLQ_TOPIC
            msg.offset = i
            messages.append(msg)

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter(messages)
        mock_kafka_cls.return_value = mock_instance

        consumer = DLQConsumer(brokers="broker:9092")
        await consumer.start()

        mock_producer = AsyncMock(spec=EventProducer)
        count = await consumer.replay(mock_producer)

        assert count == 5
        assert mock_producer.publish.await_count == 5

    @pytest.mark.asyncio
    async def test_replay_when_not_started_returns_zero(self):
        consumer = DLQConsumer(brokers="broker:9092")
        mock_producer = AsyncMock(spec=EventProducer)
        count = await consumer.replay(mock_producer)
        assert count == 0

    @pytest.mark.asyncio
    @patch("shieldops.messaging.dlq_consumer.AIOKafkaConsumer")
    async def test_replay_continues_on_error(self, mock_kafka_cls):
        """If one message fails during replay, continue to next."""
        event1 = _make_event(event_type="ev-1")
        event2 = _make_event(event_type="ev-2")

        messages = []
        for event in [event1, event2]:
            dlq_env = DLQEnvelope(
                original_event=event,
                error_message="err",
                error_type="RuntimeError",
                source_topic="shieldops.events",
            )
            carrier = EventEnvelope(
                event_type="dlq.failed",
                source="shieldops.dlq",
                payload=dlq_env.model_dump(mode="json"),
            )
            msg = MagicMock()
            msg.value = carrier
            msg.topic = DLQ_TOPIC
            msg.offset = 0
            messages.append(msg)

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter(messages)
        mock_kafka_cls.return_value = mock_instance

        consumer = DLQConsumer(brokers="broker:9092")
        await consumer.start()

        mock_producer = AsyncMock(spec=EventProducer)
        # First publish fails, second succeeds
        mock_producer.publish = AsyncMock(
            side_effect=[RuntimeError("fail"), None],
        )

        count = await consumer.replay(mock_producer)

        # Only the second succeeded
        assert count == 1


# ── EventBus DLQ integration ────────────────────────────────────────────────


class TestEventBusDLQ:
    def test_enable_dlq_true_creates_dlq(self):
        bus = EventBus(
            brokers="broker:9092",
            group_id="grp",
            enable_dlq=True,
        )
        assert bus.dlq is not None
        assert isinstance(bus.dlq, DeadLetterQueue)

    def test_enable_dlq_false_has_no_dlq(self):
        bus = EventBus(
            brokers="broker:9092",
            group_id="grp",
            enable_dlq=False,
        )
        assert bus.dlq is None

    def test_enable_dlq_default_is_true(self):
        bus = EventBus(brokers="broker:9092", group_id="grp")
        assert bus.dlq is not None

    def test_dlq_uses_bus_producer(self):
        bus = EventBus(brokers="broker:9092", group_id="grp")
        assert bus.dlq._producer is bus.producer

    def test_consumer_receives_dlq(self):
        bus = EventBus(
            brokers="broker:9092",
            group_id="grp",
            enable_dlq=True,
        )
        assert bus.consumer._dlq is bus.dlq

    def test_consumer_no_dlq_when_disabled(self):
        bus = EventBus(
            brokers="broker:9092",
            group_id="grp",
            enable_dlq=False,
        )
        assert bus.consumer._dlq is None

    def test_backward_compat_positional_args(self):
        """Existing code with positional args still works."""
        bus = EventBus("broker:9092", "grp")
        assert isinstance(bus.producer, EventProducer)
        assert isinstance(bus.consumer, EventConsumer)
        # DLQ is enabled by default
        assert bus.dlq is not None
