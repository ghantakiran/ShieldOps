"""Tests for shieldops.operations.recovery_coordinator — RecoveryCoordinator."""

from __future__ import annotations

from shieldops.operations.recovery_coordinator import (
    RecoveryCoordinator,
    RecoveryCoordinatorReport,
    RecoveryMilestone,
    RecoveryPhase,
    RecoveryPriority,
    RecoveryRecord,
    RecoveryStatus,
)


def _engine(**kw) -> RecoveryCoordinator:
    return RecoveryCoordinator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # RecoveryPhase (5)
    def test_phase_assessment(self):
        assert RecoveryPhase.ASSESSMENT == "assessment"

    def test_phase_containment(self):
        assert RecoveryPhase.CONTAINMENT == "containment"

    def test_phase_restoration(self):
        assert RecoveryPhase.RESTORATION == "restoration"

    def test_phase_verification(self):
        assert RecoveryPhase.VERIFICATION == "verification"

    def test_phase_post_recovery(self):
        assert RecoveryPhase.POST_RECOVERY == "post_recovery"

    # RecoveryStatus (5)
    def test_status_pending(self):
        assert RecoveryStatus.PENDING == "pending"

    def test_status_in_progress(self):
        assert RecoveryStatus.IN_PROGRESS == "in_progress"

    def test_status_completed(self):
        assert RecoveryStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert RecoveryStatus.FAILED == "failed"

    def test_status_escalated(self):
        assert RecoveryStatus.ESCALATED == "escalated"

    # RecoveryPriority (5)
    def test_priority_critical(self):
        assert RecoveryPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert RecoveryPriority.HIGH == "high"

    def test_priority_medium(self):
        assert RecoveryPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert RecoveryPriority.LOW == "low"

    def test_priority_deferred(self):
        assert RecoveryPriority.DEFERRED == "deferred"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_recovery_record_defaults(self):
        r = RecoveryRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.recovery_phase == RecoveryPhase.ASSESSMENT
        assert r.recovery_status == RecoveryStatus.PENDING
        assert r.recovery_priority == RecoveryPriority.HIGH
        assert r.affected_services == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_recovery_milestone_defaults(self):
        r = RecoveryMilestone()
        assert r.id
        assert r.milestone_name == ""
        assert r.recovery_phase == RecoveryPhase.RESTORATION
        assert r.recovery_status == RecoveryStatus.IN_PROGRESS
        assert r.duration_seconds == 0.0
        assert r.created_at > 0

    def test_recovery_coordinator_report_defaults(self):
        r = RecoveryCoordinatorReport()
        assert r.total_recoveries == 0
        assert r.total_milestones == 0
        assert r.completion_rate_pct == 0.0
        assert r.by_phase == {}
        assert r.by_status == {}
        assert r.escalation_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_recovery
# -------------------------------------------------------------------


