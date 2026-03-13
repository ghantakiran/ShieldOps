"""Tests for MessageThroughputForecaster."""

from __future__ import annotations

from shieldops.analytics.message_throughput_forecaster import (
    BottleneckType,
    ForecastWindow,
    MessageThroughputForecaster,
    ScalingUrgency,
)


def _engine(**kw) -> MessageThroughputForecaster:
    return MessageThroughputForecaster(**kw)


class TestEnums:
    def test_forecast_window_values(self):
        for v in ForecastWindow:
            assert isinstance(v.value, str)

    def test_bottleneck_type_values(self):
        for v in BottleneckType:
            assert isinstance(v.value, str)

    def test_scaling_urgency_values(self):
        for v in ScalingUrgency:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(topic_name="t1")
        assert r.topic_name == "t1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(topic_name=f"t-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().add_record()
        assert r.forecast_window == (ForecastWindow.HOURLY)


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            topic_name="t1",
            current_throughput=1000.0,
            capacity_pct=85.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "topic_name")
        assert a.topic_name == "t1"
        assert a.bottleneck_detected is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(topic_name="t1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_urgent_topics(self):
        eng = _engine()
        eng.add_record(
            topic_name="t1",
            scaling_urgency=(ScalingUrgency.IMMEDIATE),
        )
        rpt = eng.generate_report()
        assert len(rpt.urgent_topics) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(topic_name="t1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(topic_name="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestForecastThroughputDemand:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            topic_name="t1",
            current_throughput=1000.0,
        )
        result = eng.forecast_throughput_demand()
        assert len(result) == 1
        assert result[0]["forecast_demand"] == 1200.0

    def test_empty(self):
        r = _engine().forecast_throughput_demand()
        assert r == []


class TestDetectThroughputBottlenecks:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(topic_name="t1", capacity_pct=90.0)
        result = eng.detect_throughput_bottlenecks()
        assert len(result) == 1

    def test_no_bottleneck(self):
        eng = _engine()
        eng.add_record(topic_name="t1", capacity_pct=50.0)
        r = eng.detect_throughput_bottlenecks()
        assert r == []


class TestRankTopicsByScalingUrgency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            topic_name="t1",
            scaling_urgency=(ScalingUrgency.IMMEDIATE),
            capacity_pct=95.0,
        )
        eng.add_record(
            topic_name="t2",
            scaling_urgency=ScalingUrgency.NONE,
            capacity_pct=20.0,
        )
        result = eng.rank_topics_by_scaling_urgency()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_topics_by_scaling_urgency()
        assert r == []
