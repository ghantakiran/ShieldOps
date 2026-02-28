"""Tests for shieldops.analytics.capacity_anomaly — CapacityAnomalyDetector."""

from __future__ import annotations

from shieldops.analytics.capacity_anomaly import (
    AnomalyPattern,
    AnomalyRecord,
    AnomalySeverity,
    AnomalyType,
    CapacityAnomalyDetector,
    CapacityAnomalyReport,
    ResourceType,
)


def _engine(**kw) -> CapacityAnomalyDetector:
    return CapacityAnomalyDetector(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # AnomalyType (5)
    def test_type_spike(self):
        assert AnomalyType.SPIKE == "spike"

    def test_type_drop(self):
        assert AnomalyType.DROP == "drop"

    def test_type_trend_shift(self):
        assert AnomalyType.TREND_SHIFT == "trend_shift"

    def test_type_seasonal_deviation(self):
        assert AnomalyType.SEASONAL_DEVIATION == "seasonal_deviation"

    def test_type_flatline(self):
        assert AnomalyType.FLATLINE == "flatline"

    # AnomalySeverity (5)
    def test_severity_critical(self):
        assert AnomalySeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert AnomalySeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert AnomalySeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert AnomalySeverity.LOW == "low"

    def test_severity_informational(self):
        assert AnomalySeverity.INFORMATIONAL == "informational"

    # ResourceType (5)
    def test_resource_cpu(self):
        assert ResourceType.CPU == "cpu"

    def test_resource_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_resource_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_resource_network(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_connections(self):
        assert ResourceType.CONNECTIONS == "connections"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_anomaly_record_defaults(self):
        r = AnomalyRecord()
        assert r.id
        assert r.service_name == ""
        assert r.anomaly_type == AnomalyType.SPIKE
        assert r.severity == AnomalySeverity.MODERATE
        assert r.resource == ResourceType.CPU
        assert r.confidence_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_anomaly_pattern_defaults(self):
        r = AnomalyPattern()
        assert r.id
        assert r.pattern_name == ""
        assert r.anomaly_type == AnomalyType.SPIKE
        assert r.severity == AnomalySeverity.MODERATE
        assert r.threshold_value == 0.0
        assert r.cooldown_minutes == 30
        assert r.created_at > 0

    def test_capacity_anomaly_report_defaults(self):
        r = CapacityAnomalyReport()
        assert r.total_anomalies == 0
        assert r.total_patterns == 0
        assert r.high_confidence_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_anomaly
# -------------------------------------------------------------------


class TestRecordAnomaly:
    def test_basic(self):
        eng = _engine()
        r = eng.record_anomaly("api-gateway", anomaly_type=AnomalyType.SPIKE)
        assert r.service_name == "api-gateway"
        assert r.anomaly_type == AnomalyType.SPIKE

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_anomaly(
            "payment-service",
            anomaly_type=AnomalyType.DROP,
            severity=AnomalySeverity.CRITICAL,
            resource=ResourceType.MEMORY,
            confidence_pct=95.0,
            details="Memory usage dropped suddenly",
        )
        assert r.severity == AnomalySeverity.CRITICAL
        assert r.resource == ResourceType.MEMORY
        assert r.confidence_pct == 95.0
        assert r.details == "Memory usage dropped suddenly"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_anomaly(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_anomaly
# -------------------------------------------------------------------


class TestGetAnomaly:
    def test_found(self):
        eng = _engine()
        r = eng.record_anomaly("api-gateway")
        assert eng.get_anomaly(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_anomaly("nonexistent") is None


# -------------------------------------------------------------------
# list_anomalies
# -------------------------------------------------------------------


class TestListAnomalies:
    def test_list_all(self):
        eng = _engine()
        eng.record_anomaly("svc-a")
        eng.record_anomaly("svc-b")
        assert len(eng.list_anomalies()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_anomaly("svc-a")
        eng.record_anomaly("svc-b")
        results = eng.list_anomalies(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_anomaly_type(self):
        eng = _engine()
        eng.record_anomaly("svc-a", anomaly_type=AnomalyType.SPIKE)
        eng.record_anomaly("svc-b", anomaly_type=AnomalyType.DROP)
        results = eng.list_anomalies(anomaly_type=AnomalyType.DROP)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_pattern
# -------------------------------------------------------------------


class TestAddPattern:
    def test_basic(self):
        eng = _engine()
        p = eng.add_pattern(
            "spike-detector",
            anomaly_type=AnomalyType.SPIKE,
            severity=AnomalySeverity.HIGH,
            threshold_value=85.0,
            cooldown_minutes=15,
        )
        assert p.pattern_name == "spike-detector"
        assert p.anomaly_type == AnomalyType.SPIKE
        assert p.threshold_value == 85.0
        assert p.cooldown_minutes == 15

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_pattern(f"pattern-{i}")
        assert len(eng._patterns) == 2


# -------------------------------------------------------------------
# analyze_anomaly_patterns
# -------------------------------------------------------------------


class TestAnalyzeAnomalyPatterns:
    def test_with_data(self):
        eng = _engine(min_confidence_pct=70.0)
        eng.record_anomaly("svc-a", confidence_pct=80.0)
        eng.record_anomaly("svc-a", confidence_pct=60.0)
        eng.record_anomaly("svc-a", confidence_pct=90.0)
        result = eng.analyze_anomaly_patterns("svc-a")
        assert result["avg_confidence"] == 76.67
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_anomaly_patterns("unknown-svc")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_confidence_pct=70.0)
        eng.record_anomaly("svc-a", confidence_pct=80.0)
        eng.record_anomaly("svc-a", confidence_pct=75.0)
        result = eng.analyze_anomaly_patterns("svc-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_critical_anomalies
# -------------------------------------------------------------------


class TestIdentifyCriticalAnomalies:
    def test_with_critical(self):
        eng = _engine()
        eng.record_anomaly("svc-a", severity=AnomalySeverity.CRITICAL)
        eng.record_anomaly("svc-a", severity=AnomalySeverity.HIGH)
        eng.record_anomaly("svc-b", severity=AnomalySeverity.LOW)
        results = eng.identify_critical_anomalies()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["critical_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_anomalies() == []

    def test_single_critical_not_returned(self):
        eng = _engine()
        eng.record_anomaly("svc-a", severity=AnomalySeverity.CRITICAL)
        assert eng.identify_critical_anomalies() == []


# -------------------------------------------------------------------
# rank_by_impact
# -------------------------------------------------------------------


class TestRankByImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_anomaly("svc-a", confidence_pct=20.0)
        eng.record_anomaly("svc-b", confidence_pct=90.0)
        results = eng.rank_by_impact()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_confidence_pct"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact() == []


# -------------------------------------------------------------------
# detect_recurring_anomalies
# -------------------------------------------------------------------


class TestDetectRecurringAnomalies:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_anomaly("svc-a")
        eng.record_anomaly("svc-b")
        results = eng.detect_recurring_anomalies()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_recurring_anomalies() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_anomaly("svc-a")
        assert eng.detect_recurring_anomalies() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_anomaly("svc-a", severity=AnomalySeverity.CRITICAL)
        eng.record_anomaly("svc-b", severity=AnomalySeverity.LOW)
        eng.add_pattern("pattern-1")
        report = eng.generate_report()
        assert report.total_anomalies == 2
        assert report.total_patterns == 1
        assert report.critical_count == 1
        assert report.by_type != {}
        assert report.by_severity != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_anomalies == 0
        assert report.high_confidence_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_anomaly("svc-a")
        eng.add_pattern("pattern-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._patterns) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_anomalies"] == 0
        assert stats["total_patterns"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_confidence_pct=75.0)
        eng.record_anomaly("svc-a", anomaly_type=AnomalyType.SPIKE)
        eng.record_anomaly("svc-b", anomaly_type=AnomalyType.DROP)
        eng.add_pattern("pattern-1")
        stats = eng.get_stats()
        assert stats["total_anomalies"] == 2
        assert stats["total_patterns"] == 1
        assert stats["unique_services"] == 2
        assert stats["min_confidence_pct"] == 75.0
