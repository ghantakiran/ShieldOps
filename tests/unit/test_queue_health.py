"""Tests for shieldops.observability.queue_health — QueueHealthMonitor."""

from __future__ import annotations

from shieldops.observability.queue_health import (
    ConsumerGroup,
    ConsumerState,
    QueueHealthMonitor,
    QueueHealthStatus,
    QueueHealthSummary,
    QueueMetric,
    QueueType,
)


def _engine(**kw) -> QueueHealthMonitor:
    return QueueHealthMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # QueueType (6)
    def test_type_kafka(self):
        assert QueueType.KAFKA == "kafka"

    def test_type_rabbitmq(self):
        assert QueueType.RABBITMQ == "rabbitmq"

    def test_type_sqs(self):
        assert QueueType.SQS == "sqs"

    def test_type_redis(self):
        assert QueueType.REDIS == "redis"

    def test_type_pubsub(self):
        assert QueueType.PUBSUB == "pubsub"

    def test_type_nats(self):
        assert QueueType.NATS == "nats"

    # QueueHealthStatus (5)
    def test_status_healthy(self):
        assert QueueHealthStatus.HEALTHY == "healthy"

    def test_status_warning(self):
        assert QueueHealthStatus.WARNING == "warning"

    def test_status_critical(self):
        assert QueueHealthStatus.CRITICAL == "critical"

    def test_status_stalled(self):
        assert QueueHealthStatus.STALLED == "stalled"

    def test_status_unknown(self):
        assert QueueHealthStatus.UNKNOWN == "unknown"

    # ConsumerState (4)
    def test_consumer_active(self):
        assert ConsumerState.ACTIVE == "active"

    def test_consumer_lagging(self):
        assert ConsumerState.LAGGING == "lagging"

    def test_consumer_idle(self):
        assert ConsumerState.IDLE == "idle"

    def test_consumer_disconnected(self):
        assert ConsumerState.DISCONNECTED == "disconnected"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_queue_metric_defaults(self):
        m = QueueMetric()
        assert m.id
        assert m.queue_type == QueueType.KAFKA
        assert m.status == QueueHealthStatus.UNKNOWN
        assert m.depth == 0

    def test_consumer_group_defaults(self):
        g = ConsumerGroup()
        assert g.id
        assert g.state == ConsumerState.ACTIVE
        assert g.lag == 0

    def test_queue_health_summary_defaults(self):
        s = QueueHealthSummary()
        assert s.total_queues == 0
        assert s.recommendations == []


# ---------------------------------------------------------------------------
# record_metric
# ---------------------------------------------------------------------------


class TestRecordMetric:
    def test_basic_healthy(self):
        eng = _engine()
        m = eng.record_metric(queue_name="orders", queue_type=QueueType.KAFKA, depth=100)
        assert m.queue_name == "orders"
        assert m.status == QueueHealthStatus.HEALTHY

    def test_warning_depth(self):
        eng = _engine()
        m = eng.record_metric(queue_name="orders", queue_type=QueueType.KAFKA, depth=1500)
        assert m.status == QueueHealthStatus.WARNING

    def test_critical_depth(self):
        eng = _engine()
        m = eng.record_metric(queue_name="orders", queue_type=QueueType.KAFKA, depth=15000)
        assert m.status == QueueHealthStatus.CRITICAL

    def test_stalled_old_message(self):
        eng = _engine(stall_threshold_seconds=300)
        m = eng.record_metric(
            queue_name="orders",
            queue_type=QueueType.KAFKA,
            depth=500,
            oldest_message_age_seconds=600.0,
        )
        assert m.status == QueueHealthStatus.STALLED

    def test_eviction(self):
        eng = _engine(max_metrics=3)
        for i in range(5):
            eng.record_metric(queue_name=f"q-{i}", queue_type=QueueType.KAFKA, depth=10)
        assert len(eng._metrics) == 3


# ---------------------------------------------------------------------------
# get_metric
# ---------------------------------------------------------------------------


