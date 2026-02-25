"""Tests for shieldops.incidents.action_tracker — PostIncidentActionTracker."""

from __future__ import annotations

from shieldops.incidents.action_tracker import (
    ActionCategory,
    ActionPriority,
    ActionStatus,
    ActionSummary,
    ActionTrackerReport,
    PostIncidentAction,
    PostIncidentActionTracker,
)


def _engine(**kw) -> PostIncidentActionTracker:
    return PostIncidentActionTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_open(self):
        assert ActionStatus.OPEN == "open"

    def test_status_in_progress(self):
        assert ActionStatus.IN_PROGRESS == "in_progress"

    def test_status_completed(self):
        assert ActionStatus.COMPLETED == "completed"

    def test_status_overdue(self):
        assert ActionStatus.OVERDUE == "overdue"

    def test_status_cancelled(self):
        assert ActionStatus.CANCELLED == "cancelled"

    def test_priority_critical(self):
        assert ActionPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert ActionPriority.HIGH == "high"

    def test_priority_medium(self):
        assert ActionPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert ActionPriority.LOW == "low"

    def test_priority_optional(self):
        assert ActionPriority.OPTIONAL == "optional"

    def test_category_prevention(self):
        assert ActionCategory.PREVENTION == "prevention"

    def test_category_detection(self):
        assert ActionCategory.DETECTION == "detection"

    def test_category_response(self):
        assert ActionCategory.RESPONSE == "response"

    def test_category_documentation(self):
        assert ActionCategory.DOCUMENTATION == "documentation"

    def test_category_process(self):
        assert ActionCategory.PROCESS == "process"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_post_incident_action_defaults(self):
        r = PostIncidentAction()
        assert r.id
        assert r.incident_id == ""
        assert r.title == ""
        assert r.assignee == ""
        assert r.status == ActionStatus.OPEN
        assert r.priority == ActionPriority.MEDIUM
        assert r.category == ActionCategory.PREVENTION
        assert r.due_days == 30
        assert r.created_at > 0

    def test_action_summary_defaults(self):
        s = ActionSummary()
        assert s.id
        assert s.incident_id == ""
        assert s.total_actions == 0
        assert s.completed == 0

    def test_report_defaults(self):
        r = ActionTrackerReport()
        assert r.total_actions == 0
        assert r.total_completed == 0
        assert r.total_overdue == 0
        assert r.completion_rate_pct == 0.0
        assert r.by_status == {}
        assert r.by_priority == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_action
# ---------------------------------------------------------------------------


class TestRecordAction:
    def test_basic(self):
        eng = _engine()
        r = eng.record_action(
            incident_id="INC-001",
            title="Add monitoring",
            assignee="alice",
            priority=ActionPriority.HIGH,
            category=ActionCategory.DETECTION,
        )
        assert r.incident_id == "INC-001"
        assert r.title == "Add monitoring"
        assert r.assignee == "alice"
        assert r.priority == ActionPriority.HIGH
        assert r.status == ActionStatus.OPEN

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_action(incident_id=f"INC-{i}", title=f"Action {i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get / list / complete
# ---------------------------------------------------------------------------


class TestGetAction:
    def test_found(self):
        eng = _engine()
        r = eng.record_action(incident_id="INC-001", title="Fix it")
        result = eng.get_action(r.id)
        assert result is not None
        assert result.title == "Fix it"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_action("nonexistent") is None


class TestListActions:
    def test_list_all(self):
        eng = _engine()
        eng.record_action(incident_id="INC-001", title="A1")
        eng.record_action(incident_id="INC-002", title="A2")
        assert len(eng.list_actions()) == 2

    def test_filter_by_incident(self):
        eng = _engine()
        eng.record_action(incident_id="INC-001", title="A1")
        eng.record_action(incident_id="INC-002", title="A2")
        results = eng.list_actions(incident_id="INC-001")
        assert len(results) == 1

    def test_filter_by_assignee(self):
        eng = _engine()
        eng.record_action(incident_id="INC-001", title="A1", assignee="alice")
        eng.record_action(incident_id="INC-002", title="A2", assignee="bob")
        results = eng.list_actions(assignee="alice")
        assert len(results) == 1


class TestCompleteAction:
    def test_complete(self):
        eng = _engine()
        r = eng.record_action(incident_id="INC-001", title="Fix it")
        result = eng.complete_action(r.id)
        assert result is not None
        assert result.status == ActionStatus.COMPLETED

    def test_not_found(self):
        eng = _engine()
        assert eng.complete_action("nonexistent") is None


# ---------------------------------------------------------------------------
# domain operations
# ---------------------------------------------------------------------------


class TestIdentifyOverdueActions:
    def test_no_overdue(self):
        eng = _engine()
        eng.record_action(incident_id="INC-001", title="A1", due_days=9999)
        results = eng.identify_overdue_actions()
        assert len(results) == 0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overdue_actions() == []


class TestCalculateCompletionRate:
    def test_with_data(self):
        eng = _engine()
        r1 = eng.record_action(incident_id="INC-001", title="A1")
        eng.record_action(incident_id="INC-002", title="A2")
        eng.complete_action(r1.id)
        result = eng.calculate_completion_rate()
        assert result["total"] == 2
        assert result["completed"] == 1
        assert result["completion_rate_pct"] == 50.0

    def test_empty(self):
        eng = _engine()
        result = eng.calculate_completion_rate()
        assert result["total"] == 0


class TestSummarizeIncidentActions:
    def test_with_data(self):
        eng = _engine()
        r1 = eng.record_action(incident_id="INC-001", title="A1")
        eng.record_action(incident_id="INC-001", title="A2")
        eng.complete_action(r1.id)
        result = eng.summarize_incident_actions("INC-001")
        assert result["total_actions"] == 2
        assert result["completed"] == 1

    def test_no_data(self):
        eng = _engine()
        result = eng.summarize_incident_actions("unknown")
        assert result["total_actions"] == 0


class TestRankAssigneesByCompletion:
    def test_ranked(self):
        eng = _engine()
        r1 = eng.record_action(incident_id="INC-001", title="A1", assignee="alice")
        eng.record_action(incident_id="INC-002", title="A2", assignee="bob")
        eng.complete_action(r1.id)
        results = eng.rank_assignees_by_completion()
        assert len(results) == 2
        assert results[0]["assignee"] == "alice"
        assert results[0]["completion_rate_pct"] == 100.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_assignees_by_completion() == []


# ---------------------------------------------------------------------------
# report / clear / stats
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_action(incident_id="INC-001", title="A1", priority=ActionPriority.CRITICAL)
        report = eng.generate_report()
        assert isinstance(report, ActionTrackerReport)
        assert report.total_actions == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_actions == 0
        assert "All post-incident actions on track" in report.recommendations


class TestClearDataAT:
    def test_clears(self):
        eng = _engine()
        eng.record_action(incident_id="INC-001", title="A1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


class TestGetStatsAT:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_actions"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_action(incident_id="INC-001", title="A1", assignee="alice")
        stats = eng.get_stats()
        assert stats["total_actions"] == 1
        assert stats["unique_incidents"] == 1
        assert stats["unique_assignees"] == 1
