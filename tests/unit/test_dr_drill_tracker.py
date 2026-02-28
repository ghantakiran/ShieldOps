"""Tests for shieldops.operations.dr_drill_tracker — DRDrillTracker."""

from __future__ import annotations

from shieldops.operations.dr_drill_tracker import (
    DRDrillReport,
    DRDrillTracker,
    DrillFinding,
    DrillOutcome,
    DrillRecord,
    DrillScope,
    DrillType,
)


def _engine(**kw) -> DRDrillTracker:
    return DRDrillTracker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DrillType (5)
    def test_type_failover(self):
        assert DrillType.FAILOVER == "failover"

    def test_type_backup_restore(self):
        assert DrillType.BACKUP_RESTORE == "backup_restore"

    def test_type_network_partition(self):
        assert DrillType.NETWORK_PARTITION == "network_partition"

    def test_type_data_center_loss(self):
        assert DrillType.DATA_CENTER_LOSS == "data_center_loss"

    def test_type_cascading_failure(self):
        assert DrillType.CASCADING_FAILURE == "cascading_failure"

    # DrillOutcome (5)
    def test_outcome_success(self):
        assert DrillOutcome.SUCCESS == "success"

    def test_outcome_partial(self):
        assert DrillOutcome.PARTIAL == "partial"

    def test_outcome_failed(self):
        assert DrillOutcome.FAILED == "failed"

    def test_outcome_timeout(self):
        assert DrillOutcome.TIMEOUT == "timeout"

    def test_outcome_aborted(self):
        assert DrillOutcome.ABORTED == "aborted"

    # DrillScope (5)
    def test_scope_single_service(self):
        assert DrillScope.SINGLE_SERVICE == "single_service"

    def test_scope_multi_service(self):
        assert DrillScope.MULTI_SERVICE == "multi_service"

    def test_scope_regional(self):
        assert DrillScope.REGIONAL == "regional"

    def test_scope_cross_region(self):
        assert DrillScope.CROSS_REGION == "cross_region"

    def test_scope_full_platform(self):
        assert DrillScope.FULL_PLATFORM == "full_platform"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_drill_record_defaults(self):
        r = DrillRecord()
        assert r.id
        assert r.service_name == ""
        assert r.drill_type == DrillType.FAILOVER
        assert r.outcome == DrillOutcome.SUCCESS
        assert r.scope == DrillScope.SINGLE_SERVICE
        assert r.recovery_time_minutes == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_drill_finding_defaults(self):
        r = DrillFinding()
        assert r.id
        assert r.finding_name == ""
        assert r.drill_type == DrillType.FAILOVER
        assert r.outcome == DrillOutcome.SUCCESS
        assert r.severity_score == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_dr_drill_report_defaults(self):
        r = DRDrillReport()
        assert r.total_drills == 0
        assert r.total_findings == 0
        assert r.avg_recovery_time_min == 0.0
        assert r.by_type == {}
        assert r.by_outcome == {}
        assert r.failed_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_drill
# -------------------------------------------------------------------


