"""Tests for TrafficPatternIntelligence."""

from __future__ import annotations

from shieldops.topology.traffic_pattern_intelligence import (
    AnomalySeverity,
    PatternType,
    TrafficPatternIntelligence,
    TrafficTrend,
)


def _engine(**kw) -> TrafficPatternIntelligence:
    return TrafficPatternIntelligence(**kw)


class TestEnums:
    def test_pattern_type_values(self):
        for v in PatternType:
            assert isinstance(v.value, str)

    def test_traffic_trend_values(self):
        for v in TrafficTrend:
            assert isinstance(v.value, str)

    def test_anomaly_severity_values(self):
        for v in AnomalySeverity:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(service="svc-a")
        assert r.service == "svc-a"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(service=f"svc-{i}")
        assert len(eng._records) == 5

    def test_all_fields(self):
        eng = _engine()
        r = eng.record_item(
            service="svc-a",
            pattern_type=PatternType.ANOMALOUS,
            deviation_pct=150.0,
        )
        assert r.deviation_pct == 150.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            service="svc-a",
            deviation_pct=50.0,
        )
        a = eng.process(r.id)
        assert a.deviation_pct == 50.0

    def test_anomalous(self):
        eng = _engine()
        r = eng.record_item(
            service="svc-a",
            pattern_type=PatternType.ANOMALOUS,
        )
        a = eng.process(r.id)
        assert a.is_anomalous is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(service="svc-a")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_anomalous_services(self):
        eng = _engine()
        eng.record_item(
            service="svc-a",
            pattern_type=PatternType.ANOMALOUS,
        )
        rpt = eng.generate_report()
        assert len(rpt.anomalous_services) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(service="svc-a")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(service="svc-a")
        eng.clear_data()
        assert len(eng._records) == 0


class TestDetectTrafficAnomalies:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            service="svc-a",
            pattern_type=PatternType.ANOMALOUS,
            deviation_pct=200.0,
        )
        result = eng.detect_traffic_anomalies()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_traffic_anomalies() == []


class TestClassifyTrafficSeasonality:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            service="svc-a",
            pattern_type=PatternType.SEASONAL,
        )
        result = eng.classify_traffic_seasonality()
        assert len(result) == 1
        assert result[0]["dominant_pattern"] == "seasonal"

    def test_empty(self):
        assert _engine().classify_traffic_seasonality() == []


class TestPredictTrafficShift:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            service="svc-a",
            traffic_trend=TrafficTrend.GROWING,
            request_rate=1000.0,
        )
        result = eng.predict_traffic_shift()
        assert len(result) == 1
        assert result[0]["trend"] == "growing"

    def test_empty(self):
        assert _engine().predict_traffic_shift() == []
