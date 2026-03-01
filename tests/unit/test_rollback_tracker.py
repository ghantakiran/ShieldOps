"""Tests for shieldops.changes.rollback_tracker — DeploymentRollbackTracker."""

from __future__ import annotations

from shieldops.changes.rollback_tracker import (
    DeploymentRollbackTracker,
    RollbackImpact,
    RollbackPattern,
    RollbackReason,
    RollbackRecord,
    RollbackStatus,
    RollbackTrackerReport,
)


def _engine(**kw) -> DeploymentRollbackTracker:
    return DeploymentRollbackTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_reason_bug(self):
        assert RollbackReason.BUG == "bug"

    def test_reason_performance(self):
        assert RollbackReason.PERFORMANCE == "performance"

    def test_reason_security(self):
        assert RollbackReason.SECURITY == "security"

    def test_reason_compatibility(self):
        assert RollbackReason.COMPATIBILITY == "compatibility"

    def test_reason_configuration(self):
        assert RollbackReason.CONFIGURATION == "configuration"

    def test_impact_none(self):
        assert RollbackImpact.NONE == "none"

    def test_impact_minor(self):
        assert RollbackImpact.MINOR == "minor"

    def test_impact_moderate(self):
        assert RollbackImpact.MODERATE == "moderate"

    def test_impact_major(self):
        assert RollbackImpact.MAJOR == "major"

    def test_impact_critical(self):
        assert RollbackImpact.CRITICAL == "critical"

    def test_status_initiated(self):
        assert RollbackStatus.INITIATED == "initiated"

    def test_status_in_progress(self):
        assert RollbackStatus.IN_PROGRESS == "in_progress"

    def test_status_completed(self):
        assert RollbackStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert RollbackStatus.FAILED == "failed"

    def test_status_cancelled(self):
        assert RollbackStatus.CANCELLED == "cancelled"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_rollback_record_defaults(self):
        r = RollbackRecord()
        assert r.id
        assert r.deployment_id == ""
        assert r.rollback_reason == RollbackReason.BUG
        assert r.rollback_impact == RollbackImpact.NONE
        assert r.rollback_status == RollbackStatus.INITIATED
        assert r.duration_minutes == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_rollback_pattern_defaults(self):
        p = RollbackPattern()
        assert p.id
        assert p.service_pattern == ""
        assert p.rollback_reason == RollbackReason.BUG
        assert p.frequency_threshold == 0
        assert p.auto_block is False
        assert p.description == ""
        assert p.created_at > 0

    def test_rollback_tracker_report_defaults(self):
        r = RollbackTrackerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_patterns == 0
        assert r.failed_rollbacks == 0
        assert r.avg_duration_minutes == 0.0
        assert r.by_reason == {}
        assert r.by_impact == {}
        assert r.by_status == {}
        assert r.frequent_rollers == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_rollback
# ---------------------------------------------------------------------------


