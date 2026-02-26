"""Tests for shieldops.changes.rollback_analyzer — DeploymentRollbackAnalyzer."""

from __future__ import annotations

from shieldops.changes.rollback_analyzer import (
    DeploymentRollbackAnalyzer,
    RollbackAnalyzerReport,
    RollbackImpact,
    RollbackPattern,
    RollbackReason,
    RollbackRecord,
    RollbackSpeed,
)


def _engine(**kw) -> DeploymentRollbackAnalyzer:
    return DeploymentRollbackAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # RollbackReason (5)
    def test_reason_performance(self):
        assert RollbackReason.PERFORMANCE_DEGRADATION == "performance_degradation"

    def test_reason_error_spike(self):
        assert RollbackReason.ERROR_SPIKE == "error_spike"

    def test_reason_health_check(self):
        assert RollbackReason.HEALTH_CHECK_FAILURE == "health_check_failure"

    def test_reason_customer_impact(self):
        assert RollbackReason.CUSTOMER_IMPACT == "customer_impact"

    def test_reason_manual(self):
        assert RollbackReason.MANUAL_TRIGGER == "manual_trigger"

    # RollbackImpact (5)
    def test_impact_critical(self):
        assert RollbackImpact.CRITICAL == "critical"

    def test_impact_high(self):
        assert RollbackImpact.HIGH == "high"

    def test_impact_moderate(self):
        assert RollbackImpact.MODERATE == "moderate"

    def test_impact_low(self):
        assert RollbackImpact.LOW == "low"

    def test_impact_minimal(self):
        assert RollbackImpact.MINIMAL == "minimal"

    # RollbackSpeed (5)
    def test_speed_instant(self):
        assert RollbackSpeed.INSTANT == "instant"

    def test_speed_fast(self):
        assert RollbackSpeed.FAST == "fast"

    def test_speed_normal(self):
        assert RollbackSpeed.NORMAL == "normal"

    def test_speed_slow(self):
        assert RollbackSpeed.SLOW == "slow"

    def test_speed_manual(self):
        assert RollbackSpeed.MANUAL == "manual"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_rollback_record_defaults(self):
        r = RollbackRecord()
        assert r.id
        assert r.service_name == ""
        assert r.reason == RollbackReason.MANUAL_TRIGGER
        assert r.impact == RollbackImpact.LOW
        assert r.speed == RollbackSpeed.NORMAL
        assert r.rollback_rate_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_rollback_pattern_defaults(self):
        p = RollbackPattern()
        assert p.id
        assert p.pattern_name == ""
        assert p.reason == RollbackReason.MANUAL_TRIGGER
        assert p.impact == RollbackImpact.LOW
        assert p.frequency == 0
        assert p.description == ""
        assert p.created_at > 0

    def test_report_defaults(self):
        r = RollbackAnalyzerReport()
        assert r.total_rollbacks == 0
        assert r.total_patterns == 0
        assert r.avg_rollback_rate_pct == 0.0
        assert r.by_reason == {}
        assert r.by_impact == {}
        assert r.high_rollback_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_rollback
# -------------------------------------------------------------------


