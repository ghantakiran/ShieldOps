"""Tests for shieldops.billing.budget_aware_autoscaler."""

from __future__ import annotations

from shieldops.billing.budget_aware_autoscaler import (
    AutoscalingAnalysis,
    AutoscalingRecord,
    BudgetAutoscalerReport,
    BudgetAwareAutoscaler,
    BudgetStatus,
    ScalingAction,
    ScalingStrategy,
)


def _engine(**kw) -> BudgetAwareAutoscaler:
    return BudgetAwareAutoscaler(**kw)


class TestEnums:
    def test_scalingstrategy_cost_optimized(self):
        assert ScalingStrategy.COST_OPTIMIZED == "cost_optimized"

    def test_scalingstrategy_performance_first(self):
        assert ScalingStrategy.PERFORMANCE_FIRST == "performance_first"

    def test_scalingstrategy_balanced(self):
        assert ScalingStrategy.BALANCED == "balanced"

    def test_scalingstrategy_conservative(self):
        assert ScalingStrategy.CONSERVATIVE == "conservative"

    def test_scalingstrategy_aggressive(self):
        assert ScalingStrategy.AGGRESSIVE == "aggressive"

    def test_budgetstatus_under_budget(self):
        assert BudgetStatus.UNDER_BUDGET == "under_budget"

    def test_budgetstatus_at_threshold(self):
        assert BudgetStatus.AT_THRESHOLD == "at_threshold"

    def test_budgetstatus_over_budget(self):
        assert BudgetStatus.OVER_BUDGET == "over_budget"

    def test_budgetstatus_critical(self):
        assert BudgetStatus.CRITICAL == "critical"

    def test_budgetstatus_exhausted(self):
        assert BudgetStatus.EXHAUSTED == "exhausted"

    def test_scalingaction_scale_up(self):
        assert ScalingAction.SCALE_UP == "scale_up"

    def test_scalingaction_scale_down(self):
        assert ScalingAction.SCALE_DOWN == "scale_down"

    def test_scalingaction_scale_out(self):
        assert ScalingAction.SCALE_OUT == "scale_out"

    def test_scalingaction_scale_in(self):
        assert ScalingAction.SCALE_IN == "scale_in"

    def test_scalingaction_maintain(self):
        assert ScalingAction.MAINTAIN == "maintain"


class TestModels:
    def test_autoscaling_record_defaults(self):
        r = AutoscalingRecord()
        assert r.id
        assert r.scaling_strategy == ScalingStrategy.BALANCED
        assert r.budget_status == BudgetStatus.UNDER_BUDGET
        assert r.scaling_action == ScalingAction.MAINTAIN
        assert r.budget_used_pct == 0.0
        assert r.resource_count == 0
        assert r.cost_impact == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_autoscaling_analysis_defaults(self):
        a = AutoscalingAnalysis()
        assert a.id
        assert a.scaling_strategy == ScalingStrategy.BALANCED
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_budget_autoscaler_report_defaults(self):
        r = BudgetAutoscalerReport()
        assert r.id
        assert r.total_records == 0
        assert r.over_budget_count == 0
        assert r.avg_budget_used_pct == 0.0
        assert r.by_scaling_strategy == {}
        assert r.top_over_budget == []
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordScalingEvent:
    def test_basic(self):
        eng = _engine()
        r = eng.record_scaling_event(
            scaling_strategy=ScalingStrategy.COST_OPTIMIZED,
            budget_status=BudgetStatus.OVER_BUDGET,
            scaling_action=ScalingAction.SCALE_DOWN,
            budget_used_pct=105.0,
            resource_count=20,
            cost_impact=-500.0,
            service="api-fleet",
            team="platform",
        )
        assert r.scaling_strategy == ScalingStrategy.COST_OPTIMIZED
        assert r.budget_status == BudgetStatus.OVER_BUDGET
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_scaling_event(scaling_strategy=ScalingStrategy.BALANCED)
        assert len(eng._records) == 3


