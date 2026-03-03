"""Tests for shieldops.billing.cost_aware_scaling_optimizer — CostAwareScalingOptimizer."""

from __future__ import annotations

from shieldops.billing.cost_aware_scaling_optimizer import (
    CostAwareScalingOptimizer,
    CostAwareScalingReport,
    CostScalingAnalysis,
    CostScalingRecord,
    CostSignal,
    OptimizationResult,
    ScalingMode,
)


def _engine(**kw) -> CostAwareScalingOptimizer:
    return CostAwareScalingOptimizer(**kw)


class TestEnums:
    def test_scaling_mode_performance_first(self):
        assert ScalingMode.PERFORMANCE_FIRST == "performance_first"

    def test_scaling_mode_cost_first(self):
        assert ScalingMode.COST_FIRST == "cost_first"

    def test_scaling_mode_balanced(self):
        assert ScalingMode.BALANCED == "balanced"

    def test_scaling_mode_peak_handling(self):
        assert ScalingMode.PEAK_HANDLING == "peak_handling"

    def test_scaling_mode_minimum(self):
        assert ScalingMode.MINIMUM == "minimum"

    def test_cost_signal_spot_price(self):
        assert CostSignal.SPOT_PRICE == "spot_price"

    def test_cost_signal_ri_utilization(self):
        assert CostSignal.RI_UTILIZATION == "ri_utilization"

    def test_cost_signal_on_demand_spend(self):
        assert CostSignal.ON_DEMAND_SPEND == "on_demand_spend"

    def test_cost_signal_savings_plan(self):
        assert CostSignal.SAVINGS_PLAN == "savings_plan"

    def test_cost_signal_budget_remaining(self):
        assert CostSignal.BUDGET_REMAINING == "budget_remaining"

    def test_optimization_result_savings_achieved(self):
        assert OptimizationResult.SAVINGS_ACHIEVED == "savings_achieved"

    def test_optimization_result_performance_maintained(self):
        assert OptimizationResult.PERFORMANCE_MAINTAINED == "performance_maintained"

    def test_optimization_result_trade_off(self):
        assert OptimizationResult.TRADE_OFF == "trade_off"

    def test_optimization_result_no_change(self):
        assert OptimizationResult.NO_CHANGE == "no_change"

    def test_optimization_result_reverted(self):
        assert OptimizationResult.REVERTED == "reverted"


class TestModels:
    def test_record_defaults(self):
        r = CostScalingRecord()
        assert r.id
        assert r.name == ""
        assert r.scaling_mode == ScalingMode.PERFORMANCE_FIRST
        assert r.cost_signal == CostSignal.SPOT_PRICE
        assert r.optimization_result == OptimizationResult.REVERTED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = CostScalingAnalysis()
        assert a.id
        assert a.name == ""
        assert a.scaling_mode == ScalingMode.PERFORMANCE_FIRST
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = CostAwareScalingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_scaling_mode == {}
        assert r.by_cost_signal == {}
        assert r.by_optimization_result == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            scaling_mode=ScalingMode.PERFORMANCE_FIRST,
            cost_signal=CostSignal.RI_UTILIZATION,
            optimization_result=OptimizationResult.SAVINGS_ACHIEVED,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.scaling_mode == ScalingMode.PERFORMANCE_FIRST
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

    def test_filter_by_scaling_mode(self):
        eng = _engine()
        eng.record_entry(name="a", scaling_mode=ScalingMode.PERFORMANCE_FIRST)
        eng.record_entry(name="b", scaling_mode=ScalingMode.COST_FIRST)
        assert len(eng.list_records(scaling_mode=ScalingMode.PERFORMANCE_FIRST)) == 1

    def test_filter_by_cost_signal(self):
        eng = _engine()
        eng.record_entry(name="a", cost_signal=CostSignal.SPOT_PRICE)
        eng.record_entry(name="b", cost_signal=CostSignal.RI_UTILIZATION)
        assert len(eng.list_records(cost_signal=CostSignal.SPOT_PRICE)) == 1

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
        eng.record_entry(name="a", scaling_mode=ScalingMode.COST_FIRST, score=90.0)
        eng.record_entry(name="b", scaling_mode=ScalingMode.COST_FIRST, score=70.0)
        result = eng.analyze_distribution()
        assert "cost_first" in result
        assert result["cost_first"]["count"] == 2

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
