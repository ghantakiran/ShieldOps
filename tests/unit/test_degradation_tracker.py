"""Tests for shieldops.sla.degradation_tracker — ServiceDegradationTracker."""

from __future__ import annotations

from shieldops.sla.degradation_tracker import (
    DegradationEvent,
    DegradationRecord,
    DegradationSeverity,
    DegradationType,
    RecoveryMethod,
    ServiceDegradationReport,
    ServiceDegradationTracker,
)


def _engine(**kw) -> ServiceDegradationTracker:
    return ServiceDegradationTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_latency_spike(self):
        assert DegradationType.LATENCY_SPIKE == "latency_spike"

    def test_type_error_rate_increase(self):
        assert DegradationType.ERROR_RATE_INCREASE == "error_rate_increase"

    def test_type_throughput_drop(self):
        assert DegradationType.THROUGHPUT_DROP == "throughput_drop"

    def test_type_partial_outage(self):
        assert DegradationType.PARTIAL_OUTAGE == "partial_outage"

    def test_type_capacity_limit(self):
        assert DegradationType.CAPACITY_LIMIT == "capacity_limit"

    def test_severity_critical(self):
        assert DegradationSeverity.CRITICAL == "critical"

    def test_severity_major(self):
        assert DegradationSeverity.MAJOR == "major"

    def test_severity_moderate(self):
        assert DegradationSeverity.MODERATE == "moderate"

    def test_severity_minor(self):
        assert DegradationSeverity.MINOR == "minor"

    def test_severity_cosmetic(self):
        assert DegradationSeverity.COSMETIC == "cosmetic"

    def test_recovery_auto_heal(self):
        assert RecoveryMethod.AUTO_HEAL == "auto_heal"

    def test_recovery_manual_fix(self):
        assert RecoveryMethod.MANUAL_FIX == "manual_fix"

    def test_recovery_rollback(self):
        assert RecoveryMethod.ROLLBACK == "rollback"

    def test_recovery_failover(self):
        assert RecoveryMethod.FAILOVER == "failover"

    def test_recovery_scaling(self):
        assert RecoveryMethod.SCALING == "scaling"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_degradation_record_defaults(self):
        r = DegradationRecord()
        assert r.id
        assert r.degradation_id == ""
        assert r.degradation_type == DegradationType.LATENCY_SPIKE
        assert r.degradation_severity == DegradationSeverity.MINOR
        assert r.recovery_method == RecoveryMethod.AUTO_HEAL
        assert r.duration_minutes == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_degradation_event_defaults(self):
        e = DegradationEvent()
        assert e.id
        assert e.degradation_id == ""
        assert e.degradation_type == DegradationType.LATENCY_SPIKE
        assert e.value == 0.0
        assert e.threshold == 0.0
        assert e.breached is False
        assert e.description == ""
        assert e.created_at > 0

    def test_service_degradation_report_defaults(self):
        r = ServiceDegradationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_events == 0
        assert r.critical_degradations == 0
        assert r.avg_duration_minutes == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.by_recovery == {}
        assert r.top_degraded == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_degradation
# ---------------------------------------------------------------------------


