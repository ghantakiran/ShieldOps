"""Tests for shieldops.security.security_workflow_automator — SecurityWorkflowAutomator."""

from __future__ import annotations

from shieldops.security.security_workflow_automator import (
    AutomationLevel,
    SecurityWorkflowAutomator,
    WorkflowAutomationAnalysis,
    WorkflowAutomationRecord,
    WorkflowAutomationReport,
    WorkflowStatus,
    WorkflowType,
)


def _engine(**kw) -> SecurityWorkflowAutomator:
    return SecurityWorkflowAutomator(**kw)


class TestEnums:
    def test_workflowtype_val1(self):
        assert WorkflowType.ALERT_TRIAGE == "alert_triage"

    def test_workflowtype_val2(self):
        assert WorkflowType.INCIDENT_RESPONSE == "incident_response"

    def test_workflowtype_val3(self):
        assert WorkflowType.THREAT_HUNT == "threat_hunt"

    def test_workflowtype_val4(self):
        assert WorkflowType.COMPLIANCE_CHECK == "compliance_check"

    def test_workflowtype_val5(self):
        assert WorkflowType.VULNERABILITY_SCAN == "vulnerability_scan"

    def test_automationlevel_val1(self):
        assert AutomationLevel.FULL == "full"

    def test_automationlevel_val2(self):
        assert AutomationLevel.PARTIAL == "partial"

    def test_automationlevel_val3(self):
        assert AutomationLevel.ASSISTED == "assisted"

    def test_automationlevel_val4(self):
        assert AutomationLevel.MANUAL == "manual"

    def test_automationlevel_val5(self):
        assert AutomationLevel.DISABLED == "disabled"

    def test_workflowstatus_val1(self):
        assert WorkflowStatus.ACTIVE == "active"

    def test_workflowstatus_val2(self):
        assert WorkflowStatus.PAUSED == "paused"

    def test_workflowstatus_val3(self):
        assert WorkflowStatus.COMPLETED == "completed"

    def test_workflowstatus_val4(self):
        assert WorkflowStatus.FAILED == "failed"

    def test_workflowstatus_val5(self):
        assert WorkflowStatus.DEPRECATED == "deprecated"


class TestModels:
    def test_record_defaults(self):
        r = WorkflowAutomationRecord()
        assert r.id
        assert r.workflow_name == ""

    def test_analysis_defaults(self):
        a = WorkflowAutomationAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = WorkflowAutomationReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_workflow(
            workflow_name="test",
            workflow_type=WorkflowType.INCIDENT_RESPONSE,
            automation_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.workflow_name == "test"
        assert r.automation_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_workflow(workflow_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_workflow(workflow_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_workflow(workflow_name="a")
        eng.record_workflow(workflow_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_workflow(workflow_name="a", workflow_type=WorkflowType.ALERT_TRIAGE)
        eng.record_workflow(workflow_name="b", workflow_type=WorkflowType.INCIDENT_RESPONSE)
        assert len(eng.list_records(workflow_type=WorkflowType.ALERT_TRIAGE)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_workflow(workflow_name="a", automation_level=AutomationLevel.FULL)
        eng.record_workflow(workflow_name="b", automation_level=AutomationLevel.PARTIAL)
        assert len(eng.list_records(automation_level=AutomationLevel.FULL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_workflow(workflow_name="a", team="sec")
        eng.record_workflow(workflow_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_workflow(workflow_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            workflow_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(workflow_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_workflow(
            workflow_name="a", workflow_type=WorkflowType.ALERT_TRIAGE, automation_score=90.0
        )
        eng.record_workflow(
            workflow_name="b", workflow_type=WorkflowType.ALERT_TRIAGE, automation_score=70.0
        )
        result = eng.analyze_distribution()
        assert WorkflowType.ALERT_TRIAGE.value in result
        assert result[WorkflowType.ALERT_TRIAGE.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_workflow(workflow_name="a", automation_score=60.0)
        eng.record_workflow(workflow_name="b", automation_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_workflow(workflow_name="a", automation_score=50.0)
        eng.record_workflow(workflow_name="b", automation_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["automation_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_workflow(workflow_name="a", service="auth", automation_score=90.0)
        eng.record_workflow(workflow_name="b", service="api", automation_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(workflow_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(workflow_name="a", analysis_score=20.0)
        eng.add_analysis(workflow_name="b", analysis_score=20.0)
        eng.add_analysis(workflow_name="c", analysis_score=80.0)
        eng.add_analysis(workflow_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_workflow(workflow_name="test", automation_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_workflow(workflow_name="test")
        eng.add_analysis(workflow_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_workflow(workflow_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
