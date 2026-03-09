"""Tests for shieldops.observability.ml_anomaly_detection_engine — MlAnomalyDetectionEngine."""

from __future__ import annotations

from shieldops.observability.ml_anomaly_detection_engine import (
    AnomalyRecord,
    AnomalySeverity,
    AnomalyType,
    DetectionMethod,
    MlAnomalyDetectionEngine,
    TrendDirection,
)


def _engine(**kw) -> MlAnomalyDetectionEngine:
    return MlAnomalyDetectionEngine(**kw)


class TestEnums:
    def test_anomaly_type_point(self):
        assert AnomalyType.POINT == "point"

    def test_detection_method(self):
        assert DetectionMethod.Z_SCORE == "z_score"

    def test_severity(self):
        assert AnomalySeverity.CRITICAL == "critical"

    def test_trend(self):
        assert TrendDirection.INCREASING == "increasing"


class TestModels:
    def test_record_defaults(self):
        r = AnomalyRecord()
        assert r.id
        assert r.value == 0.0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(metric_name="cpu_usage", value=95.0, expected_value=50.0)
        assert rec.metric_name == "cpu_usage"
        assert rec.value == 95.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(metric_name=f"m-{i}", value=float(i))
        assert len(eng._records) == 3


class TestZScores:
    def test_basic(self):
        eng = _engine()
        for i in range(10):
            eng.add_record(metric_name="cpu", value=50.0 + i, service="api")
        result = eng.compute_z_scores("cpu")
        assert isinstance(result, dict)


class TestIsolationScore:
    def test_basic(self):
        eng = _engine()
        for i in range(5):
            eng.add_record(metric_name="mem", value=float(i * 10))
        result = eng.compute_isolation_score("mem")
        assert isinstance(result, dict)


class TestSeasonalDecompose:
    def test_basic(self):
        eng = _engine()
        for i in range(20):
            eng.add_record(metric_name="latency", value=float(i % 7 * 10), service="api")
        result = eng.decompose_seasonal("latency")
        assert result is not None


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", value=99.0, service="api")
        result = eng.process("api")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", value=99.0)
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", value=50.0)
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", value=50.0)
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
