"""Tests for shieldops.analytics.workflow_analyzer — WorkflowEfficiencyAnalyzer."""

from __future__ import annotations

from shieldops.analytics.workflow_analyzer import (
    BottleneckType,
    EfficiencyLevel,
    WorkflowEfficiencyAnalyzer,
    WorkflowEfficiencyReport,
    WorkflowRecord,
    WorkflowStep,
    WorkflowType,
)


def _engine(**kw) -> WorkflowEfficiencyAnalyzer:
    return WorkflowEfficiencyAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_workflow_type_incident_response(self):
        assert WorkflowType.INCIDENT_RESPONSE == "incident_response"

    def test_workflow_type_deployment(self):
        assert WorkflowType.DEPLOYMENT == "deployment"

    def test_workflow_type_change_management(self):
        assert WorkflowType.CHANGE_MANAGEMENT == "change_management"

    def test_workflow_type_security_review(self):
        assert WorkflowType.SECURITY_REVIEW == "security_review"

    def test_workflow_type_maintenance(self):
        assert WorkflowType.MAINTENANCE == "maintenance"

    def test_efficiency_level_optimal(self):
        assert EfficiencyLevel.OPTIMAL == "optimal"

    def test_efficiency_level_efficient(self):
        assert EfficiencyLevel.EFFICIENT == "efficient"

    def test_efficiency_level_acceptable(self):
        assert EfficiencyLevel.ACCEPTABLE == "acceptable"

    def test_efficiency_level_inefficient(self):
        assert EfficiencyLevel.INEFFICIENT == "inefficient"

    def test_efficiency_level_broken(self):
        assert EfficiencyLevel.BROKEN == "broken"

    def test_bottleneck_type_approval_delay(self):
        assert BottleneckType.APPROVAL_DELAY == "approval_delay"

    def test_bottleneck_type_manual_step(self):
        assert BottleneckType.MANUAL_STEP == "manual_step"

    def test_bottleneck_type_handoff_gap(self):
        assert BottleneckType.HANDOFF_GAP == "handoff_gap"

    def test_bottleneck_type_tool_limitation(self):
        assert BottleneckType.TOOL_LIMITATION == "tool_limitation"

    def test_bottleneck_type_process_gap(self):
        assert BottleneckType.PROCESS_GAP == "process_gap"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_workflow_record_defaults(self):
        r = WorkflowRecord()
        assert r.id
        assert r.workflow_id == ""
        assert r.workflow_type == WorkflowType.INCIDENT_RESPONSE
        assert r.efficiency_level == EfficiencyLevel.ACCEPTABLE
        assert r.bottleneck_type == BottleneckType.MANUAL_STEP
        assert r.efficiency_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_workflow_step_defaults(self):
        s = WorkflowStep()
        assert s.id
        assert s.step_pattern == ""
        assert s.workflow_type == WorkflowType.INCIDENT_RESPONSE
        assert s.duration_minutes == 0.0
        assert s.automation_pct == 0.0
        assert s.description == ""
        assert s.created_at > 0

    def test_workflow_efficiency_report_defaults(self):
        r = WorkflowEfficiencyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_steps == 0
        assert r.efficient_workflows == 0
        assert r.avg_efficiency_score == 0.0
        assert r.by_type == {}
        assert r.by_level == {}
        assert r.by_bottleneck == {}
        assert r.inefficient == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_workflow
# ---------------------------------------------------------------------------