class TestRecordRecovery:
    def test_basic(self):
        eng = _engine()
        r = eng.record_recovery("INC-001", recovery_phase=RecoveryPhase.ASSESSMENT)
        assert r.incident_id == "INC-001"
        assert r.recovery_phase == RecoveryPhase.ASSESSMENT

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_recovery(
            "INC-002",
            recovery_phase=RecoveryPhase.RESTORATION,
            recovery_status=RecoveryStatus.FAILED,
            recovery_priority=RecoveryPriority.CRITICAL,
            affected_services=5,
            details="Multi-service outage",
        )
        assert r.recovery_status == RecoveryStatus.FAILED
        assert r.recovery_priority == RecoveryPriority.CRITICAL
        assert r.affected_services == 5
        assert r.details == "Multi-service outage"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_recovery(f"INC-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_recovery
# -------------------------------------------------------------------


class TestGetRecovery:
    def test_found(self):
        eng = _engine()
        r = eng.record_recovery("INC-001")
        assert eng.get_recovery(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_recovery("nonexistent") is None


# -------------------------------------------------------------------
# list_recoveries
# -------------------------------------------------------------------


class TestListRecoveries:
    def test_list_all(self):
        eng = _engine()
        eng.record_recovery("INC-001")
        eng.record_recovery("INC-002")
        assert len(eng.list_recoveries()) == 2

    def test_filter_by_incident_id(self):
        eng = _engine()
        eng.record_recovery("INC-001")
        eng.record_recovery("INC-002")
        results = eng.list_recoveries(incident_id="INC-001")
        assert len(results) == 1
        assert results[0].incident_id == "INC-001"

    def test_filter_by_recovery_status(self):
        eng = _engine()
        eng.record_recovery("INC-001", recovery_status=RecoveryStatus.PENDING)
        eng.record_recovery("INC-002", recovery_status=RecoveryStatus.COMPLETED)
        results = eng.list_recoveries(recovery_status=RecoveryStatus.COMPLETED)
        assert len(results) == 1
        assert results[0].incident_id == "INC-002"


# -------------------------------------------------------------------
# add_milestone
# -------------------------------------------------------------------


class TestAddMilestone:
    def test_basic(self):
        eng = _engine()
        m = eng.add_milestone(
            "services-restored",
            recovery_phase=RecoveryPhase.RESTORATION,
            recovery_status=RecoveryStatus.COMPLETED,
            duration_seconds=120.0,
        )
        assert m.milestone_name == "services-restored"
        assert m.recovery_status == RecoveryStatus.COMPLETED
        assert m.duration_seconds == 120.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_milestone(f"milestone-{i}")
        assert len(eng._milestones) == 2


# -------------------------------------------------------------------
# analyze_recovery_speed
# -------------------------------------------------------------------


class TestAnalyzeRecoverySpeed:
    def test_with_data(self):
        eng = _engine()
        eng.record_recovery("INC-001", recovery_status=RecoveryStatus.COMPLETED)
        eng.record_recovery("INC-001", recovery_status=RecoveryStatus.COMPLETED)
        eng.record_recovery("INC-001", recovery_status=RecoveryStatus.FAILED)
        result = eng.analyze_recovery_speed("INC-001")
        assert result["completion_rate"] == 66.67
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_recovery_speed("INC-999")
        assert result["status"] == "no_data"

    def test_full_completion(self):
        eng = _engine()
        eng.record_recovery("INC-001", recovery_status=RecoveryStatus.COMPLETED)
        eng.record_recovery("INC-001", recovery_status=RecoveryStatus.COMPLETED)
        result = eng.analyze_recovery_speed("INC-001")
        assert result["completion_rate"] == 100.0


# -------------------------------------------------------------------
# identify_stalled_recoveries
# -------------------------------------------------------------------


class TestIdentifyStalledRecoveries:
    def test_with_stalled(self):
        eng = _engine()
        eng.record_recovery("INC-001", recovery_status=RecoveryStatus.FAILED)
        eng.record_recovery("INC-001", recovery_status=RecoveryStatus.ESCALATED)
        eng.record_recovery("INC-002", recovery_status=RecoveryStatus.COMPLETED)
        results = eng.identify_stalled_recoveries()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"
        assert results[0]["stalled_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_stalled_recoveries() == []

    def test_single_failed_not_returned(self):
        eng = _engine()
        eng.record_recovery("INC-001", recovery_status=RecoveryStatus.FAILED)
        assert eng.identify_stalled_recoveries() == []


# -------------------------------------------------------------------
# rank_by_recovery_time
# -------------------------------------------------------------------


class TestRankByRecoveryTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_recovery("INC-001", affected_services=2)
        eng.record_recovery("INC-002", affected_services=10)
        results = eng.rank_by_recovery_time()
        assert results[0]["incident_id"] == "INC-002"
        assert results[0]["avg_affected_services"] == 10.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_recovery_time() == []


# -------------------------------------------------------------------
# detect_recovery_regressions
# -------------------------------------------------------------------


class TestDetectRecoveryRegressions:
    def test_with_regressions(self):
        eng = _engine()
        for _ in range(5):
            eng.record_recovery("INC-001")
        eng.record_recovery("INC-002")
        results = eng.detect_recovery_regressions()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_recovery_regressions() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_recovery("INC-001")
        assert eng.detect_recovery_regressions() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_recovery("INC-001", recovery_status=RecoveryStatus.FAILED)
        eng.record_recovery("INC-002", recovery_status=RecoveryStatus.COMPLETED)
        eng.add_milestone("milestone-1")
        report = eng.generate_report()
        assert report.total_recoveries == 2
        assert report.total_milestones == 1
        assert report.by_phase != {}
        assert report.by_status != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_recoveries == 0
        assert report.completion_rate_pct == 0.0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_recovery("INC-001")
        eng.add_milestone("milestone-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._milestones) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_recoveries"] == 0
        assert stats["total_milestones"] == 0
        assert stats["phase_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_recovery_hours=24.0)
        eng.record_recovery("INC-001", recovery_phase=RecoveryPhase.ASSESSMENT)
        eng.record_recovery("INC-002", recovery_phase=RecoveryPhase.RESTORATION)
        eng.add_milestone("milestone-1")
        stats = eng.get_stats()
        assert stats["total_recoveries"] == 2
        assert stats["total_milestones"] == 1
        assert stats["unique_incidents"] == 2
        assert stats["max_recovery_hours"] == 24.0
