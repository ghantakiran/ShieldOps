"""Tests for shieldops.analytics.anomaly_scorer — MetricAnomalyScorer."""

from __future__ import annotations

from shieldops.analytics.anomaly_scorer import (
    AnomalyContext,
    AnomalyRecord,
    AnomalySeverity,
    AnomalySource,
    AnomalyType,
    MetricAnomalyReport,
    MetricAnomalyScorer,
)


def _engine(**kw) -> MetricAnomalyScorer:
    return MetricAnomalyScorer(**kw)


class TestEnums:
    def test_type_spike(self):
        assert AnomalyType.SPIKE == "spike"

    def test_type_drop(self):
        assert AnomalyType.DROP == "drop"

    def test_type_drift(self):
        assert AnomalyType.DRIFT == "drift"

    def test_type_oscillation(self):
        assert AnomalyType.OSCILLATION == "oscillation"

    def test_type_flatline(self):
        assert AnomalyType.FLATLINE == "flatline"

    def test_severity_critical(self):
        assert AnomalySeverity.CRITICAL == "critical"

    def test_severity_major(self):
        assert AnomalySeverity.MAJOR == "major"

    def test_severity_moderate(self):
        assert AnomalySeverity.MODERATE == "moderate"

    def test_severity_minor(self):
        assert AnomalySeverity.MINOR == "minor"

    def test_severity_noise(self):
        assert AnomalySeverity.NOISE == "noise"

    def test_source_application(self):
        assert AnomalySource.APPLICATION == "application"

    def test_source_infrastructure(self):
        assert AnomalySource.INFRASTRUCTURE == "infrastructure"

    def test_source_network(self):
        assert AnomalySource.NETWORK == "network"

    def test_source_database(self):
        assert AnomalySource.DATABASE == "database"

    def test_source_external(self):
        assert AnomalySource.EXTERNAL == "external"


class TestModels:
    def test_anomaly_record_defaults(self):
        r = AnomalyRecord()
        assert r.id
        assert r.metric_name == ""
        assert r.anomaly_type == AnomalyType.SPIKE
        assert r.severity == AnomalySeverity.NOISE
        assert r.source == AnomalySource.APPLICATION
        assert r.anomaly_score == 0.0
        assert r.service == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_anomaly_context_defaults(self):
        c = AnomalyContext()
        assert c.id
        assert c.record_id == ""
        assert c.context_metric == ""
        assert c.correlation_score == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_report_defaults(self):
        r = MetricAnomalyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_contexts == 0
        assert r.critical_anomalies == 0
        assert r.avg_anomaly_score == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.by_source == {}
        assert r.top_anomalies == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecordAnomaly:
    def test_basic(self):
        eng = _engine()
        r = eng.record_anomaly("cpu_usage", anomaly_score=85.0)
        assert r.metric_name == "cpu_usage"
        assert r.anomaly_score == 85.0

    def test_with_type(self):
        eng = _engine()
        r = eng.record_anomaly("latency_p99", anomaly_type=AnomalyType.DRIFT)
        assert r.anomaly_type == AnomalyType.DRIFT

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_anomaly(f"metric-{i}")
        assert len(eng._records) == 3


class TestGetAnomaly:
    def test_found(self):
        eng = _engine()
        r = eng.record_anomaly("metric-1")
        assert eng.get_anomaly(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_anomaly("nonexistent") is None


class TestListAnomalies:
    def test_list_all(self):
        eng = _engine()
        eng.record_anomaly("m1")
        eng.record_anomaly("m2")
        assert len(eng.list_anomalies()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_anomaly("m1", anomaly_type=AnomalyType.SPIKE)
        eng.record_anomaly("m2", anomaly_type=AnomalyType.DROP)
        results = eng.list_anomalies(anomaly_type=AnomalyType.SPIKE)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_anomaly("m1", severity=AnomalySeverity.CRITICAL)
        eng.record_anomaly("m2", severity=AnomalySeverity.NOISE)
        results = eng.list_anomalies(severity=AnomalySeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_anomaly("m1", source=AnomalySource.DATABASE)
        eng.record_anomaly("m2", source=AnomalySource.NETWORK)
        results = eng.list_anomalies(source=AnomalySource.DATABASE)
        assert len(results) == 1


class TestAddContext:
    def test_basic(self):
        eng = _engine()
        c = eng.add_context("rec-1", context_metric="error_rate", correlation_score=0.92)
        assert c.record_id == "rec-1"
        assert c.context_metric == "error_rate"
        assert c.correlation_score == 0.92

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_context(f"rec-{i}")
        assert len(eng._contexts) == 2


class TestAnalyzeAnomalyPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_anomaly("m1", anomaly_type=AnomalyType.SPIKE, anomaly_score=80.0)
        eng.record_anomaly("m2", anomaly_type=AnomalyType.SPIKE, anomaly_score=60.0)
        eng.record_anomaly("m3", anomaly_type=AnomalyType.DROP, anomaly_score=40.0)
        result = eng.analyze_anomaly_patterns()
        assert "spike" in result
        assert result["spike"]["count"] == 2
        assert result["spike"]["avg_anomaly_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_anomaly_patterns() == {}


class TestIdentifyCriticalAnomalies:
    def test_with_critical(self):
        eng = _engine(min_anomaly_score=70.0)
        eng.record_anomaly("hot-metric", anomaly_score=95.0, service="api")
        eng.record_anomaly("ok-metric", anomaly_score=30.0, service="worker")
        results = eng.identify_critical_anomalies()
        assert len(results) == 1
        assert results[0]["metric_name"] == "hot-metric"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_anomalies() == []


class TestRankByAnomalyScore:
    def test_descending_order(self):
        eng = _engine()
        eng.record_anomaly("m1", service="api", anomaly_score=90.0)
        eng.record_anomaly("m2", service="worker", anomaly_score=30.0)
        results = eng.rank_by_anomaly_score()
        assert results[0]["service"] == "api"
        assert results[0]["avg_anomaly_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_anomaly_score() == []


class TestDetectAnomalyTrends:
    def test_worsening(self):
        eng = _engine()
        for score in [20.0, 20.0, 90.0, 90.0]:
            eng.record_anomaly("m", anomaly_score=score)
        result = eng.detect_anomaly_trends()
        assert result["trend"] == "worsening"

    def test_improving(self):
        eng = _engine()
        for score in [90.0, 90.0, 20.0, 20.0]:
            eng.record_anomaly("m", anomaly_score=score)
        result = eng.detect_anomaly_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_anomaly("m1", anomaly_score=80.0)
        result = eng.detect_anomaly_trends()
        assert result["status"] == "insufficient_data"


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_anomaly_score=70.0)
        eng.record_anomaly("m1", severity=AnomalySeverity.CRITICAL, anomaly_score=95.0)
        eng.record_anomaly("m2", severity=AnomalySeverity.NOISE, anomaly_score=10.0)
        eng.add_context("rec-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_contexts == 1
        assert report.critical_anomalies == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_anomaly("m1")
        eng.add_context("rec-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._contexts) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_contexts"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_anomaly("m1", anomaly_type=AnomalyType.SPIKE, service="api")
        eng.record_anomaly("m2", anomaly_type=AnomalyType.DROP, service="worker")
        eng.add_context("rec-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_contexts"] == 1
        assert stats["unique_services"] == 2