class TestRecordDegradation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_degradation(
            degradation_id="DEG-001",
            degradation_type=DegradationType.ERROR_RATE_INCREASE,
            degradation_severity=DegradationSeverity.MAJOR,
            recovery_method=RecoveryMethod.ROLLBACK,
            duration_minutes=15.0,
            service="api-gateway",
            team="sre",
        )
        assert r.degradation_id == "DEG-001"
        assert r.degradation_type == DegradationType.ERROR_RATE_INCREASE
        assert r.degradation_severity == DegradationSeverity.MAJOR
        assert r.recovery_method == RecoveryMethod.ROLLBACK
        assert r.duration_minutes == 15.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_degradation(degradation_id=f"DEG-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_degradation
# ---------------------------------------------------------------------------


class TestGetDegradation:
    def test_found(self):
        eng = _engine()
        r = eng.record_degradation(
            degradation_id="DEG-001",
            degradation_severity=DegradationSeverity.CRITICAL,
        )
        result = eng.get_degradation(r.id)
        assert result is not None
        assert result.degradation_severity == DegradationSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_degradation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_degradations
# ---------------------------------------------------------------------------


class TestListDegradations:
    def test_list_all(self):
        eng = _engine()
        eng.record_degradation(degradation_id="DEG-001")
        eng.record_degradation(degradation_id="DEG-002")
        assert len(eng.list_degradations()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_degradation(
            degradation_id="DEG-001",
            degradation_type=DegradationType.PARTIAL_OUTAGE,
        )
        eng.record_degradation(
            degradation_id="DEG-002",
            degradation_type=DegradationType.LATENCY_SPIKE,
        )
        results = eng.list_degradations(dtype=DegradationType.PARTIAL_OUTAGE)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_degradation(
            degradation_id="DEG-001",
            degradation_severity=DegradationSeverity.CRITICAL,
        )
        eng.record_degradation(
            degradation_id="DEG-002",
            degradation_severity=DegradationSeverity.MINOR,
        )
        results = eng.list_degradations(severity=DegradationSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_degradation(degradation_id="DEG-001", service="api")
        eng.record_degradation(degradation_id="DEG-002", service="web")
        results = eng.list_degradations(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_degradation(degradation_id="DEG-001", team="sre")
        eng.record_degradation(degradation_id="DEG-002", team="platform")
        results = eng.list_degradations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_degradation(degradation_id=f"DEG-{i}")
        assert len(eng.list_degradations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_event
# ---------------------------------------------------------------------------


class TestAddEvent:
    def test_basic(self):
        eng = _engine()
        e = eng.add_event(
            degradation_id="DEG-001",
            degradation_type=DegradationType.THROUGHPUT_DROP,
            value=75.0,
            threshold=80.0,
            breached=False,
            description="Throughput within limits",
        )
        assert e.degradation_id == "DEG-001"
        assert e.degradation_type == DegradationType.THROUGHPUT_DROP
        assert e.value == 75.0
        assert e.threshold == 80.0
        assert e.breached is False
        assert e.description == "Throughput within limits"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_event(degradation_id=f"DEG-{i}")
        assert len(eng._events) == 2


# ---------------------------------------------------------------------------
# analyze_degradation_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeDegradationPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_degradation(
            degradation_id="DEG-001",
            degradation_type=DegradationType.LATENCY_SPIKE,
            duration_minutes=10.0,
        )
        eng.record_degradation(
            degradation_id="DEG-002",
            degradation_type=DegradationType.LATENCY_SPIKE,
            duration_minutes=20.0,
        )
        result = eng.analyze_degradation_patterns()
        assert "latency_spike" in result
        assert result["latency_spike"]["count"] == 2
        assert result["latency_spike"]["avg_duration_minutes"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_degradation_patterns() == {}


# ---------------------------------------------------------------------------
# identify_frequent_degradations
# ---------------------------------------------------------------------------


class TestIdentifyFrequentDegradations:
    def test_detects_critical(self):
        eng = _engine()
        eng.record_degradation(
            degradation_id="DEG-001",
            degradation_severity=DegradationSeverity.CRITICAL,
        )
        eng.record_degradation(
            degradation_id="DEG-002",
            degradation_severity=DegradationSeverity.MINOR,
        )
        results = eng.identify_frequent_degradations()
        assert len(results) == 1
        assert results[0]["degradation_id"] == "DEG-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_frequent_degradations() == []


# ---------------------------------------------------------------------------
# rank_by_duration
# ---------------------------------------------------------------------------


class TestRankByDuration:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_degradation(degradation_id="DEG-001", service="api", duration_minutes=30.0)
        eng.record_degradation(degradation_id="DEG-002", service="api", duration_minutes=20.0)
        eng.record_degradation(degradation_id="DEG-003", service="web", duration_minutes=5.0)
        results = eng.rank_by_duration()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_duration_minutes"] == 25.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_duration() == []


# ---------------------------------------------------------------------------
# detect_degradation_trends
# ---------------------------------------------------------------------------


class TestDetectDegradationTrends:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_event(degradation_id="DEG-001", value=val)
        result = eng.detect_degradation_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_event(degradation_id="DEG-001", value=val)
        result = eng.detect_degradation_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_degradation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_degradation(
            degradation_id="DEG-001",
            degradation_type=DegradationType.LATENCY_SPIKE,
            degradation_severity=DegradationSeverity.CRITICAL,
            duration_minutes=15.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, ServiceDegradationReport)
        assert report.total_records == 1
        assert report.critical_degradations == 1
        assert report.avg_duration_minutes == 15.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_degradation(degradation_id="DEG-001")
        eng.add_event(degradation_id="DEG-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
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
        eng.record_degradation(
            degradation_id="DEG-001",
            degradation_type=DegradationType.PARTIAL_OUTAGE,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_degradations"] == 1
        assert "partial_outage" in stats["type_distribution"]
