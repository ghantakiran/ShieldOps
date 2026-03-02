"""Tests for shieldops.security.soar_workflow_optimizer — SOARWorkflowOptimizer."""

from __future__ import annotations

from shieldops.security.soar_workflow_optimizer import (
    OptimizationImpact,
    OptimizationType,
    SOARWorkflowOptimizer,
    WorkflowCategory,
    WorkflowOptAnalysis,
    WorkflowOptRecord,
    WorkflowOptReport,
)


def _engine(**kw) -> SOARWorkflowOptimizer:
    return SOARWorkflowOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_workflowcategory_val1(self):
        assert WorkflowCategory.ALERT_TRIAGE == "alert_triage"

    def test_workflowcategory_val2(self):
        assert WorkflowCategory.CONTAINMENT == "containment"

    def test_workflowcategory_val3(self):
        assert WorkflowCategory.INVESTIGATION == "investigation"

    def test_workflowcategory_val4(self):
        assert WorkflowCategory.ENRICHMENT == "enrichment"

    def test_workflowcategory_val5(self):
        assert WorkflowCategory.REPORTING == "reporting"

    def test_optimizationtype_val1(self):
        assert OptimizationType.AUTOMATION == "automation"

    def test_optimizationtype_val2(self):
        assert OptimizationType.PARALLELIZATION == "parallelization"

    def test_optimizationtype_val3(self):
        assert OptimizationType.DEDUPLICATION == "deduplication"

    def test_optimizationtype_val4(self):
        assert OptimizationType.PRIORITIZATION == "prioritization"

    def test_optimizationtype_val5(self):
        assert OptimizationType.ELIMINATION == "elimination"

    def test_optimizationimpact_val1(self):
        assert OptimizationImpact.HIGH == "high"

    def test_optimizationimpact_val2(self):
        assert OptimizationImpact.MEDIUM == "medium"

    def test_optimizationimpact_val3(self):
        assert OptimizationImpact.LOW == "low"

    def test_optimizationimpact_val4(self):
        assert OptimizationImpact.MINIMAL == "minimal"

    def test_optimizationimpact_val5(self):
        assert OptimizationImpact.NEGATIVE == "negative"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = WorkflowOptRecord()
        assert r.id
        assert r.name == ""
        assert r.workflow_category == WorkflowCategory.ALERT_TRIAGE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = WorkflowOptAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = WorkflowOptReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_category == {}
        assert r.by_optimization == {}
        assert r.by_impact == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_optimization(
            name="test",
            workflow_category=WorkflowCategory.CONTAINMENT,
            score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.name == "test"
        assert r.workflow_category == WorkflowCategory.CONTAINMENT
        assert r.score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_optimization(name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_optimization(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_optimization(name="a")
        eng.record_optimization(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_optimization(name="a", workflow_category=WorkflowCategory.ALERT_TRIAGE)
        eng.record_optimization(name="b", workflow_category=WorkflowCategory.CONTAINMENT)
        results = eng.list_records(workflow_category=WorkflowCategory.ALERT_TRIAGE)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_optimization(name="a", optimization_type=OptimizationType.AUTOMATION)
        eng.record_optimization(name="b", optimization_type=OptimizationType.PARALLELIZATION)
        results = eng.list_records(optimization_type=OptimizationType.AUTOMATION)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_optimization(name="a", team="sec")
        eng.record_optimization(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_optimization(name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_optimization(
            name="a",
            workflow_category=WorkflowCategory.ALERT_TRIAGE,
            score=90.0,
        )
        eng.record_optimization(
            name="b",
            workflow_category=WorkflowCategory.ALERT_TRIAGE,
            score=70.0,
        )
        result = eng.analyze_category_distribution()
        assert "alert_triage" in result
        assert result["alert_triage"]["count"] == 2
        assert result["alert_triage"]["avg_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_category_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(score_threshold=80.0)
        eng.record_optimization(name="a", score=60.0)
        eng.record_optimization(name="b", score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(score_threshold=80.0)
        eng.record_optimization(name="a", score=50.0)
        eng.record_optimization(name="b", score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_optimization(name="a", service="auth-svc", score=90.0)
        eng.record_optimization(name="b", service="api-gw", score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="t1", analysis_score=20.0)
        eng.add_analysis(name="t2", analysis_score=20.0)
        eng.add_analysis(name="t3", analysis_score=80.0)
        eng.add_analysis(name="t4", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(score_threshold=80.0)
        eng.record_optimization(
            name="test",
            workflow_category=WorkflowCategory.CONTAINMENT,
            score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, WorkflowOptReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy range" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_optimization(name="test")
        eng.add_analysis(name="test")
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
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_optimization(
            name="test",
            workflow_category=WorkflowCategory.ALERT_TRIAGE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "alert_triage" in stats["category_distribution"]
