"""Tests for shieldops.security.soar_playbook_engine — SOARPlaybookEngine."""

from __future__ import annotations

from shieldops.security.soar_playbook_engine import (
    ActionType,
    ExecutionResult,
    PlaybookExecution,
    PlaybookRecord,
    PlaybookStatus,
    SOARPlaybookEngine,
    SOARPlaybookReport,
)


def _engine(**kw) -> SOARPlaybookEngine:
    return SOARPlaybookEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_active(self):
        assert PlaybookStatus.ACTIVE == "active"

    def test_status_draft(self):
        assert PlaybookStatus.DRAFT == "draft"

    def test_status_deprecated(self):
        assert PlaybookStatus.DEPRECATED == "deprecated"

    def test_status_testing(self):
        assert PlaybookStatus.TESTING == "testing"

    def test_status_disabled(self):
        assert PlaybookStatus.DISABLED == "disabled"

    def test_action_containment(self):
        assert ActionType.CONTAINMENT == "containment"

    def test_action_eradication(self):
        assert ActionType.ERADICATION == "eradication"

    def test_action_recovery(self):
        assert ActionType.RECOVERY == "recovery"

    def test_action_investigation(self):
        assert ActionType.INVESTIGATION == "investigation"

    def test_action_notification(self):
        assert ActionType.NOTIFICATION == "notification"

    def test_result_success(self):
        assert ExecutionResult.SUCCESS == "success"

    def test_result_partial(self):
        assert ExecutionResult.PARTIAL == "partial"

    def test_result_failure(self):
        assert ExecutionResult.FAILURE == "failure"

    def test_result_timeout(self):
        assert ExecutionResult.TIMEOUT == "timeout"

    def test_result_skipped(self):
        assert ExecutionResult.SKIPPED == "skipped"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_playbook_record_defaults(self):
        r = PlaybookRecord()
        assert r.id
        assert r.playbook_name == ""
        assert r.playbook_status == PlaybookStatus.ACTIVE
        assert r.action_type == ActionType.CONTAINMENT
        assert r.execution_result == ExecutionResult.SUCCESS
        assert r.effectiveness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_playbook_execution_defaults(self):
        c = PlaybookExecution()
        assert c.id
        assert c.playbook_name == ""
        assert c.playbook_status == PlaybookStatus.ACTIVE
        assert c.execution_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_soar_playbook_report_defaults(self):
        r = SOARPlaybookReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_executions == 0
        assert r.low_effectiveness_count == 0
        assert r.avg_effectiveness_score == 0.0
        assert r.by_status == {}
        assert r.by_action == {}
        assert r.by_result == {}
        assert r.top_low_effectiveness == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_playbook
# ---------------------------------------------------------------------------


