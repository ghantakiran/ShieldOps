"""Tests for shieldops.analytics.bottleneck_detector — CapacityBottleneckDetector."""

from __future__ import annotations

from shieldops.analytics.bottleneck_detector import (
    BottleneckEvent,
    BottleneckRecord,
    BottleneckSeverity,
    BottleneckTrend,
    BottleneckType,
    CapacityBottleneckDetector,
    CapacityBottleneckReport,
)


def _engine(**kw) -> CapacityBottleneckDetector:
    return CapacityBottleneckDetector(**kw)


class TestEnums:
    def test_type_cpu(self):
        assert BottleneckType.CPU == "cpu"

    def test_type_memory(self):
        assert BottleneckType.MEMORY == "memory"

    def test_type_disk_io(self):
        assert BottleneckType.DISK_IO == "disk_io"

    def test_type_network(self):
        assert BottleneckType.NETWORK == "network"

    def test_type_connection_pool(self):
        assert BottleneckType.CONNECTION_POOL == "connection_pool"

    def test_severity_critical(self):
        assert BottleneckSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert BottleneckSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert BottleneckSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert BottleneckSeverity.LOW == "low"

    def test_severity_none(self):
        assert BottleneckSeverity.NONE == "none"

    def test_trend_worsening(self):
        assert BottleneckTrend.WORSENING == "worsening"

    def test_trend_stable(self):
        assert BottleneckTrend.STABLE == "stable"

    def test_trend_improving(self):
        assert BottleneckTrend.IMPROVING == "improving"

    def test_trend_resolved(self):
        assert BottleneckTrend.RESOLVED == "resolved"

    def test_trend_recurring(self):
        assert BottleneckTrend.RECURRING == "recurring"


class TestModels:
    def test_bottleneck_record_defaults(self):
        r = BottleneckRecord()
        assert r.id
        assert r.service == ""
        assert r.bottleneck_type == BottleneckType.CPU
        assert r.severity == BottleneckSeverity.NONE
        assert r.utilization_pct == 0.0
        assert r.duration_minutes == 0.0
        assert r.team == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_bottleneck_event_defaults(self):
        e = BottleneckEvent()
        assert e.id
        assert e.record_id == ""
        assert e.event_type == ""
        assert e.impact_score == 0.0
        assert e.affected_users == 0
        assert e.created_at > 0

    def test_report_defaults(self):
        r = CapacityBottleneckReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_events == 0
        assert r.critical_bottlenecks == 0
        assert r.avg_utilization_pct == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.most_constrained == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecordBottleneck:
    def test_basic(self):
        eng = _engine()
        r = eng.record_bottleneck("api-service", utilization_pct=85.0)
        assert r.service == "api-service"
        assert r.utilization_pct == 85.0

    def test_with_severity(self):
        eng = _engine()
        r = eng.record_bottleneck("db", severity=BottleneckSeverity.CRITICAL)
        assert r.severity == BottleneckSeverity.CRITICAL

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_bottleneck(f"svc-{i}")
        assert len(eng._records) == 3


class TestGetBottleneck:
    def test_found(self):
        eng = _engine()
        r = eng.record_bottleneck("svc-1")
        assert eng.get_bottleneck(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_bottleneck("nonexistent") is None


class TestListBottlenecks:
    def test_list_all(self):
        eng = _engine()
        eng.record_bottleneck("svc-1")
        eng.record_bottleneck("svc-2")
        assert len(eng.list_bottlenecks()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_bottleneck("svc-1", bottleneck_type=BottleneckType.CPU)
        eng.record_bottleneck("svc-2", bottleneck_type=BottleneckType.MEMORY)
        results = eng.list_bottlenecks(bottleneck_type=BottleneckType.CPU)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_bottleneck("svc-1", severity=BottleneckSeverity.CRITICAL)
        eng.record_bottleneck("svc-2", severity=BottleneckSeverity.LOW)
        results = eng.list_bottlenecks(severity=BottleneckSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_bottleneck("api")
        eng.record_bottleneck("worker")
        results = eng.list_bottlenecks(service="api")
        assert len(results) == 1


class TestAddEvent:
    def test_basic(self):
        eng = _engine()
        e = eng.add_event("rec-1", event_type="spike", impact_score=8.5, affected_users=500)
        assert e.record_id == "rec-1"
        assert e.event_type == "spike"
        assert e.impact_score == 8.5
        assert e.affected_users == 500

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_event(f"rec-{i}")
        assert len(eng._events) == 2


class TestAnalyzeBottleneckPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_bottleneck("svc-1", bottleneck_type=BottleneckType.CPU, utilization_pct=80.0)
        eng.record_bottleneck("svc-2", bottleneck_type=BottleneckType.CPU, utilization_pct=60.0)
        eng.record_bottleneck("svc-3", bottleneck_type=BottleneckType.MEMORY, utilization_pct=50.0)
        result = eng.analyze_bottleneck_patterns()
        assert "cpu" in result
        assert result["cpu"]["count"] == 2
        assert result["cpu"]["avg_utilization_pct"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_bottleneck_patterns() == {}


class TestIdentifyCriticalBottlenecks:
    def test_with_critical(self):
        eng = _engine(critical_utilization_pct=90.0)
        eng.record_bottleneck("hot-svc", utilization_pct=95.0)
        eng.record_bottleneck("ok-svc", utilization_pct=70.0)
        results = eng.identify_critical_bottlenecks()
        assert len(results) == 1
        assert results[0]["service"] == "hot-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_bottlenecks() == []


class TestRankByUtilization:
    def test_descending_order(self):
        eng = _engine()
        eng.record_bottleneck("api", utilization_pct=90.0)
        eng.record_bottleneck("worker", utilization_pct=40.0)
        results = eng.rank_by_utilization()
        assert results[0]["service"] == "api"
        assert results[0]["avg_utilization_pct"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization() == []


class TestDetectBottleneckTrends:
    def test_worsening(self):
        eng = _engine()
        for util in [30.0, 30.0, 90.0, 90.0]:
            eng.record_bottleneck("svc", utilization_pct=util)
        result = eng.detect_bottleneck_trends()
        assert result["trend"] == "worsening"

    def test_improving(self):
        eng = _engine()
        for util in [90.0, 90.0, 30.0, 30.0]:
            eng.record_bottleneck("svc", utilization_pct=util)
        result = eng.detect_bottleneck_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_bottleneck("svc", utilization_pct=80.0)
        result = eng.detect_bottleneck_trends()
        assert result["status"] == "insufficient_data"


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(critical_utilization_pct=90.0)
        eng.record_bottleneck("svc-1", severity=BottleneckSeverity.CRITICAL, utilization_pct=95.0)
        eng.record_bottleneck("svc-2", severity=BottleneckSeverity.LOW, utilization_pct=50.0)
        eng.add_event("rec-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_events == 1
        assert report.critical_bottlenecks == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_bottleneck("svc-1")
        eng.add_event("rec-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._events) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_events"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_bottleneck("api", bottleneck_type=BottleneckType.CPU)
        eng.record_bottleneck("db", bottleneck_type=BottleneckType.MEMORY)
        eng.add_event("rec-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_events"] == 1
        assert stats["unique_services"] == 2