class TestGetScalingEvent:
    def test_found(self):
        eng = _engine()
        r = eng.record_scaling_event(budget_used_pct=75.0)
        result = eng.get_scaling_event(r.id)
        assert result is not None
        assert result.budget_used_pct == 75.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_scaling_event("nonexistent") is None


class TestListScalingEvents:
    def test_list_all(self):
        eng = _engine()
        eng.record_scaling_event(scaling_strategy=ScalingStrategy.BALANCED)
        eng.record_scaling_event(scaling_strategy=ScalingStrategy.AGGRESSIVE)
        assert len(eng.list_scaling_events()) == 2

    def test_filter_by_strategy(self):
        eng = _engine()
        eng.record_scaling_event(scaling_strategy=ScalingStrategy.BALANCED)
        eng.record_scaling_event(scaling_strategy=ScalingStrategy.CONSERVATIVE)
        results = eng.list_scaling_events(scaling_strategy=ScalingStrategy.BALANCED)
        assert len(results) == 1

    def test_filter_by_budget_status(self):
        eng = _engine()
        eng.record_scaling_event(budget_status=BudgetStatus.UNDER_BUDGET)
        eng.record_scaling_event(budget_status=BudgetStatus.OVER_BUDGET)
        results = eng.list_scaling_events(budget_status=BudgetStatus.UNDER_BUDGET)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_scaling_event(team="platform")
        eng.record_scaling_event(team="data")
        results = eng.list_scaling_events(team="platform")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_scaling_event(scaling_strategy=ScalingStrategy.BALANCED)
        assert len(eng.list_scaling_events(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            scaling_strategy=ScalingStrategy.AGGRESSIVE,
            analysis_score=90.0,
            threshold=80.0,
            breached=True,
            description="over budget scaling triggered",
        )
        assert a.scaling_strategy == ScalingStrategy.AGGRESSIVE
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(scaling_strategy=ScalingStrategy.BALANCED)
        assert len(eng._analyses) == 2


class TestAnalyzeStrategyDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_scaling_event(
            scaling_strategy=ScalingStrategy.COST_OPTIMIZED, budget_used_pct=60.0
        )
        eng.record_scaling_event(
            scaling_strategy=ScalingStrategy.COST_OPTIMIZED, budget_used_pct=80.0
        )
        result = eng.analyze_strategy_distribution()
        assert "cost_optimized" in result
        assert result["cost_optimized"]["count"] == 2
        assert result["cost_optimized"]["avg_budget_used_pct"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_strategy_distribution() == {}


class TestIdentifyOverBudgetEvents:
    def test_detects_over_budget(self):
        eng = _engine()
        eng.record_scaling_event(budget_status=BudgetStatus.OVER_BUDGET)
        eng.record_scaling_event(budget_status=BudgetStatus.UNDER_BUDGET)
        results = eng.identify_over_budget_events()
        assert len(results) == 1

    def test_detects_critical(self):
        eng = _engine()
        eng.record_scaling_event(budget_status=BudgetStatus.CRITICAL)
        results = eng.identify_over_budget_events()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_over_budget_events() == []


class TestRankByBudgetUsage:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_scaling_event(service="api-fleet", budget_used_pct=95.0)
        eng.record_scaling_event(service="batch-fleet", budget_used_pct=45.0)
        results = eng.rank_by_budget_usage()
        assert results[0]["service"] == "api-fleet"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_budget_usage() == []


class TestDetectBudgetTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_budget_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_budget_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_budget_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_scaling_event(
            scaling_strategy=ScalingStrategy.COST_OPTIMIZED,
            budget_status=BudgetStatus.OVER_BUDGET,
            scaling_action=ScalingAction.SCALE_DOWN,
            budget_used_pct=110.0,
        )
        report = eng.generate_report()
        assert isinstance(report, BudgetAutoscalerReport)
        assert report.total_records == 1
        assert report.over_budget_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_scaling_event(scaling_strategy=ScalingStrategy.BALANCED)
        eng.add_analysis(scaling_strategy=ScalingStrategy.BALANCED)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["scaling_strategy_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_scaling_event(
            scaling_strategy=ScalingStrategy.BALANCED,
            service="api-fleet",
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "balanced" in stats["scaling_strategy_distribution"]