class TestRecordPlaybook:
    def test_basic(self):
        eng = _engine()
        r = eng.record_playbook(
            playbook_name="isolate-host",
            playbook_status=PlaybookStatus.DRAFT,
            action_type=ActionType.ERADICATION,
            execution_result=ExecutionResult.PARTIAL,
            effectiveness_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.playbook_name == "isolate-host"
        assert r.playbook_status == PlaybookStatus.DRAFT
        assert r.action_type == ActionType.ERADICATION
        assert r.execution_result == ExecutionResult.PARTIAL
        assert r.effectiveness_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_playbook(playbook_name=f"PB-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_playbook
# ---------------------------------------------------------------------------


class TestGetPlaybook:
    def test_found(self):
        eng = _engine()
        r = eng.record_playbook(
            playbook_name="isolate-host",
            execution_result=ExecutionResult.SUCCESS,
        )
        result = eng.get_playbook(r.id)
        assert result is not None
        assert result.execution_result == ExecutionResult.SUCCESS

    def test_not_found(self):
        eng = _engine()
        assert eng.get_playbook("nonexistent") is None


# ---------------------------------------------------------------------------
# list_playbooks
# ---------------------------------------------------------------------------


class TestListPlaybooks:
    def test_list_all(self):
        eng = _engine()
        eng.record_playbook(playbook_name="PB-001")
        eng.record_playbook(playbook_name="PB-002")
        assert len(eng.list_playbooks()) == 2

    def test_filter_by_playbook_status(self):
        eng = _engine()
        eng.record_playbook(
            playbook_name="PB-001",
            playbook_status=PlaybookStatus.ACTIVE,
        )
        eng.record_playbook(
            playbook_name="PB-002",
            playbook_status=PlaybookStatus.DRAFT,
        )
        results = eng.list_playbooks(playbook_status=PlaybookStatus.ACTIVE)
        assert len(results) == 1

    def test_filter_by_action_type(self):
        eng = _engine()
        eng.record_playbook(
            playbook_name="PB-001",
            action_type=ActionType.CONTAINMENT,
        )
        eng.record_playbook(
            playbook_name="PB-002",
            action_type=ActionType.RECOVERY,
        )
        results = eng.list_playbooks(
            action_type=ActionType.CONTAINMENT,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_playbook(playbook_name="PB-001", team="security")
        eng.record_playbook(playbook_name="PB-002", team="platform")
        results = eng.list_playbooks(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_playbook(playbook_name=f"PB-{i}")
        assert len(eng.list_playbooks(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_execution
# ---------------------------------------------------------------------------


class TestAddExecution:
    def test_basic(self):
        eng = _engine()
        e = eng.add_execution(
            playbook_name="isolate-host",
            playbook_status=PlaybookStatus.DRAFT,
            execution_score=88.5,
            threshold=80.0,
            breached=True,
            description="execution completed with warnings",
        )
        assert e.playbook_name == "isolate-host"
        assert e.playbook_status == PlaybookStatus.DRAFT
        assert e.execution_score == 88.5
        assert e.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_execution(playbook_name=f"PB-{i}")
        assert len(eng._executions) == 2


# ---------------------------------------------------------------------------
# analyze_playbook_distribution
# ---------------------------------------------------------------------------


class TestAnalyzePlaybookDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_playbook(
            playbook_name="PB-001",
            playbook_status=PlaybookStatus.ACTIVE,
            effectiveness_score=90.0,
        )
        eng.record_playbook(
            playbook_name="PB-002",
            playbook_status=PlaybookStatus.ACTIVE,
            effectiveness_score=70.0,
        )
        result = eng.analyze_playbook_distribution()
        assert "active" in result
        assert result["active"]["count"] == 2
        assert result["active"]["avg_effectiveness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_playbook_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_effectiveness_playbooks
# ---------------------------------------------------------------------------


class TestIdentifyLowEffectivenessPlaybooks:
    def test_detects_below_threshold(self):
        eng = _engine(effectiveness_threshold=80.0)
        eng.record_playbook(playbook_name="PB-001", effectiveness_score=60.0)
        eng.record_playbook(playbook_name="PB-002", effectiveness_score=90.0)
        results = eng.identify_low_effectiveness_playbooks()
        assert len(results) == 1
        assert results[0]["playbook_name"] == "PB-001"

    def test_sorted_ascending(self):
        eng = _engine(effectiveness_threshold=80.0)
        eng.record_playbook(playbook_name="PB-001", effectiveness_score=50.0)
        eng.record_playbook(playbook_name="PB-002", effectiveness_score=30.0)
        results = eng.identify_low_effectiveness_playbooks()
        assert len(results) == 2
        assert results[0]["effectiveness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_effectiveness_playbooks() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_playbook(playbook_name="PB-001", service="auth-svc", effectiveness_score=90.0)
        eng.record_playbook(playbook_name="PB-002", service="api-gw", effectiveness_score=50.0)
        results = eng.rank_by_effectiveness()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_effectiveness_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# ---------------------------------------------------------------------------
# detect_execution_trends
# ---------------------------------------------------------------------------


class TestDetectExecutionTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_execution(playbook_name="PB-001", execution_score=50.0)
        result = eng.detect_execution_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_execution(playbook_name="PB-001", execution_score=20.0)
        eng.add_execution(playbook_name="PB-002", execution_score=20.0)
        eng.add_execution(playbook_name="PB-003", execution_score=80.0)
        eng.add_execution(playbook_name="PB-004", execution_score=80.0)
        result = eng.detect_execution_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_execution_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(effectiveness_threshold=80.0)
        eng.record_playbook(
            playbook_name="isolate-host",
            playbook_status=PlaybookStatus.DRAFT,
            action_type=ActionType.ERADICATION,
            execution_result=ExecutionResult.PARTIAL,
            effectiveness_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SOARPlaybookReport)
        assert report.total_records == 1
        assert report.low_effectiveness_count == 1
        assert len(report.top_low_effectiveness) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_playbook(playbook_name="PB-001")
        eng.add_execution(playbook_name="PB-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._executions) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_executions"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_playbook(
            playbook_name="PB-001",
            playbook_status=PlaybookStatus.ACTIVE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "active" in stats["status_distribution"]
