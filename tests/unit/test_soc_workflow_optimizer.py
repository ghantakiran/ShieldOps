"""Tests for shieldops.operations.soc_workflow_optimizer — SocWorkflowOptimizer."""

from __future__ import annotations

from shieldops.operations.soc_workflow_optimizer import (
    OptimizationArea,
    SocWorkflowOptimizer,
    SocWorkflowReport,
    WorkflowAnalysis,
    WorkflowEfficiency,
    WorkflowPhase,
    WorkflowRecord,
)


def _engine(**kw) -> SocWorkflowOptimizer:
    return SocWorkflowOptimizer(**kw)


class TestEnums:
    def test_workflow_phase_triage(self):
        assert WorkflowPhase.TRIAGE == "triage"

    def test_workflow_phase_investigation(self):
        assert WorkflowPhase.INVESTIGATION == "investigation"

    def test_workflow_phase_containment(self):
        assert WorkflowPhase.CONTAINMENT == "containment"

    def test_workflow_phase_remediation(self):
        assert WorkflowPhase.REMEDIATION == "remediation"

    def test_workflow_phase_closure(self):
        assert WorkflowPhase.CLOSURE == "closure"

    def test_optimization_area_automation(self):
        assert OptimizationArea.AUTOMATION == "automation"

    def test_optimization_area_routing(self):
        assert OptimizationArea.ROUTING == "routing"

    def test_optimization_area_prioritization(self):
        assert OptimizationArea.PRIORITIZATION == "prioritization"

    def test_optimization_area_enrichment(self):
        assert OptimizationArea.ENRICHMENT == "enrichment"

    def test_optimization_area_handoff(self):
        assert OptimizationArea.HANDOFF == "handoff"

    def test_workflow_efficiency_optimal(self):
        assert WorkflowEfficiency.OPTIMAL == "optimal"

    def test_workflow_efficiency_good(self):
        assert WorkflowEfficiency.GOOD == "good"

    def test_workflow_efficiency_needs_improvement(self):
        assert WorkflowEfficiency.NEEDS_IMPROVEMENT == "needs_improvement"

    def test_workflow_efficiency_poor(self):
        assert WorkflowEfficiency.POOR == "poor"

    def test_workflow_efficiency_blocked(self):
        assert WorkflowEfficiency.BLOCKED == "blocked"


class TestModels:
    def test_record_defaults(self):
        r = WorkflowRecord()
        assert r.id
        assert r.name == ""
        assert r.workflow_phase == WorkflowPhase.TRIAGE
        assert r.optimization_area == OptimizationArea.AUTOMATION
        assert r.workflow_efficiency == WorkflowEfficiency.BLOCKED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = WorkflowAnalysis()
        assert a.id
        assert a.name == ""
        assert a.workflow_phase == WorkflowPhase.TRIAGE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = SocWorkflowReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_workflow_phase == {}
        assert r.by_optimization_area == {}
        assert r.by_workflow_efficiency == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            workflow_phase=WorkflowPhase.TRIAGE,
            optimization_area=OptimizationArea.ROUTING,
            workflow_efficiency=WorkflowEfficiency.OPTIMAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.workflow_phase == WorkflowPhase.TRIAGE
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_workflow_phase(self):
        eng = _engine()
        eng.record_entry(name="a", workflow_phase=WorkflowPhase.TRIAGE)
        eng.record_entry(name="b", workflow_phase=WorkflowPhase.INVESTIGATION)
        assert len(eng.list_records(workflow_phase=WorkflowPhase.TRIAGE)) == 1

    def test_filter_by_optimization_area(self):
        eng = _engine()
        eng.record_entry(name="a", optimization_area=OptimizationArea.AUTOMATION)
        eng.record_entry(name="b", optimization_area=OptimizationArea.ROUTING)
        assert len(eng.list_records(optimization_area=OptimizationArea.AUTOMATION)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", workflow_phase=WorkflowPhase.INVESTIGATION, score=90.0)
        eng.record_entry(name="b", workflow_phase=WorkflowPhase.INVESTIGATION, score=70.0)
        result = eng.analyze_distribution()
        assert "investigation" in result
        assert result["investigation"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
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
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
