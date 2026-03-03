"""Tests for shieldops.observability.event_driven_observability_tracker

EventDrivenObservabilityTracker.
"""

from __future__ import annotations

from shieldops.observability.event_driven_observability_tracker import (
    EventBusAnalysis,
    EventBusRecord,
    EventBusType,
    EventDrivenObservabilityReport,
    EventDrivenObservabilityTracker,
    EventHealth,
    EventSource,
)


def _engine(**kw) -> EventDrivenObservabilityTracker:
    return EventDrivenObservabilityTracker(**kw)


class TestEnums:
    def test_event_bus_type_kafka(self):
        assert EventBusType.KAFKA == "kafka"

    def test_event_bus_type_rabbitmq(self):
        assert EventBusType.RABBITMQ == "rabbitmq"

    def test_event_bus_type_sqs(self):
        assert EventBusType.SQS == "sqs"

    def test_event_bus_type_pubsub(self):
        assert EventBusType.PUBSUB == "pubsub"

    def test_event_bus_type_nats(self):
        assert EventBusType.NATS == "nats"

    def test_event_source_producer(self):
        assert EventSource.PRODUCER == "producer"

    def test_event_source_consumer(self):
        assert EventSource.CONSUMER == "consumer"

    def test_event_source_broker(self):
        assert EventSource.BROKER == "broker"

    def test_event_source_connector(self):
        assert EventSource.CONNECTOR == "connector"

    def test_event_source_stream(self):
        assert EventSource.STREAM == "stream"

    def test_event_health_healthy(self):
        assert EventHealth.HEALTHY == "healthy"

    def test_event_health_lagging(self):
        assert EventHealth.LAGGING == "lagging"

    def test_event_health_backpressure(self):
        assert EventHealth.BACKPRESSURE == "backpressure"

    def test_event_health_stalled(self):
        assert EventHealth.STALLED == "stalled"

    def test_event_health_dead_letter(self):
        assert EventHealth.DEAD_LETTER == "dead_letter"


class TestModels:
    def test_record_defaults(self):
        r = EventBusRecord()
        assert r.id
        assert r.name == ""
        assert r.event_bus_type == EventBusType.KAFKA
        assert r.event_source == EventSource.PRODUCER
        assert r.event_health == EventHealth.DEAD_LETTER
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = EventBusAnalysis()
        assert a.id
        assert a.name == ""
        assert a.event_bus_type == EventBusType.KAFKA
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = EventDrivenObservabilityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_event_bus_type == {}
        assert r.by_event_source == {}
        assert r.by_event_health == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            event_bus_type=EventBusType.KAFKA,
            event_source=EventSource.CONSUMER,
            event_health=EventHealth.HEALTHY,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.event_bus_type == EventBusType.KAFKA
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_event_bus_type(self):
        eng = _engine()
        eng.record_entry(name="a", event_bus_type=EventBusType.KAFKA)
        eng.record_entry(name="b", event_bus_type=EventBusType.RABBITMQ)
        assert len(eng.list_records(event_bus_type=EventBusType.KAFKA)) == 1

    def test_filter_by_event_source(self):
        eng = _engine()
        eng.record_entry(name="a", event_source=EventSource.PRODUCER)
        eng.record_entry(name="b", event_source=EventSource.CONSUMER)
        assert len(eng.list_records(event_source=EventSource.PRODUCER)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", event_bus_type=EventBusType.RABBITMQ, score=90.0)
        eng.record_entry(name="b", event_bus_type=EventBusType.RABBITMQ, score=70.0)
        result = eng.analyze_distribution()
        assert "rabbitmq" in result
        assert result["rabbitmq"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