class TestRecordWorkflow:
    def test_basic(self):
        eng = _engine()
        r = eng.record_workflow(
            workflow_id="WF-001",
            workflow_type=WorkflowType.DEPLOYMENT,
            efficiency_level=EfficiencyLevel.OPTIMAL,
            bottleneck_type=BottleneckType.APPROVAL_DELAY,
            efficiency_score=95.0,
            team="sre",
        )
        assert r.workflow_id == "WF-001"
        assert r.workflow_type == WorkflowType.DEPLOYMENT
        assert r.efficiency_level == EfficiencyLevel.OPTIMAL
        assert r.bottleneck_type == BottleneckType.APPROVAL_DELAY
        assert r.efficiency_score == 95.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_workflow(workflow_id=f"WF-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_workflow
# ---------------------------------------------------------------------------


class TestGetWorkflow:
    def test_found(self):
        eng = _engine()
        r = eng.record_workflow(
            workflow_id="WF-001",
            workflow_type=WorkflowType.CHANGE_MANAGEMENT,
        )
        result = eng.get_workflow(r.id)
        assert result is not None
        assert result.workflow_type == WorkflowType.CHANGE_MANAGEMENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_workflow("nonexistent") is None


# ---------------------------------------------------------------------------
# list_workflows
# ---------------------------------------------------------------------------


class TestListWorkflows:
    def test_list_all(self):
        eng = _engine()
        eng.record_workflow(workflow_id="WF-001")
        eng.record_workflow(workflow_id="WF-002")
        assert len(eng.list_workflows()) == 2

    def test_filter_by_workflow_type(self):
        eng = _engine()
        eng.record_workflow(
            workflow_id="WF-001",
            workflow_type=WorkflowType.INCIDENT_RESPONSE,
        )
        eng.record_workflow(
            workflow_id="WF-002",
            workflow_type=WorkflowType.MAINTENANCE,
        )
        results = eng.list_workflows(workflow_type=WorkflowType.INCIDENT_RESPONSE)
        assert len(results) == 1

    def test_filter_by_efficiency_level(self):
        eng = _engine()
        eng.record_workflow(
            workflow_id="WF-001",
            efficiency_level=EfficiencyLevel.OPTIMAL,
        )
        eng.record_workflow(
            workflow_id="WF-002",
            efficiency_level=EfficiencyLevel.BROKEN,
        )
        results = eng.list_workflows(efficiency_level=EfficiencyLevel.OPTIMAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_workflow(workflow_id="WF-001", team="sre")
        eng.record_workflow(workflow_id="WF-002", team="platform")
        results = eng.list_workflows(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_workflow(workflow_id=f"WF-{i}")
        assert len(eng.list_workflows(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_step
# ---------------------------------------------------------------------------


class TestAddStep:
    def test_basic(self):
        eng = _engine()
        s = eng.add_step(
            step_pattern="approval-*",
            workflow_type=WorkflowType.SECURITY_REVIEW,
            duration_minutes=30.0,
            automation_pct=50.0,
            description="Security review approval step",
        )
        assert s.step_pattern == "approval-*"
        assert s.workflow_type == WorkflowType.SECURITY_REVIEW
        assert s.duration_minutes == 30.0
        assert s.automation_pct == 50.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_step(step_pattern=f"step-{i}")
        assert len(eng._steps) == 2


# ---------------------------------------------------------------------------
# analyze_workflow_efficiency
# ---------------------------------------------------------------------------


class TestAnalyzeWorkflowEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_workflow(
            workflow_id="WF-001",
            workflow_type=WorkflowType.DEPLOYMENT,
            efficiency_score=90.0,
        )
        eng.record_workflow(
            workflow_id="WF-002",
            workflow_type=WorkflowType.DEPLOYMENT,
            efficiency_score=80.0,
        )
        result = eng.analyze_workflow_efficiency()
        assert "deployment" in result
        assert result["deployment"]["count"] == 2
        assert result["deployment"]["avg_efficiency_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_workflow_efficiency() == {}


# ---------------------------------------------------------------------------
# identify_inefficient_workflows
# ---------------------------------------------------------------------------


class TestIdentifyInefficientWorkflows:
    def test_detects_inefficient(self):
        eng = _engine(min_efficiency_score=70.0)
        eng.record_workflow(
            workflow_id="WF-001",
            efficiency_score=40.0,
        )
        eng.record_workflow(
            workflow_id="WF-002",
            efficiency_score=90.0,
        )
        results = eng.identify_inefficient_workflows()
        assert len(results) == 1
        assert results[0]["workflow_id"] == "WF-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_inefficient_workflows() == []


# ---------------------------------------------------------------------------
# rank_by_efficiency_score
# ---------------------------------------------------------------------------


class TestRankByEfficiencyScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_workflow(workflow_id="WF-001", team="sre", efficiency_score=90.0)
        eng.record_workflow(workflow_id="WF-002", team="sre", efficiency_score=80.0)
        eng.record_workflow(workflow_id="WF-003", team="platform", efficiency_score=50.0)
        results = eng.rank_by_efficiency_score()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["total_efficiency"] == 170.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_efficiency_score() == []


# ---------------------------------------------------------------------------
# detect_workflow_bottlenecks
# ---------------------------------------------------------------------------


class TestDetectWorkflowBottlenecks:
    def test_stable(self):
        eng = _engine()
        for score in [70.0, 70.0, 70.0, 70.0]:
            eng.record_workflow(workflow_id="WF", efficiency_score=score)
        result = eng.detect_workflow_bottlenecks()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for score in [40.0, 40.0, 90.0, 90.0]:
            eng.record_workflow(workflow_id="WF", efficiency_score=score)
        result = eng.detect_workflow_bottlenecks()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_workflow_bottlenecks()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_efficiency_score=70.0)
        eng.record_workflow(
            workflow_id="WF-001",
            workflow_type=WorkflowType.DEPLOYMENT,
            efficiency_level=EfficiencyLevel.INEFFICIENT,
            efficiency_score=40.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, WorkflowEfficiencyReport)
        assert report.total_records == 1
        assert report.avg_efficiency_score == 40.0
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
        eng.record_workflow(workflow_id="WF-001")
        eng.add_step(step_pattern="s1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._steps) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_steps"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_workflow(
            workflow_id="WF-001",
            workflow_type=WorkflowType.DEPLOYMENT,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_workflows"] == 1
        assert "deployment" in stats["type_distribution"]