class TestRecordRollback:
    def test_basic(self):
        eng = _engine()
        r = eng.record_rollback(
            "svc-a",
            reason=RollbackReason.ERROR_SPIKE,
            impact=RollbackImpact.HIGH,
            rollback_rate_pct=5.0,
        )
        assert r.service_name == "svc-a"
        assert r.reason == RollbackReason.ERROR_SPIKE
        assert r.rollback_rate_pct == 5.0

    def test_with_speed(self):
        eng = _engine()
        r = eng.record_rollback("svc-b", speed=RollbackSpeed.INSTANT)
        assert r.speed == RollbackSpeed.INSTANT

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_rollback(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_rollback
# -------------------------------------------------------------------


class TestGetRollback:
    def test_found(self):
        eng = _engine()
        r = eng.record_rollback("svc-a")
        assert eng.get_rollback(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_rollback("nonexistent") is None


# -------------------------------------------------------------------
# list_rollbacks
# -------------------------------------------------------------------


class TestListRollbacks:
    def test_list_all(self):
        eng = _engine()
        eng.record_rollback("svc-a")
        eng.record_rollback("svc-b")
        assert len(eng.list_rollbacks()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_rollback("svc-a")
        eng.record_rollback("svc-b")
        results = eng.list_rollbacks(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_reason(self):
        eng = _engine()
        eng.record_rollback("svc-a", reason=RollbackReason.ERROR_SPIKE)
        eng.record_rollback("svc-b", reason=RollbackReason.MANUAL_TRIGGER)
        results = eng.list_rollbacks(reason=RollbackReason.ERROR_SPIKE)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_pattern
# -------------------------------------------------------------------


class TestAddPattern:
    def test_basic(self):
        eng = _engine()
        p = eng.add_pattern("recurring-oom", reason=RollbackReason.ERROR_SPIKE, frequency=5)
        assert p.pattern_name == "recurring-oom"
        assert p.frequency == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_pattern(f"pattern-{i}")
        assert len(eng._patterns) == 2


# -------------------------------------------------------------------
# analyze_rollback_frequency
# -------------------------------------------------------------------


class TestAnalyzeRollbackFrequency:
    def test_with_data(self):
        eng = _engine(max_rate_pct=10.0)
        eng.record_rollback("svc-a", rollback_rate_pct=5.0)
        eng.record_rollback("svc-a", rollback_rate_pct=8.0)
        result = eng.analyze_rollback_frequency("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total"] == 2
        assert result["avg_rate"] == 6.5
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_rollback_frequency("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_high_rollback_services
# -------------------------------------------------------------------


class TestIdentifyHighRollbackServices:
    def test_with_high_impact(self):
        eng = _engine()
        eng.record_rollback("svc-a", impact=RollbackImpact.CRITICAL)
        eng.record_rollback("svc-a", impact=RollbackImpact.HIGH)
        eng.record_rollback("svc-b", impact=RollbackImpact.LOW)
        results = eng.identify_high_rollback_services()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_rollback_services() == []


# -------------------------------------------------------------------
# rank_by_rollback_rate
# -------------------------------------------------------------------


class TestRankByRollbackRate:
    def test_with_data(self):
        eng = _engine()
        eng.record_rollback("svc-a", rollback_rate_pct=10.0)
        eng.record_rollback("svc-b", rollback_rate_pct=50.0)
        results = eng.rank_by_rollback_rate()
        assert results[0]["avg_rollback_rate_pct"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_rollback_rate() == []


# -------------------------------------------------------------------
# detect_rollback_trends
# -------------------------------------------------------------------


class TestDetectRollbackTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(4):
            eng.record_rollback("svc-trending")
        eng.record_rollback("svc-stable")
        results = eng.detect_rollback_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-trending"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_rollback_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(max_rate_pct=5.0)
        eng.record_rollback("svc-a", impact=RollbackImpact.CRITICAL, rollback_rate_pct=15.0)
        eng.record_rollback("svc-b", impact=RollbackImpact.LOW, rollback_rate_pct=2.0)
        eng.add_pattern("pat-1")
        report = eng.generate_report()
        assert isinstance(report, RollbackAnalyzerReport)
        assert report.total_rollbacks == 2
        assert report.total_patterns == 1
        assert report.high_rollback_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "acceptable limits" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_rollback("svc-a")
        eng.add_pattern("pat-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._patterns) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_rollbacks"] == 0
        assert stats["total_patterns"] == 0
        assert stats["reason_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_rollback("svc-a", reason=RollbackReason.ERROR_SPIKE)
        eng.record_rollback("svc-b", reason=RollbackReason.MANUAL_TRIGGER)
        eng.add_pattern("pat-1")
        stats = eng.get_stats()
        assert stats["total_rollbacks"] == 2
        assert stats["total_patterns"] == 1
        assert stats["unique_services"] == 2
