"""Tests for shieldops.analytics.resource_contention — ResourceContentionDetector."""

from __future__ import annotations

from shieldops.analytics.resource_contention import (
    ContentionEvent,
    ContentionRecord,
    ContentionSeverity,
    ContentionSource,
    ContentionType,
    ResourceContentionDetector,
    ResourceContentionReport,
)


def _engine(**kw) -> ResourceContentionDetector:
    return ResourceContentionDetector(**kw)


class TestEnums:
    def test_type_cpu_throttling(self):
        assert ContentionType.CPU_THROTTLING == "cpu_throttling"

    def test_type_memory_pressure(self):
        assert ContentionType.MEMORY_PRESSURE == "memory_pressure"

    def test_type_io_saturation(self):
        assert ContentionType.IO_SATURATION == "io_saturation"

    def test_type_network_congestion(self):
        assert ContentionType.NETWORK_CONGESTION == "network_congestion"

    def test_type_lock_contention(self):
        assert ContentionType.LOCK_CONTENTION == "lock_contention"

    def test_severity_critical(self):
        assert ContentionSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert ContentionSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert ContentionSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert ContentionSeverity.LOW == "low"

    def test_severity_none(self):
        assert ContentionSeverity.NONE_SEV == "none"

    def test_source_noisy_neighbor(self):
        assert ContentionSource.NOISY_NEIGHBOR == "noisy_neighbor"

    def test_source_resource_limit(self):
        assert ContentionSource.RESOURCE_LIMIT == "resource_limit"

    def test_source_burst_traffic(self):
        assert ContentionSource.BURST_TRAFFIC == "burst_traffic"

    def test_source_memory_leak(self):
        assert ContentionSource.MEMORY_LEAK == "memory_leak"

    def test_source_misconfiguration(self):
        assert ContentionSource.MISCONFIGURATION == "misconfiguration"


class TestModels:
    def test_contention_record_defaults(self):
        r = ContentionRecord()
        assert r.id
        assert r.service_name == ""
        assert r.contention_type == ContentionType.CPU_THROTTLING
        assert r.severity == ContentionSeverity.LOW
        assert r.source == ContentionSource.RESOURCE_LIMIT
        assert r.impact_duration_hours == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_contention_event_defaults(self):
        r = ContentionEvent()
        assert r.id
        assert r.event_name == ""
        assert r.contention_type == ContentionType.CPU_THROTTLING
        assert r.severity == ContentionSeverity.LOW
        assert r.duration_hours == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = ResourceContentionReport()
        assert r.total_contentions == 0
        assert r.total_events == 0
        assert r.avg_duration_hours == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordContention:
    def test_basic(self):
        eng = _engine()
        r = eng.record_contention("svc-a", impact_duration_hours=2.5)
        assert r.service_name == "svc-a"
        assert r.impact_duration_hours == 2.5

    def test_with_severity(self):
        eng = _engine()
        r = eng.record_contention("svc-b", severity=ContentionSeverity.CRITICAL)
        assert r.severity == ContentionSeverity.CRITICAL

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_contention(f"svc-{i}")
        assert len(eng._records) == 3


class TestGetContention:
    def test_found(self):
        eng = _engine()
        r = eng.record_contention("svc-a")
        assert eng.get_contention(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_contention("nonexistent") is None


class TestListContentions:
    def test_list_all(self):
        eng = _engine()
        eng.record_contention("svc-a")
        eng.record_contention("svc-b")
        assert len(eng.list_contentions()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_contention("svc-a")
        eng.record_contention("svc-b")
        results = eng.list_contentions(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_contention("svc-a", contention_type=ContentionType.CPU_THROTTLING)
        eng.record_contention("svc-b", contention_type=ContentionType.MEMORY_PRESSURE)
        results = eng.list_contentions(contention_type=ContentionType.CPU_THROTTLING)
        assert len(results) == 1


class TestAddEvent:
    def test_basic(self):
        eng = _engine()
        e = eng.add_event("cpu-spike", duration_hours=1.5)
        assert e.event_name == "cpu-spike"
        assert e.duration_hours == 1.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_event(f"event-{i}")
        assert len(eng._events) == 2


class TestAnalyzeContentionPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_contention("svc-a", impact_duration_hours=2.0)
        eng.record_contention("svc-a", impact_duration_hours=4.0)
        result = eng.analyze_contention_patterns("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total"] == 2
        assert result["avg_duration"] == 3.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_contention_patterns("ghost")
        assert result["status"] == "no_data"


class TestIdentifyCriticalContentions:
    def test_with_critical(self):
        eng = _engine()
        eng.record_contention("svc-a", severity=ContentionSeverity.CRITICAL)
        eng.record_contention("svc-a", severity=ContentionSeverity.HIGH)
        eng.record_contention("svc-b", severity=ContentionSeverity.LOW)
        results = eng.identify_critical_contentions()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_contentions() == []


class TestRankByImpactDuration:
    def test_with_data(self):
        eng = _engine()
        eng.record_contention("svc-a", impact_duration_hours=1.0)
        eng.record_contention("svc-b", impact_duration_hours=8.0)
        results = eng.rank_by_impact_duration()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_duration_hours"] == 8.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_duration() == []


class TestDetectRecurringContentions:
    def test_with_recurring(self):
        eng = _engine()
        for i in range(5):
            eng.record_contention("svc-a", impact_duration_hours=float(1 + i))
        results = eng.detect_recurring_contentions()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["pattern"] == "worsening"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_recurring_contentions() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_contention(
            "svc-a", impact_duration_hours=5.0, severity=ContentionSeverity.CRITICAL
        )
        eng.record_contention("svc-b", impact_duration_hours=1.0, severity=ContentionSeverity.LOW)
        eng.add_event("e1")
        report = eng.generate_report()
        assert report.total_contentions == 2
        assert report.total_events == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_contentions == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_contention("svc-a")
        eng.add_event("e1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._events) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_contentions"] == 0
        assert stats["total_events"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_contention("svc-a", contention_type=ContentionType.CPU_THROTTLING)
        eng.record_contention("svc-b", contention_type=ContentionType.MEMORY_PRESSURE)
        eng.add_event("e1")
        stats = eng.get_stats()
        assert stats["total_contentions"] == 2
        assert stats["total_events"] == 1
        assert stats["unique_services"] == 2