class TestRecordDrill:
    def test_basic(self):
        eng = _engine()
        r = eng.record_drill("db-primary", drill_type=DrillType.FAILOVER)
        assert r.service_name == "db-primary"
        assert r.drill_type == DrillType.FAILOVER

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_drill(
            "cache-cluster",
            drill_type=DrillType.DATA_CENTER_LOSS,
            outcome=DrillOutcome.FAILED,
            scope=DrillScope.CROSS_REGION,
            recovery_time_minutes=45.5,
            details="DC failover timeout",
        )
        assert r.outcome == DrillOutcome.FAILED
        assert r.scope == DrillScope.CROSS_REGION
        assert r.recovery_time_minutes == 45.5
        assert r.details == "DC failover timeout"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_drill(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_drill
# -------------------------------------------------------------------


class TestGetDrill:
    def test_found(self):
        eng = _engine()
        r = eng.record_drill("db-primary")
        assert eng.get_drill(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_drill("nonexistent") is None


# -------------------------------------------------------------------
# list_drills
# -------------------------------------------------------------------


class TestListDrills:
    def test_list_all(self):
        eng = _engine()
        eng.record_drill("svc-a")
        eng.record_drill("svc-b")
        assert len(eng.list_drills()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_drill("svc-a")
        eng.record_drill("svc-b")
        results = eng.list_drills(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_drill_type(self):
        eng = _engine()
        eng.record_drill("svc-a", drill_type=DrillType.FAILOVER)
        eng.record_drill("svc-b", drill_type=DrillType.BACKUP_RESTORE)
        results = eng.list_drills(drill_type=DrillType.BACKUP_RESTORE)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_finding
# -------------------------------------------------------------------


class TestAddFinding:
    def test_basic(self):
        eng = _engine()
        f = eng.add_finding(
            "slow-failover",
            drill_type=DrillType.FAILOVER,
            outcome=DrillOutcome.PARTIAL,
            severity_score=8.0,
        )
        assert f.finding_name == "slow-failover"
        assert f.outcome == DrillOutcome.PARTIAL
        assert f.severity_score == 8.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_finding(f"finding-{i}")
        assert len(eng._findings) == 2


# -------------------------------------------------------------------
# analyze_drill_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeDrillEffectiveness:
    def test_with_data(self):
        eng = _engine(min_success_rate_pct=80.0)
        eng.record_drill("svc-a", outcome=DrillOutcome.SUCCESS)
        eng.record_drill("svc-a", outcome=DrillOutcome.SUCCESS)
        eng.record_drill("svc-a", outcome=DrillOutcome.FAILED)
        result = eng.analyze_drill_effectiveness("svc-a")
        assert result["success_rate"] == 66.67
        assert result["meets_threshold"] is False

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_drill_effectiveness("unknown-svc")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_success_rate_pct=80.0)
        eng.record_drill("svc-a", outcome=DrillOutcome.SUCCESS)
        eng.record_drill("svc-a", outcome=DrillOutcome.SUCCESS)
        result = eng.analyze_drill_effectiveness("svc-a")
        assert result["success_rate"] == 100.0
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_failed_drills
# -------------------------------------------------------------------


class TestIdentifyFailedDrills:
    def test_with_failed(self):
        eng = _engine()
        eng.record_drill("svc-a", outcome=DrillOutcome.FAILED)
        eng.record_drill("svc-a", outcome=DrillOutcome.TIMEOUT)
        eng.record_drill("svc-b", outcome=DrillOutcome.SUCCESS)
        results = eng.identify_failed_drills()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["failed_timeout_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_drills() == []

    def test_single_failed_not_returned(self):
        eng = _engine()
        eng.record_drill("svc-a", outcome=DrillOutcome.FAILED)
        assert eng.identify_failed_drills() == []


# -------------------------------------------------------------------
# rank_by_recovery_time
# -------------------------------------------------------------------


class TestRankByRecoveryTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_drill("svc-a", recovery_time_minutes=10.0)
        eng.record_drill("svc-b", recovery_time_minutes=60.0)
        results = eng.rank_by_recovery_time()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_recovery_time_min"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_recovery_time() == []


# -------------------------------------------------------------------
# detect_drill_trends
# -------------------------------------------------------------------


class TestDetectDrillTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_drill("svc-a")
        eng.record_drill("svc-b")
        results = eng.detect_drill_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_drill_trends() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_drill("svc-a")
        assert eng.detect_drill_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_drill("svc-a", outcome=DrillOutcome.FAILED, recovery_time_minutes=30.0)
        eng.record_drill("svc-b", outcome=DrillOutcome.SUCCESS, recovery_time_minutes=5.0)
        eng.add_finding("finding-1")
        report = eng.generate_report()
        assert report.total_drills == 2
        assert report.total_findings == 1
        assert report.failed_count == 1
        assert report.by_type != {}
        assert report.by_outcome != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_drills == 0
        assert report.avg_recovery_time_min == 0.0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_drill("svc-a")
        eng.add_finding("finding-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._findings) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_drills"] == 0
        assert stats["total_findings"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_success_rate_pct=80.0)
        eng.record_drill("svc-a", drill_type=DrillType.FAILOVER)
        eng.record_drill("svc-b", drill_type=DrillType.BACKUP_RESTORE)
        eng.add_finding("finding-1")
        stats = eng.get_stats()
        assert stats["total_drills"] == 2
        assert stats["total_findings"] == 1
        assert stats["unique_services"] == 2
        assert stats["min_success_rate_pct"] == 80.0
