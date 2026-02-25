"""Tests for shieldops.observability.queue_depth_forecast — QueueDepthForecaster."""

from __future__ import annotations

from shieldops.observability.queue_depth_forecast import (
    BacklogTrend,
    OverflowRisk,
    QueueDepthForecaster,
    QueueDepthRecord,
    QueueDepthReport,
    QueueForecast,
    QueueType,
)


def _engine(**kw) -> QueueDepthForecaster:
    return QueueDepthForecaster(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # QueueType (5)
    def test_type_kafka(self):
        assert QueueType.KAFKA == "kafka"

    def test_type_rabbitmq(self):
        assert QueueType.RABBITMQ == "rabbitmq"

    def test_type_sqs(self):
        assert QueueType.SQS == "sqs"

    def test_type_pubsub(self):
        assert QueueType.PUBSUB == "pubsub"

    def test_type_redis_stream(self):
        assert QueueType.REDIS_STREAM == "redis_stream"

    # BacklogTrend (5)
    def test_trend_growing(self):
        assert BacklogTrend.GROWING == "growing"

    def test_trend_stable(self):
        assert BacklogTrend.STABLE == "stable"

    def test_trend_shrinking(self):
        assert BacklogTrend.SHRINKING == "shrinking"

    def test_trend_oscillating(self):
        assert BacklogTrend.OSCILLATING == "oscillating"

    def test_trend_empty(self):
        assert BacklogTrend.EMPTY == "empty"

    # OverflowRisk (5)
    def test_risk_critical(self):
        assert OverflowRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert OverflowRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert OverflowRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert OverflowRisk.LOW == "low"

    def test_risk_none(self):
        assert OverflowRisk.NONE == "none"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_queue_depth_record_defaults(self):
        r = QueueDepthRecord()
        assert r.id
        assert r.queue_name == ""
        assert r.queue_type == QueueType.KAFKA
        assert r.current_depth == 0
        assert r.consumer_count == 0
        assert r.producer_rate == 0.0
        assert r.consumer_rate == 0.0
        assert r.trend == BacklogTrend.STABLE
        assert r.details == ""
        assert r.created_at > 0

    def test_queue_forecast_defaults(self):
        r = QueueForecast()
        assert r.id
        assert r.queue_name == ""
        assert r.predicted_depth == 0
        assert r.overflow_risk == OverflowRisk.NONE
        assert r.time_to_overflow_minutes == 0.0
        assert r.recommended_consumers == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_queue_depth_report_defaults(self):
        r = QueueDepthReport()
        assert r.total_depths == 0
        assert r.total_forecasts == 0
        assert r.avg_depth == 0.0
        assert r.by_type == {}
        assert r.by_trend == {}
        assert r.at_risk_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_depth
# -------------------------------------------------------------------


class TestRecordDepth:
    def test_basic(self):
        eng = _engine()
        r = eng.record_depth("orders-queue", current_depth=5000, consumer_count=3)
        assert r.queue_name == "orders-queue"
        assert r.current_depth == 5000
        assert r.consumer_count == 3
        assert r.queue_type == QueueType.KAFKA

    def test_with_type_and_trend(self):
        eng = _engine()
        r = eng.record_depth(
            "events-queue",
            queue_type=QueueType.RABBITMQ,
            trend=BacklogTrend.GROWING,
            producer_rate=1000.0,
            consumer_rate=500.0,
        )
        assert r.queue_type == QueueType.RABBITMQ
        assert r.trend == BacklogTrend.GROWING
        assert r.producer_rate == 1000.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_depth(f"q-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_depth
# -------------------------------------------------------------------


class TestGetDepth:
    def test_found(self):
        eng = _engine()
        r = eng.record_depth("orders-queue")
        assert eng.get_depth(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_depth("nonexistent") is None


# -------------------------------------------------------------------
# list_depths
# -------------------------------------------------------------------


class TestListDepths:
    def test_list_all(self):
        eng = _engine()
        eng.record_depth("q-a")
        eng.record_depth("q-b")
        assert len(eng.list_depths()) == 2

    def test_filter_by_queue_name(self):
        eng = _engine()
        eng.record_depth("q-a")
        eng.record_depth("q-b")
        results = eng.list_depths(queue_name="q-a")
        assert len(results) == 1
        assert results[0].queue_name == "q-a"

    def test_filter_by_queue_type(self):
        eng = _engine()
        eng.record_depth("q-a", queue_type=QueueType.KAFKA)
        eng.record_depth("q-b", queue_type=QueueType.SQS)
        results = eng.list_depths(queue_type=QueueType.SQS)
        assert len(results) == 1
        assert results[0].queue_name == "q-b"


# -------------------------------------------------------------------
# create_forecast
# -------------------------------------------------------------------


class TestCreateForecast:
    def test_basic(self):
        eng = _engine()
        f = eng.create_forecast(
            "orders-queue",
            predicted_depth=150000,
            overflow_risk=OverflowRisk.HIGH,
            time_to_overflow_minutes=45.0,
            recommended_consumers=5,
        )
        assert f.queue_name == "orders-queue"
        assert f.predicted_depth == 150000
        assert f.overflow_risk == OverflowRisk.HIGH
        assert f.time_to_overflow_minutes == 45.0
        assert f.recommended_consumers == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.create_forecast(f"q-{i}")
        assert len(eng._forecasts) == 2


# -------------------------------------------------------------------
# analyze_queue_health
# -------------------------------------------------------------------


class TestAnalyzeQueueHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_depth("q-a", current_depth=1000, trend=BacklogTrend.STABLE)
        eng.record_depth("q-a", current_depth=2000, trend=BacklogTrend.GROWING)
        eng.create_forecast("q-a", predicted_depth=5000)
        result = eng.analyze_queue_health("q-a")
        assert result["queue_name"] == "q-a"
        assert result["total_depths"] == 2
        assert result["total_forecasts"] == 1
        assert result["avg_depth"] == 1500.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_queue_health("unknown")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_at_risk_queues
# -------------------------------------------------------------------


class TestIdentifyAtRiskQueues:
    def test_above_threshold(self):
        eng = _engine(overflow_threshold=100000)
        eng.record_depth("q-a", current_depth=150000)
        eng.record_depth("q-b", current_depth=50000)
        results = eng.identify_at_risk_queues()
        assert len(results) == 1
        assert results[0]["queue_name"] == "q-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_at_risk_queues() == []


# -------------------------------------------------------------------
# rank_by_backlog_growth
# -------------------------------------------------------------------


class TestRankByBacklogGrowth:
    def test_with_data(self):
        eng = _engine()
        eng.record_depth("q-a", producer_rate=1000.0, consumer_rate=500.0)
        eng.record_depth("q-b", producer_rate=200.0, consumer_rate=300.0)
        results = eng.rank_by_backlog_growth()
        assert len(results) == 2
        # q-a: growth=500, q-b: growth=-100 — sorted desc
        assert results[0]["queue_name"] == "q-a"
        assert results[0]["avg_growth_rate"] == 500.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_backlog_growth() == []


# -------------------------------------------------------------------
# estimate_consumer_scaling
# -------------------------------------------------------------------


class TestEstimateConsumerScaling:
    def test_needs_scaling(self):
        eng = _engine()
        eng.record_depth(
            "q-a",
            producer_rate=1000.0,
            consumer_rate=500.0,
            consumer_count=5,
        )
        results = eng.estimate_consumer_scaling()
        assert len(results) == 1
        assert results[0]["queue_name"] == "q-a"
        assert results[0]["additional_consumers_needed"] == 5

    def test_no_scaling_needed(self):
        eng = _engine()
        eng.record_depth(
            "q-a",
            producer_rate=500.0,
            consumer_rate=1000.0,
            consumer_count=5,
        )
        results = eng.estimate_consumer_scaling()
        assert len(results) == 0

    def test_empty(self):
        eng = _engine()
        assert eng.estimate_consumer_scaling() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(overflow_threshold=1000)
        eng.record_depth(
            "q-a", current_depth=5000, producer_rate=100.0, consumer_rate=50.0, consumer_count=2
        )
        eng.create_forecast("q-a", predicted_depth=10000)
        report = eng.generate_report()
        assert report.total_depths == 1
        assert report.total_forecasts == 1
        assert report.at_risk_count == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_depths == 0
        assert "good" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_depth("q")
        eng.create_forecast("q")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._forecasts) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_depths"] == 0
        assert stats["total_forecasts"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_depth("q-a")
        eng.record_depth("q-b")
        eng.create_forecast("q-a")
        stats = eng.get_stats()
        assert stats["total_depths"] == 2
        assert stats["total_forecasts"] == 1
        assert stats["unique_queues"] == 2
        assert stats["overflow_threshold"] == 100000