class TestRecordRollback:
    def test_basic(self):
        eng = _engine()
        r = eng.record_rollback(
            deployment_id="DEP-001",
            rollback_reason=RollbackReason.PERFORMANCE,
            rollback_impact=RollbackImpact.MAJOR,
            rollback_status=RollbackStatus.COMPLETED,
            duration_minutes=15.5,
            team="sre",
        )
        assert r.deployment_id == "DEP-001"
        assert r.rollback_reason == RollbackReason.PERFORMANCE
        assert r.rollback_impact == RollbackImpact.MAJOR
        assert r.rollback_status == RollbackStatus.COMPLETED
        assert r.duration_minutes == 15.5
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_rollback(deployment_id=f"DEP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_rollback
# ---------------------------------------------------------------------------


class TestGetRollback:
    def test_found(self):
        eng = _engine()
        r = eng.record_rollback(
            deployment_id="DEP-001",
            rollback_impact=RollbackImpact.CRITICAL,
        )
        result = eng.get_rollback(r.id)
        assert result is not None
        assert result.rollback_impact == RollbackImpact.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_rollback("nonexistent") is None


# ---------------------------------------------------------------------------
# list_rollbacks
# ---------------------------------------------------------------------------


class TestListRollbacks:
    def test_list_all(self):
        eng = _engine()
        eng.record_rollback(deployment_id="DEP-001")
        eng.record_rollback(deployment_id="DEP-002")
        assert len(eng.list_rollbacks()) == 2

    def test_filter_by_reason(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_reason=RollbackReason.SECURITY,
        )
        eng.record_rollback(
            deployment_id="DEP-002",
            rollback_reason=RollbackReason.BUG,
        )
        results = eng.list_rollbacks(reason=RollbackReason.SECURITY)
        assert len(results) == 1

    def test_filter_by_impact(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_impact=RollbackImpact.CRITICAL,
        )
        eng.record_rollback(
            deployment_id="DEP-002",
            rollback_impact=RollbackImpact.MINOR,
        )
        results = eng.list_rollbacks(impact=RollbackImpact.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_rollback(deployment_id="DEP-001", team="sre")
        eng.record_rollback(deployment_id="DEP-002", team="platform")
        results = eng.list_rollbacks(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_rollback(deployment_id=f"DEP-{i}")
        assert len(eng.list_rollbacks(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_pattern
# ---------------------------------------------------------------------------


class TestAddPattern:
    def test_basic(self):
        eng = _engine()
        p = eng.add_pattern(
            service_pattern="payment-*",
            rollback_reason=RollbackReason.COMPATIBILITY,
            frequency_threshold=3,
            auto_block=True,
            description="Block frequent rollers",
        )
        assert p.service_pattern == "payment-*"
        assert p.rollback_reason == RollbackReason.COMPATIBILITY
        assert p.frequency_threshold == 3
        assert p.auto_block is True
        assert p.description == "Block frequent rollers"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_pattern(service_pattern=f"svc-{i}")
        assert len(eng._patterns) == 2


# ---------------------------------------------------------------------------
# analyze_rollback_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeRollbackPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_reason=RollbackReason.BUG,
            duration_minutes=10.0,
        )
        eng.record_rollback(
            deployment_id="DEP-002",
            rollback_reason=RollbackReason.BUG,
            duration_minutes=20.0,
        )
        result = eng.analyze_rollback_patterns()
        assert "bug" in result
        assert result["bug"]["count"] == 2
        assert result["bug"]["avg_duration"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_rollback_patterns() == {}


# ---------------------------------------------------------------------------
# identify_frequent_rollers
# ---------------------------------------------------------------------------


class TestIdentifyFrequentRollers:
    def test_detects_failed(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_status=RollbackStatus.FAILED,
        )
        eng.record_rollback(
            deployment_id="DEP-002",
            rollback_status=RollbackStatus.COMPLETED,
        )
        results = eng.identify_frequent_rollers()
        assert len(results) == 1
        assert results[0]["deployment_id"] == "DEP-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_frequent_rollers() == []


# ---------------------------------------------------------------------------
# rank_by_duration
# ---------------------------------------------------------------------------


class TestRankByDuration:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_rollback(deployment_id="DEP-001", team="sre", duration_minutes=30.0)
        eng.record_rollback(deployment_id="DEP-002", team="sre", duration_minutes=20.0)
        eng.record_rollback(deployment_id="DEP-003", team="platform", duration_minutes=5.0)
        results = eng.rank_by_duration()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_duration"] == 25.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_duration() == []


# ---------------------------------------------------------------------------
# detect_rollback_trends
# ---------------------------------------------------------------------------


class TestDetectRollbackTrends:
    def test_stable(self):
        eng = _engine()
        for count in [10, 10, 10, 10]:
            eng.add_pattern(service_pattern="s", frequency_threshold=count)
        result = eng.detect_rollback_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for count in [5, 5, 20, 20]:
            eng.add_pattern(service_pattern="s", frequency_threshold=count)
        result = eng.detect_rollback_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_rollback_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_reason=RollbackReason.BUG,
            rollback_status=RollbackStatus.FAILED,
            duration_minutes=10.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, RollbackTrackerReport)
        assert report.total_records == 1
        assert report.failed_rollbacks == 1
        assert report.avg_duration_minutes == 10.0
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
        eng.record_rollback(deployment_id="DEP-001")
        eng.add_pattern(service_pattern="s1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._patterns) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_patterns"] == 0
        assert stats["reason_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_reason=RollbackReason.SECURITY,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_deployments"] == 1
        assert "security" in stats["reason_distribution"]
