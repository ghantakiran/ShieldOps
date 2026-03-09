"""Tests for shieldops.observability.realtime_streaming_analytics — RealtimeStreamingAnalytics."""

from __future__ import annotations

from shieldops.observability.realtime_streaming_analytics import (
    ArrivalStatus,
    RealtimeStreamingAnalytics,
    StreamingReport,
    StreamRecord,
    StreamStatus,
    WindowType,
)


def _engine(**kw) -> RealtimeStreamingAnalytics:
    return RealtimeStreamingAnalytics(**kw)


class TestEnums:
    def test_window_tumbling(self):
        assert WindowType.TUMBLING == "tumbling"

    def test_stream_status(self):
        assert StreamStatus.HEALTHY == "healthy"

    def test_arrival_on_time(self):
        assert ArrivalStatus.ON_TIME == "on_time"


class TestModels:
    def test_record_defaults(self):
        r = StreamRecord()
        assert r.id
        assert r.created_at > 0

    def test_report_defaults(self):
        r = StreamingReport()
        assert r.total_records == 0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(stream_name="clicks", events_per_second=1000.0)
        assert rec.stream_name == "clicks"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(stream_name=f"s-{i}")
        assert len(eng._records) == 3


class TestWindowedAggregation:
    def test_basic(self):
        eng = _engine()
        eng.add_record(stream_name="events", events_per_second=100.0)
        eng.add_record(stream_name="events", events_per_second=200.0)
        result = eng.compute_windowed_aggregation("events")
        assert isinstance(result, dict)


class TestBackpressure:
    def test_basic(self):
        eng = _engine()
        eng.add_record(stream_name="events", events_per_second=100.0)
        result = eng.detect_backpressure()
        assert isinstance(result, list)


class TestLateArrivals:
    def test_basic(self):
        eng = _engine()
        eng.add_record(stream_name="events", arrival_status=ArrivalStatus.LATE)
        result = eng.analyze_late_arrivals()
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(stream_name="events", service="api")
        result = eng.process("events")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(stream_name="events")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(stream_name="events")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(stream_name="events")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
