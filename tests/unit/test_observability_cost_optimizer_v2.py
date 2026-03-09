"""Tests for shieldops.billing.observability_cost_optimizer_v2 — ObservabilityCostOptimizerV2."""

from __future__ import annotations

from shieldops.billing.observability_cost_optimizer_v2 import (
    CostCategory,
    CostRecord,
    CostReport,
    CostTrend,
    ObservabilityCostOptimizerV2,
    OptimizationRecommendation,
    OptimizationType,
)


def _engine(**kw) -> ObservabilityCostOptimizerV2:
    return ObservabilityCostOptimizerV2(**kw)


class TestEnums:
    def test_category_metrics(self):
        assert CostCategory.METRICS == "metrics"

    def test_category_logs(self):
        assert CostCategory.LOGS == "logs"

    def test_category_traces(self):
        assert CostCategory.TRACES == "traces"

    def test_category_storage(self):
        assert CostCategory.STORAGE == "storage"

    def test_category_compute(self):
        assert CostCategory.COMPUTE == "compute"

    def test_category_egress(self):
        assert CostCategory.EGRESS == "egress"

    def test_opt_downsampling(self):
        assert OptimizationType.DOWNSAMPLING == "downsampling"

    def test_opt_tier_migration(self):
        assert OptimizationType.TIER_MIGRATION == "tier_migration"

    def test_opt_deduplication(self):
        assert OptimizationType.DEDUPLICATION == "deduplication"

    def test_trend_increasing(self):
        assert CostTrend.INCREASING == "increasing"

    def test_trend_stable(self):
        assert CostTrend.STABLE == "stable"

    def test_trend_decreasing(self):
        assert CostTrend.DECREASING == "decreasing"


class TestModels:
    def test_cost_record_defaults(self):
        r = CostRecord()
        assert r.id
        assert r.category == CostCategory.METRICS
        assert r.cost_usd == 0.0

    def test_recommendation_defaults(self):
        r = OptimizationRecommendation()
        assert r.id
        assert r.applied is False

    def test_report_defaults(self):
        r = CostReport()
        assert r.total_cost_usd == 0.0
        assert r.cost_trend == CostTrend.STABLE


class TestAddCost:
    def test_basic(self):
        eng = _engine()
        c = eng.add_cost(CostCategory.METRICS, "api-svc", 150.0)
        assert c.category == CostCategory.METRICS
        assert c.cost_usd == 150.0

    def test_with_volume(self):
        eng = _engine()
        c = eng.add_cost(CostCategory.LOGS, "svc", 50.0, volume_units=1000000)
        assert c.volume_units == 1000000

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_cost(CostCategory.METRICS, "svc", float(i))
        assert len(eng._costs) == 3


class TestAnalyzeCosts:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_costs()
        assert result["total_cost_usd"] == 0

    def test_by_category(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "svc", 100.0)
        eng.add_cost(CostCategory.LOGS, "svc", 200.0)
        result = eng.analyze_costs()
        assert result["by_category"]["metrics"] == 100.0
        assert result["top_category"] == "logs"

    def test_filter_by_service(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "api", 100.0)
        eng.add_cost(CostCategory.METRICS, "web", 200.0)
        result = eng.analyze_costs(service="api")
        assert result["total_cost_usd"] == 100.0


class TestRecommendOptimizations:
    def test_low_cost_no_action(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "svc", 10.0)
        recs = eng.recommend_optimizations()
        assert len(recs) >= 1

    def test_high_cost_recommendations(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "svc", 200.0)
        recs = eng.recommend_optimizations()
        types = [r.opt_type for r in recs]
        assert OptimizationType.DOWNSAMPLING in types

    def test_very_high_cost(self):
        eng = _engine()
        eng.add_cost(CostCategory.LOGS, "svc", 1000.0)
        recs = eng.recommend_optimizations()
        types = [r.opt_type for r in recs]
        assert OptimizationType.TIER_MIGRATION in types

    def test_filter_by_service(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "api", 200.0)
        eng.add_cost(CostCategory.METRICS, "web", 10.0)
        recs = eng.recommend_optimizations(service="api")
        assert all(r.service == "api" for r in recs)


class TestEstimateSavings:
    def test_empty(self):
        eng = _engine()
        result = eng.estimate_savings()
        assert result["total_potential_savings_usd"] == 0

    def test_with_recommendations(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "svc", 500.0)
        eng.recommend_optimizations()
        result = eng.estimate_savings()
        assert result["total_potential_savings_usd"] > 0
        assert result["savings_pct"] > 0


class TestApplyOptimization:
    def test_not_found(self):
        eng = _engine()
        result = eng.apply_optimization("nonexistent")
        assert result["status"] == "not_found"

    def test_apply_success(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "svc", 500.0)
        recs = eng.recommend_optimizations()
        result = eng.apply_optimization(recs[0].id)
        assert result["status"] == "applied"
        assert recs[0].applied is True


class TestGetCostBreakdown:
    def test_by_category(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "svc", 100.0)
        eng.add_cost(CostCategory.LOGS, "svc", 200.0)
        result = eng.get_cost_breakdown(group_by="category")
        assert result["breakdown"]["metrics"] == 100.0

    def test_by_service(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "api", 100.0)
        eng.add_cost(CostCategory.METRICS, "web", 50.0)
        result = eng.get_cost_breakdown(group_by="service")
        assert result["breakdown"]["api"] == 100.0

    def test_empty(self):
        eng = _engine()
        result = eng.get_cost_breakdown()
        assert result["total_usd"] == 0


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_cost_usd == 0.0

    def test_with_data(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "svc", 500.0)
        eng.recommend_optimizations()
        report = eng.generate_report()
        assert report.total_cost_usd == 500.0
        assert report.potential_savings_usd > 0

    def test_increasing_trend(self):
        eng = _engine()
        for i in range(10):
            eng.add_cost(CostCategory.METRICS, "svc", float(i * 100))
        report = eng.generate_report()
        assert report.cost_trend in (CostTrend.INCREASING, CostTrend.STABLE)


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "svc", 100.0)
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._costs) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_costs"] == 0

    def test_populated(self):
        eng = _engine()
        eng.add_cost(CostCategory.METRICS, "api", 100.0)
        stats = eng.get_stats()
        assert stats["unique_services"] == 1
