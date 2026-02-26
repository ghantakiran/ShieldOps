"""Tests for shieldops.incidents.followup_tracker — PostIncidentFollowupTracker."""

from __future__ import annotations

from shieldops.incidents.followup_tracker import (
    FollowupAssignment,
    FollowupPriority,
    FollowupRecord,
    FollowupStatus,
    FollowupTrackerReport,
    FollowupType,
    PostIncidentFollowupTracker,
)


def _engine(**kw) -> PostIncidentFollowupTracker:
    return PostIncidentFollowupTracker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # FollowupType (5)
    def test_type_action_item(self):
        assert FollowupType.ACTION_ITEM == "action_item"

    def test_type_process_change(self):
        assert FollowupType.PROCESS_CHANGE == "process_change"

    def test_type_tooling_improvement(self):
        assert FollowupType.TOOLING_IMPROVEMENT == "tooling_improvement"

    def test_type_training(self):
        assert FollowupType.TRAINING == "training"

    def test_type_documentation(self):
        assert FollowupType.DOCUMENTATION == "documentation"

    # FollowupStatus (5)
    def test_status_open(self):
        assert FollowupStatus.OPEN == "open"

    def test_status_in_progress(self):
        assert FollowupStatus.IN_PROGRESS == "in_progress"

    def test_status_completed(self):
        assert FollowupStatus.COMPLETED == "completed"

    def test_status_overdue(self):
        assert FollowupStatus.OVERDUE == "overdue"

    def test_status_cancelled(self):
        assert FollowupStatus.CANCELLED == "cancelled"

    # FollowupPriority (5)
    def test_priority_critical(self):
        assert FollowupPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert FollowupPriority.HIGH == "high"

    def test_priority_medium(self):
        assert FollowupPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert FollowupPriority.LOW == "low"

    def test_priority_optional(self):
        assert FollowupPriority.OPTIONAL == "optional"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_followup_record_defaults(self):
        r = FollowupRecord()
        assert r.id
        assert r.service_name == ""
        assert r.followup_type == FollowupType.ACTION_ITEM
        assert r.status == FollowupStatus.OPEN
        assert r.priority == FollowupPriority.MEDIUM
        assert r.age_days == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_followup_assignment_defaults(self):
        r = FollowupAssignment()
        assert r.id
        assert r.assignee_name == ""
        assert r.followup_type == FollowupType.ACTION_ITEM
        assert r.status == FollowupStatus.OPEN
        assert r.due_days == 30.0
        assert r.description == ""
        assert r.created_at > 0

    def test_followup_report_defaults(self):
        r = FollowupTrackerReport()
        assert r.total_followups == 0
        assert r.total_assignments == 0
        assert r.completion_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.overdue_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_followup
# -------------------------------------------------------------------


class TestRecordFollowup:
    def test_basic(self):
        eng = _engine()
        r = eng.record_followup(
            "svc-a",
            followup_type=FollowupType.ACTION_ITEM,
            status=FollowupStatus.OPEN,
        )
        assert r.service_name == "svc-a"
        assert r.followup_type == FollowupType.ACTION_ITEM

    def test_with_priority(self):
        eng = _engine()
        r = eng.record_followup("svc-b", priority=FollowupPriority.CRITICAL)
        assert r.priority == FollowupPriority.CRITICAL

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_followup(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_followup
# -------------------------------------------------------------------


class TestGetFollowup:
    def test_found(self):
        eng = _engine()
        r = eng.record_followup("svc-a")
        assert eng.get_followup(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_followup("nonexistent") is None


# -------------------------------------------------------------------
# list_followups
# -------------------------------------------------------------------


class TestListFollowups:
    def test_list_all(self):
        eng = _engine()
        eng.record_followup("svc-a")
        eng.record_followup("svc-b")
        assert len(eng.list_followups()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_followup("svc-a")
        eng.record_followup("svc-b")
        results = eng.list_followups(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_followup("svc-a", followup_type=FollowupType.PROCESS_CHANGE)
        eng.record_followup("svc-b", followup_type=FollowupType.ACTION_ITEM)
        results = eng.list_followups(followup_type=FollowupType.PROCESS_CHANGE)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_assignment
# -------------------------------------------------------------------


class TestAddAssignment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assignment(
            "alice",
            followup_type=FollowupType.TOOLING_IMPROVEMENT,
            status=FollowupStatus.IN_PROGRESS,
            due_days=14.0,
            description="Improve alerting",
        )
        assert a.assignee_name == "alice"
        assert a.due_days == 14.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_assignment(f"user-{i}")
        assert len(eng._assignments) == 2


# -------------------------------------------------------------------
# analyze_followup_completion
# -------------------------------------------------------------------


class TestAnalyzeFollowupCompletion:
    def test_with_data(self):
        eng = _engine()
        eng.record_followup("svc-a", status=FollowupStatus.COMPLETED, age_days=5.0)
        eng.record_followup("svc-a", status=FollowupStatus.OPEN, age_days=10.0)
        result = eng.analyze_followup_completion("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_records"] == 2
        assert result["completion_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_followup_completion("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_overdue_items
# -------------------------------------------------------------------


class TestIdentifyOverdueItems:
    def test_with_overdue(self):
        eng = _engine(overdue_days=30)
        eng.record_followup("svc-a", status=FollowupStatus.OVERDUE)
        eng.record_followup("svc-a", age_days=45.0)
        eng.record_followup("svc-b", status=FollowupStatus.OPEN, age_days=5.0)
        results = eng.identify_overdue_items()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overdue_items() == []


# -------------------------------------------------------------------
# rank_by_age
# -------------------------------------------------------------------


class TestRankByAge:
    def test_with_data(self):
        eng = _engine()
        eng.record_followup("svc-a", age_days=45.0)
        eng.record_followup("svc-a", age_days=35.0)
        eng.record_followup("svc-b", age_days=5.0)
        results = eng.rank_by_age()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_age_days"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_age() == []


# -------------------------------------------------------------------
# detect_followup_bottlenecks
# -------------------------------------------------------------------


class TestDetectFollowupBottlenecks:
    def test_with_bottlenecks(self):
        eng = _engine()
        for _ in range(5):
            eng.record_followup("svc-a")
        eng.record_followup("svc-b")
        results = eng.detect_followup_bottlenecks()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["bottleneck"] is True

    def test_no_bottlenecks(self):
        eng = _engine()
        eng.record_followup("svc-a")
        assert eng.detect_followup_bottlenecks() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_followup("svc-a", status=FollowupStatus.COMPLETED, age_days=5.0)
        eng.record_followup("svc-b", status=FollowupStatus.OPEN, age_days=10.0)
        eng.add_assignment("alice")
        report = eng.generate_report()
        assert report.total_followups == 2
        assert report.total_assignments == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_followups == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_followup("svc-a")
        eng.add_assignment("alice")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._assignments) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_followups"] == 0
        assert stats["total_assignments"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_followup("svc-a", followup_type=FollowupType.ACTION_ITEM)
        eng.record_followup("svc-b", followup_type=FollowupType.PROCESS_CHANGE)
        eng.add_assignment("alice")
        stats = eng.get_stats()
        assert stats["total_followups"] == 2
        assert stats["total_assignments"] == 1
        assert stats["unique_services"] == 2
