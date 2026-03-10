"""Tests for WorkflowIntelligenceEngine."""

from __future__ import annotations

from shieldops.operations.workflow_intelligence_engine import (
    ExecutionStatus,
    OptimizationGoal,
    WorkflowComplexity,
    WorkflowIntelligenceEngine,
)


def _engine(**kw) -> WorkflowIntelligenceEngine:
    return WorkflowIntelligenceEngine(**kw)


class TestEnums:
    def test_workflow_complexity_values(self):
        assert WorkflowComplexity.LINEAR == "linear"
        assert WorkflowComplexity.BRANCHING == "branching"
        assert WorkflowComplexity.PARALLEL == "parallel"
        assert WorkflowComplexity.ADAPTIVE == "adaptive"

    def test_execution_status_values(self):
        assert ExecutionStatus.PENDING == "pending"
        assert ExecutionStatus.RUNNING == "running"
        assert ExecutionStatus.COMPLETED == "completed"
        assert ExecutionStatus.FAILED == "failed"

    def test_optimization_goal_values(self):
        assert OptimizationGoal.SPEED == "speed"
        assert OptimizationGoal.RELIABILITY == "reliability"
        assert OptimizationGoal.COST == "cost"
        assert OptimizationGoal.COVERAGE == "coverage"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="wf-001",
            workflow_complexity=WorkflowComplexity.PARALLEL,
            execution_status=ExecutionStatus.COMPLETED,
            score=90.0,
            service="pipeline",
            team="platform",
        )
        assert r.name == "wf-001"
        assert r.workflow_complexity == WorkflowComplexity.PARALLEL
        assert r.score == 90.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=40.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.record_item(name="t", service="a", team="b")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.record_item(name="test")
        eng.add_analysis(name="test")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestAnalyzeWorkflowBottlenecks:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            name="a",
            service="api",
            execution_status=ExecutionStatus.FAILED,
            score=20.0,
        )
        eng.record_item(
            name="b",
            service="api",
            execution_status=ExecutionStatus.COMPLETED,
            score=80.0,
        )
        results = eng.analyze_workflow_bottlenecks()
        assert len(results) == 1
        assert results[0]["service"] == "api"
        assert results[0]["failed_count"] == 1

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_workflow_bottlenecks() == []


class TestRecommendWorkflowImprovements:
    def test_with_low_scores(self):
        eng = _engine(threshold=80.0)
        eng.record_item(
            name="a",
            workflow_complexity=WorkflowComplexity.ADAPTIVE,
            score=30.0,
        )
        results = eng.recommend_workflow_improvements()
        assert len(results) >= 1
        assert results[0]["complexity_type"] == "adaptive"

    def test_empty(self):
        eng = _engine()
        assert eng.recommend_workflow_improvements() == []


class TestComputeWorkflowEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            name="a",
            optimization_goal=OptimizationGoal.SPEED,
            score=85.0,
        )
        result = eng.compute_workflow_efficiency()
        assert result["overall_efficiency"] == 85.0
        assert result["total_workflows"] == 1

    def test_empty(self):
        eng = _engine()
        result = eng.compute_workflow_efficiency()
        assert result["overall_efficiency"] == 0.0