class TestGetMetric:
    def test_found(self):
        eng = _engine()
        m = eng.record_metric("orders", QueueType.KAFKA, 10)
        assert eng.get_metric(m.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_metric("nonexistent") is None


# ---------------------------------------------------------------------------
# list_metrics
# ---------------------------------------------------------------------------


class TestListMetrics:
    def test_list_all(self):
        eng = _engine()
        eng.record_metric("q1", QueueType.KAFKA, 10)
        eng.record_metric("q2", QueueType.SQS, 20)
        assert len(eng.list_metrics()) == 2

    def test_filter_queue_name(self):
        eng = _engine()
        eng.record_metric("q1", QueueType.KAFKA, 10)
        eng.record_metric("q2", QueueType.KAFKA, 20)
        results = eng.list_metrics(queue_name="q1")
        assert len(results) == 1
        assert results[0].queue_name == "q1"

    def test_filter_queue_type(self):
        eng = _engine()
        eng.record_metric("q1", QueueType.KAFKA, 10)
        eng.record_metric("q2", QueueType.SQS, 20)
        results = eng.list_metrics(queue_type=QueueType.SQS)
        assert len(results) == 1
        assert results[0].queue_type == QueueType.SQS


# ---------------------------------------------------------------------------
# register_consumer_group
# ---------------------------------------------------------------------------


class TestRegisterConsumerGroup:
    def test_active(self):
        eng = _engine()
        g = eng.register_consumer_group("grp1", "orders", consumer_count=2, lag=100)
        assert g.state == ConsumerState.ACTIVE

    def test_lagging(self):
        eng = _engine()
        g = eng.register_consumer_group("grp1", "orders", consumer_count=2, lag=2000)
        assert g.state == ConsumerState.LAGGING

    def test_idle(self):
        eng = _engine()
        g = eng.register_consumer_group("grp1", "orders", consumer_count=2, lag=0)
        assert g.state == ConsumerState.IDLE

    def test_disconnected(self):
        eng = _engine()
        g = eng.register_consumer_group("grp1", "orders", consumer_count=0, lag=0)
        assert g.state == ConsumerState.DISCONNECTED


# ---------------------------------------------------------------------------
# list_consumer_groups
# ---------------------------------------------------------------------------


class TestListConsumerGroups:
    def test_list_all(self):
        eng = _engine()
        eng.register_consumer_group("g1", "q1")
        eng.register_consumer_group("g2", "q2")
        assert len(eng.list_consumer_groups()) == 2

    def test_filter_queue_name(self):
        eng = _engine()
        eng.register_consumer_group("g1", "q1")
        eng.register_consumer_group("g2", "q2")
        results = eng.list_consumer_groups(queue_name="q1")
        assert len(results) == 1
        assert results[0].queue_name == "q1"


# ---------------------------------------------------------------------------
# detect_stalled_queues
# ---------------------------------------------------------------------------


class TestDetectStalledQueues:
    def test_none(self):
        eng = _engine()
        eng.record_metric("orders", QueueType.KAFKA, 10)
        assert len(eng.detect_stalled_queues()) == 0

    def test_some_stalled(self):
        eng = _engine(stall_threshold_seconds=300)
        eng.record_metric("orders", QueueType.KAFKA, 10, oldest_message_age_seconds=600.0)
        stalled = eng.detect_stalled_queues()
        assert len(stalled) == 1
        assert stalled[0].status == QueueHealthStatus.STALLED


# ---------------------------------------------------------------------------
# analyze_throughput
# ---------------------------------------------------------------------------


class TestAnalyzeThroughput:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_throughput()
        assert result == {}

    def test_with_data(self):
        eng = _engine()
        eng.record_metric("orders", QueueType.KAFKA, 100, enqueue_rate=50.0, dequeue_rate=40.0)
        result = eng.analyze_throughput()
        assert "orders" in result
        assert result["orders"]["avg_enqueue_rate"] == 50.0
        assert result["orders"]["sample_count"] == 1


# ---------------------------------------------------------------------------
# generate_health_summary
# ---------------------------------------------------------------------------


class TestGenerateHealthSummary:
    def test_basic_summary(self):
        eng = _engine()
        eng.record_metric("q1", QueueType.KAFKA, 10)
        eng.record_metric("q2", QueueType.KAFKA, 5000)
        summary = eng.generate_health_summary()
        assert summary.total_queues == 2
        total = (
            summary.healthy_count
            + summary.warning_count
            + summary.critical_count
            + summary.stalled_count
        )
        assert total == 2


# ---------------------------------------------------------------------------
# detect_consumer_lag
# ---------------------------------------------------------------------------


class TestDetectConsumerLag:
    def test_no_lag(self):
        eng = _engine()
        eng.register_consumer_group("g1", "q1", consumer_count=2, lag=100)
        assert len(eng.detect_consumer_lag()) == 0

    def test_with_lag(self):
        eng = _engine()
        eng.register_consumer_group("g1", "q1", consumer_count=2, lag=2000)
        lagging = eng.detect_consumer_lag()
        assert len(lagging) == 1
        assert lagging[0].state == ConsumerState.LAGGING


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_metrics"] == 0
        assert stats["total_consumer_groups"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_metric("orders", QueueType.KAFKA, 10)
        eng.register_consumer_group("g1", "orders")
        stats = eng.get_stats()
        assert stats["total_metrics"] == 1
        assert stats["total_consumer_groups"] == 1
        assert stats["unique_queues"] == 1
        assert "orders" in stats["queue_names"]
