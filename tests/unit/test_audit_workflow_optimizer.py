"""Tests for shieldops.audit.audit_workflow_optimizer — AuditWorkflowOptimizer."""

from __future__ import annotations

from shieldops.audit.audit_workflow_optimizer import (
    AuditWorkflowOptimizer,
    AuditWorkflowReport,
    BottleneckType,
    OptimizationType,
    WorkflowAnalysis,
    WorkflowRecord,
    WorkflowStage,
)


def _engine(**kw) -> AuditWorkflowOptimizer:
    return AuditWorkflowOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_stage_evidence_collection(self):
        assert WorkflowStage.EVIDENCE_COLLECTION == "evidence_collection"

    def test_stage_control_testing(self):
        assert WorkflowStage.CONTROL_TESTING == "control_testing"

    def test_stage_finding_review(self):
        assert WorkflowStage.FINDING_REVIEW == "finding_review"

    def test_stage_remediation_tracking(self):
        assert WorkflowStage.REMEDIATION_TRACKING == "remediation_tracking"

    def test_stage_report_generation(self):
        assert WorkflowStage.REPORT_GENERATION == "report_generation"

    def test_bottleneck_manual_handoff(self):
        assert BottleneckType.MANUAL_HANDOFF == "manual_handoff"

    def test_bottleneck_approval_delay(self):
        assert BottleneckType.APPROVAL_DELAY == "approval_delay"

    def test_bottleneck_evidence_gap(self):
        assert BottleneckType.EVIDENCE_GAP == "evidence_gap"

    def test_bottleneck_resource_contention(self):
        assert BottleneckType.RESOURCE_CONTENTION == "resource_contention"

    def test_bottleneck_dependency_wait(self):
        assert BottleneckType.DEPENDENCY_WAIT == "dependency_wait"

    def test_optimization_parallelize(self):
        assert OptimizationType.PARALLELIZE == "parallelize"

    def test_optimization_automate(self):
        assert OptimizationType.AUTOMATE == "automate"

    def test_optimization_eliminate(self):
        assert OptimizationType.ELIMINATE == "eliminate"

    def test_optimization_consolidate(self):
        assert OptimizationType.CONSOLIDATE == "consolidate"

    def test_optimization_defer(self):
        assert OptimizationType.DEFER == "defer"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_workflow_record_defaults(self):
        r = WorkflowRecord()
        assert r.id
        assert r.workflow_name == ""
        assert r.workflow_stage == WorkflowStage.EVIDENCE_COLLECTION
        assert r.bottleneck_type == BottleneckType.MANUAL_HANDOFF
        assert r.optimization_type == OptimizationType.PARALLELIZE
        assert r.cycle_time_hours == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_workflow_analysis_defaults(self):
        a = WorkflowAnalysis()
        assert a.id
        assert a.workflow_name == ""
        assert a.workflow_stage == WorkflowStage.EVIDENCE_COLLECTION
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_workflow_report_defaults(self):
        r = AuditWorkflowReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.long_cycle_count == 0
        assert r.avg_cycle_time == 0.0
        assert r.by_stage == {}
        assert r.by_bottleneck == {}
        assert r.by_optimization == {}
        assert r.top_long_cycles == []
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
            workflow_name="SOC2-Annual",
            workflow_stage=WorkflowStage.CONTROL_TESTING,
            bottleneck_type=BottleneckType.APPROVAL_DELAY,
            optimization_type=OptimizationType.AUTOMATE,
            cycle_time_hours=48.0,
            service="api-gateway",
            team="sre",
        )
        assert r.workflow_name == "SOC2-Annual"
        assert r.workflow_stage == WorkflowStage.CONTROL_TESTING
        assert r.bottleneck_type == BottleneckType.APPROVAL_DELAY
        assert r.optimization_type == OptimizationType.AUTOMATE
        assert r.cycle_time_hours == 48.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_workflow(workflow_name=f"WF-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_workflow
# ---------------------------------------------------------------------------


class TestGetWorkflow:
    def test_found(self):
        eng = _engine()
        r = eng.record_workflow(
            workflow_name="SOC2-Annual",
            workflow_stage=WorkflowStage.FINDING_REVIEW,
        )
        result = eng.get_workflow(r.id)
        assert result is not None
        assert result.workflow_stage == WorkflowStage.FINDING_REVIEW

    def test_not_found(self):
        eng = _engine()
        assert eng.get_workflow("nonexistent") is None


# ---------------------------------------------------------------------------
# list_workflows
# ---------------------------------------------------------------------------


class TestListWorkflows:
    def test_list_all(self):
        eng = _engine()
        eng.record_workflow(workflow_name="WF-001")
        eng.record_workflow(workflow_name="WF-002")
        assert len(eng.list_workflows()) == 2

    def test_filter_by_stage(self):
        eng = _engine()
        eng.record_workflow(
            workflow_name="WF-001",
            workflow_stage=WorkflowStage.EVIDENCE_COLLECTION,
        )
        eng.record_workflow(
            workflow_name="WF-002",
            workflow_stage=WorkflowStage.REPORT_GENERATION,
        )
        results = eng.list_workflows(workflow_stage=WorkflowStage.EVIDENCE_COLLECTION)
        assert len(results) == 1

    def test_filter_by_bottleneck(self):
        eng = _engine()
        eng.record_workflow(
            workflow_name="WF-001",
            bottleneck_type=BottleneckType.MANUAL_HANDOFF,
        )
        eng.record_workflow(
            workflow_name="WF-002",
            bottleneck_type=BottleneckType.EVIDENCE_GAP,
        )
        results = eng.list_workflows(bottleneck_type=BottleneckType.MANUAL_HANDOFF)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_workflow(workflow_name="WF-001", team="sre")
        eng.record_workflow(workflow_name="WF-002", team="platform")
        results = eng.list_workflows(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_workflow(workflow_name=f"WF-{i}")
        assert len(eng.list_workflows(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            workflow_name="SOC2-Annual",
            workflow_stage=WorkflowStage.CONTROL_TESTING,
            analysis_score=75.0,
            threshold=80.0,
            breached=True,
            description="Below target",
        )
        assert a.workflow_name == "SOC2-Annual"
        assert a.workflow_stage == WorkflowStage.CONTROL_TESTING
        assert a.analysis_score == 75.0
        assert a.threshold == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(workflow_name=f"WF-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_workflow_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeWorkflowDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_workflow(
            workflow_name="WF-001",
            workflow_stage=WorkflowStage.EVIDENCE_COLLECTION,
            cycle_time_hours=24.0,
        )
        eng.record_workflow(
            workflow_name="WF-002",
            workflow_stage=WorkflowStage.EVIDENCE_COLLECTION,
            cycle_time_hours=48.0,
        )
        result = eng.analyze_workflow_distribution()
        assert "evidence_collection" in result
        assert result["evidence_collection"]["count"] == 2
        assert result["evidence_collection"]["avg_cycle_time"] == 36.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_workflow_distribution() == {}


# ---------------------------------------------------------------------------
# identify_long_cycle_workflows
# ---------------------------------------------------------------------------


class TestIdentifyLongCycleWorkflows:
    def test_detects_long(self):
        eng = _engine(cycle_time_threshold=72.0)
        eng.record_workflow(
            workflow_name="WF-001",
            cycle_time_hours=100.0,
        )
        eng.record_workflow(
            workflow_name="WF-002",
            cycle_time_hours=50.0,
        )
        results = eng.identify_long_cycle_workflows()
        assert len(results) == 1
        assert results[0]["workflow_name"] == "WF-001"

    def test_sorted_descending(self):
        eng = _engine(cycle_time_threshold=72.0)
        eng.record_workflow(workflow_name="WF-001", cycle_time_hours=80.0)
        eng.record_workflow(workflow_name="WF-002", cycle_time_hours=120.0)
        results = eng.identify_long_cycle_workflows()
        assert len(results) == 2
        assert results[0]["cycle_time_hours"] == 120.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_long_cycle_workflows() == []


# ---------------------------------------------------------------------------
# rank_by_cycle_time
# ---------------------------------------------------------------------------


class TestRankByCycleTime:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_workflow(workflow_name="WF-001", cycle_time_hours=10.0, service="svc-a")
        eng.record_workflow(workflow_name="WF-002", cycle_time_hours=50.0, service="svc-b")
        results = eng.rank_by_cycle_time()
        assert len(results) == 2
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_cycle_time"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cycle_time() == []


# ---------------------------------------------------------------------------
# detect_workflow_trends
# ---------------------------------------------------------------------------


class TestDetectWorkflowTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(workflow_name="WF-001", analysis_score=70.0)
        result = eng.detect_workflow_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(workflow_name="WF-001", analysis_score=50.0)
        eng.add_analysis(workflow_name="WF-002", analysis_score=50.0)
        eng.add_analysis(workflow_name="WF-003", analysis_score=80.0)
        eng.add_analysis(workflow_name="WF-004", analysis_score=80.0)
        result = eng.detect_workflow_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_workflow_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(cycle_time_threshold=72.0)
        eng.record_workflow(
            workflow_name="SOC2-Annual",
            workflow_stage=WorkflowStage.EVIDENCE_COLLECTION,
            bottleneck_type=BottleneckType.APPROVAL_DELAY,
            cycle_time_hours=100.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AuditWorkflowReport)
        assert report.total_records == 1
        assert report.long_cycle_count == 1
        assert len(report.top_long_cycles) == 1
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
        eng.record_workflow(workflow_name="WF-001")
        eng.add_analysis(workflow_name="WF-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["stage_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_workflow(
            workflow_name="WF-001",
            workflow_stage=WorkflowStage.EVIDENCE_COLLECTION,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "evidence_collection" in stats["stage_distribution"]
