"""Comprehensive tests for the Kafka event bus messaging layer."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from shieldops.messaging.bus import EventBus
from shieldops.messaging.consumer import EventConsumer
from shieldops.messaging.producer import EventProducer
from shieldops.messaging.topics import (
    AGENT_RESULTS_TOPIC,
    ALL_TOPICS,
    AUDIT_TOPIC,
    EVENTS_TOPIC,
    EventEnvelope,
    deserialize_event,
    serialize_event,
)


class _AsyncIter:
    """Helper that wraps a sync iterable into a proper async iterator."""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration from None


# ── Topic constants ──────────────────────────────────────────────────────────


class TestTopicConstants:
    def test_events_topic_value(self):
        assert EVENTS_TOPIC == "shieldops.events"

    def test_agent_results_topic_value(self):
        assert AGENT_RESULTS_TOPIC == "shieldops.agent.results"

    def test_audit_topic_value(self):
        assert AUDIT_TOPIC == "shieldops.audit"

    def test_all_topics_contains_all(self):
        assert EVENTS_TOPIC in ALL_TOPICS
        assert AGENT_RESULTS_TOPIC in ALL_TOPICS
        assert AUDIT_TOPIC in ALL_TOPICS
        assert len(ALL_TOPICS) == 3


# ── EventEnvelope ────────────────────────────────────────────────────────────


class TestEventEnvelope:
    def test_create_with_required_fields(self):
        env = EventEnvelope(event_type="test", source="unit")
        assert env.event_type == "test"
        assert env.source == "unit"
        assert env.payload == {}
        assert env.correlation_id is None

    def test_auto_generates_uuid(self):
        env = EventEnvelope(event_type="test", source="unit")
        assert env.event_id is not None
        assert len(env.event_id) == 36  # standard UUID length

    def test_auto_generates_timestamp(self):
        before = datetime.now(UTC)
        env = EventEnvelope(event_type="test", source="unit")
        after = datetime.now(UTC)
        assert before <= env.timestamp <= after

    def test_unique_ids_per_instance(self):
        env1 = EventEnvelope(event_type="a", source="x")
        env2 = EventEnvelope(event_type="b", source="y")
        assert env1.event_id != env2.event_id

    def test_full_construction(self):
        ts = datetime.now(UTC)
        env = EventEnvelope(
            event_id="abc-123",
            event_type="alert.fired",
            source="prometheus",
            timestamp=ts,
            payload={"severity": "critical"},
            correlation_id="corr-456",
        )
        assert env.event_id == "abc-123"
        assert env.event_type == "alert.fired"
        assert env.source == "prometheus"
        assert env.timestamp == ts
        assert env.payload == {"severity": "critical"}
        assert env.correlation_id == "corr-456"


# ── Serialization round-trip ─────────────────────────────────────────────────


class TestSerialization:
    def test_serialize_returns_bytes(self):
        env = EventEnvelope(event_type="test", source="unit")
        data = serialize_event(env)
        assert isinstance(data, bytes)

    def test_serialize_is_valid_json(self):
        env = EventEnvelope(event_type="test", source="unit", payload={"k": "v"})
        data = serialize_event(env)
        parsed = json.loads(data)
        assert parsed["event_type"] == "test"
        assert parsed["payload"] == {"k": "v"}

    def test_round_trip(self):
        original = EventEnvelope(
            event_type="alert.fired",
            source="prometheus",
            payload={"metric": "cpu_usage", "value": 95.3},
            correlation_id="corr-789",
        )
        data = serialize_event(original)
        restored = deserialize_event(data)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.source == original.source
        assert restored.payload == original.payload
        assert restored.correlation_id == original.correlation_id

    def test_deserialize_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            deserialize_event(b"not-json")

    def test_deserialize_missing_required_field_raises(self):
        incomplete = json.dumps({"event_type": "test"}).encode()
        with pytest.raises(ValidationError):
            deserialize_event(incomplete)


# ── EventProducer ────────────────────────────────────────────────────────────


class TestEventProducer:
    def test_init_does_not_create_client(self):
        producer = EventProducer(brokers="localhost:9092")
        assert producer._producer is None

    @pytest.mark.asyncio
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_start_creates_and_starts_client(self, mock_kafka_cls):
        mock_instance = AsyncMock()
        mock_kafka_cls.return_value = mock_instance

        producer = EventProducer(brokers="broker:9092")
        await producer.start()

        mock_kafka_cls.assert_called_once()
        mock_instance.start.assert_awaited_once()
        assert producer._producer is mock_instance

    @pytest.mark.asyncio
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_stop_stops_client(self, mock_kafka_cls):
        mock_instance = AsyncMock()
        mock_kafka_cls.return_value = mock_instance

        producer = EventProducer(brokers="broker:9092")
        await producer.start()
        await producer.stop()

        mock_instance.stop.assert_awaited_once()
        assert producer._producer is None

    @pytest.mark.asyncio
    async def test_stop_when_not_started_is_noop(self):
        producer = EventProducer(brokers="broker:9092")
        await producer.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_publish_when_not_started_logs_warning(self):
        producer = EventProducer(brokers="broker:9092")
        env = EventEnvelope(event_type="test", source="unit")
        # Should not raise, just log
        await producer.publish("some.topic", env)

    @pytest.mark.asyncio
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_publish_sends_to_topic(self, mock_kafka_cls):
        mock_instance = AsyncMock()
        mock_kafka_cls.return_value = mock_instance

        producer = EventProducer(brokers="broker:9092")
        await producer.start()

        env = EventEnvelope(event_type="alert", source="test")
        await producer.publish("shieldops.events", env)

        mock_instance.send_and_wait.assert_awaited_once_with("shieldops.events", value=env)

    @pytest.mark.asyncio
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_publish_event_returns_envelope(self, mock_kafka_cls):
        mock_kafka_cls.return_value = AsyncMock()

        producer = EventProducer(brokers="broker:9092")
        await producer.start()

        result = await producer.publish_event("alert.fired", {"alert": "cpu"})

        assert isinstance(result, EventEnvelope)
        assert result.event_type == "alert.fired"
        assert result.source == "shieldops"
        assert result.payload == {"alert": "cpu"}

    @pytest.mark.asyncio
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_publish_event_uses_events_topic(self, mock_kafka_cls):
        mock_instance = AsyncMock()
        mock_kafka_cls.return_value = mock_instance

        producer = EventProducer(brokers="broker:9092")
        await producer.start()
        await producer.publish_event("alert.fired", {"a": 1})

        call_args = mock_instance.send_and_wait.call_args
        assert call_args[0][0] == EVENTS_TOPIC

    @pytest.mark.asyncio
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_publish_event_custom_source(self, mock_kafka_cls):
        mock_kafka_cls.return_value = AsyncMock()

        producer = EventProducer(brokers="broker:9092")
        await producer.start()

        result = await producer.publish_event("x", {}, source="custom")
        assert result.source == "custom"

    @pytest.mark.asyncio
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_publish_result_uses_results_topic(self, mock_kafka_cls):
        mock_instance = AsyncMock()
        mock_kafka_cls.return_value = mock_instance

        producer = EventProducer(brokers="broker:9092")
        await producer.start()

        result = await producer.publish_result(
            "investigation", {"finding": "root cause"}, correlation_id="c-1"
        )

        assert result.event_type == "agent.result.investigation"
        assert result.source == "agent.investigation"
        assert result.correlation_id == "c-1"
        call_args = mock_instance.send_and_wait.call_args
        assert call_args[0][0] == AGENT_RESULTS_TOPIC

    @pytest.mark.asyncio
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_publish_result_without_correlation_id(self, mock_kafka_cls):
        mock_kafka_cls.return_value = AsyncMock()

        producer = EventProducer(brokers="broker:9092")
        await producer.start()

        result = await producer.publish_result("remediation", {"status": "done"})
        assert result.correlation_id is None

    @pytest.mark.asyncio
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_publish_audit_uses_audit_topic(self, mock_kafka_cls):
        mock_instance = AsyncMock()
        mock_kafka_cls.return_value = mock_instance

        producer = EventProducer(brokers="broker:9092")
        await producer.start()

        result = await producer.publish_audit(
            "pod.restarted", {"pod": "nginx-1", "namespace": "prod"}
        )

        assert result.event_type == "audit.pod.restarted"
        assert result.source == "shieldops.audit"
        assert result.payload["pod"] == "nginx-1"
        call_args = mock_instance.send_and_wait.call_args
        assert call_args[0][0] == AUDIT_TOPIC

    @pytest.mark.asyncio
    async def test_publish_event_when_not_started_returns_envelope(self):
        """Even when the producer is not started, an envelope is returned."""
        producer = EventProducer(brokers="broker:9092")
        result = await producer.publish_event("test", {"k": "v"})
        assert isinstance(result, EventEnvelope)
        assert result.event_type == "test"


# ── EventConsumer ────────────────────────────────────────────────────────────


class TestEventConsumer:
    def test_init_stores_config(self):
        consumer = EventConsumer(
            brokers="broker:9092",
            group_id="test-group",
            topics=["topic.a", "topic.b"],
        )
        assert consumer._brokers == "broker:9092"
        assert consumer._group_id == "test-group"
        assert consumer._topics == ["topic.a", "topic.b"]
        assert consumer._consumer is None

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_start_creates_and_starts_client(self, mock_kafka_cls):
        mock_instance = AsyncMock()
        mock_kafka_cls.return_value = mock_instance

        consumer = EventConsumer(brokers="broker:9092", group_id="grp", topics=["t1"])
        await consumer.start()

        mock_kafka_cls.assert_called_once()
        # Verify topics are passed as positional args
        call_args = mock_kafka_cls.call_args
        assert "t1" in call_args[0]
        mock_instance.start.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_stop_stops_client(self, mock_kafka_cls):
        mock_instance = AsyncMock()
        mock_kafka_cls.return_value = mock_instance

        consumer = EventConsumer(brokers="broker:9092", group_id="grp", topics=["t1"])
        await consumer.start()
        await consumer.stop()

        mock_instance.stop.assert_awaited_once()
        assert consumer._consumer is None

    @pytest.mark.asyncio
    async def test_stop_when_not_started_is_noop(self):
        consumer = EventConsumer(brokers="broker:9092", group_id="grp", topics=["t1"])
        await consumer.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_consume_when_not_started_returns_immediately(self):
        consumer = EventConsumer(brokers="broker:9092", group_id="grp", topics=["t1"])
        handler = AsyncMock()
        await consumer.consume(handler)
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_consume_dispatches_messages_to_handler(self, mock_kafka_cls):
        env = EventEnvelope(event_type="test", source="unit")
        mock_message = MagicMock()
        mock_message.value = env
        mock_message.topic = "shieldops.events"
        mock_message.offset = 0

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter([mock_message])
        mock_kafka_cls.return_value = mock_instance

        consumer = EventConsumer(brokers="broker:9092", group_id="grp", topics=["t1"])
        await consumer.start()

        handler = AsyncMock()
        await consumer.consume(handler)

        handler.assert_awaited_once_with(env)

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    async def test_consume_continues_on_handler_error(self, mock_kafka_cls):
        """A failing handler should not stop the consumer loop."""
        env1 = EventEnvelope(event_type="bad", source="unit")
        env2 = EventEnvelope(event_type="good", source="unit")

        msg1 = MagicMock(value=env1, topic="t", offset=0)
        msg2 = MagicMock(value=env2, topic="t", offset=1)

        mock_instance = AsyncMock()
        mock_instance.__aiter__ = lambda self: _AsyncIter([msg1, msg2])
        mock_kafka_cls.return_value = mock_instance

        consumer = EventConsumer(brokers="broker:9092", group_id="grp", topics=["t"])
        await consumer.start()

        handler = AsyncMock(side_effect=[RuntimeError("boom"), None])
        await consumer.consume(handler)

        # Both messages were dispatched despite the first one failing
        assert handler.await_count == 2

    @pytest.mark.asyncio
    async def test_consume_batch_when_not_started_returns_immediately(self):
        consumer = EventConsumer(brokers="broker:9092", group_id="grp", topics=["t1"])
        handler = AsyncMock()
        await consumer.consume_batch(handler)
        handler.assert_not_awaited()


# ── EventBus ─────────────────────────────────────────────────────────────────


class TestEventBus:
    def test_init_creates_producer_and_consumer(self):
        bus = EventBus(brokers="broker:9092", group_id="grp")
        assert isinstance(bus.producer, EventProducer)
        assert isinstance(bus.consumer, EventConsumer)

    def test_consumer_subscribes_to_all_topics(self):
        bus = EventBus(brokers="broker:9092", group_id="grp")
        assert bus.consumer._topics == ALL_TOPICS

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_start_starts_both(self, mock_prod_cls, mock_cons_cls):
        mock_prod_cls.return_value = AsyncMock()
        mock_cons_cls.return_value = AsyncMock()

        bus = EventBus(brokers="broker:9092", group_id="grp")
        await bus.start()

        mock_prod_cls.return_value.start.assert_awaited_once()
        mock_cons_cls.return_value.start.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_stop_stops_consumer_before_producer(self, mock_prod_cls, mock_cons_cls):
        mock_prod = AsyncMock()
        mock_cons = AsyncMock()
        mock_prod_cls.return_value = mock_prod
        mock_cons_cls.return_value = mock_cons

        call_order: list[str] = []
        mock_cons.stop.side_effect = lambda: call_order.append("consumer")
        mock_prod.stop.side_effect = lambda: call_order.append("producer")

        bus = EventBus(brokers="broker:9092", group_id="grp")
        await bus.start()
        await bus.stop()

        assert call_order == ["consumer", "producer"]

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_publish_delegates_to_producer(self, mock_prod_cls, mock_cons_cls):
        mock_instance = AsyncMock()
        mock_prod_cls.return_value = mock_instance
        mock_cons_cls.return_value = AsyncMock()

        bus = EventBus(brokers="broker:9092", group_id="grp")
        await bus.start()

        result = await bus.publish("alert.fired", {"severity": "high"})

        assert isinstance(result, EventEnvelope)
        assert result.event_type == "alert.fired"
        assert result.payload == {"severity": "high"}
        mock_instance.send_and_wait.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("shieldops.messaging.consumer.AIOKafkaConsumer")
    @patch("shieldops.messaging.producer.AIOKafkaProducer")
    async def test_publish_sends_to_events_topic(self, mock_prod_cls, mock_cons_cls):
        mock_instance = AsyncMock()
        mock_prod_cls.return_value = mock_instance
        mock_cons_cls.return_value = AsyncMock()

        bus = EventBus(brokers="broker:9092", group_id="grp")
        await bus.start()
        await bus.publish("test.event", {})

        call_args = mock_instance.send_and_wait.call_args
        assert call_args[0][0] == EVENTS_TOPIC

    def test_producer_property(self):
        bus = EventBus(brokers="broker:9092", group_id="grp")
        assert bus.producer is bus._producer

    def test_consumer_property(self):
        bus = EventBus(brokers="broker:9092", group_id="grp")
        assert bus.consumer is bus._consumer
