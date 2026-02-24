"""Tests for shieldops.billing.commitment_planner — CloudCommitmentPlanner."""

from __future__ import annotations

from shieldops.billing.commitment_planner import (
    CloudCommitmentPlanner,
    CommitmentPlanReport,
    CommitmentRecommendation,
    PricingModel,
    RecommendationConfidence,
    WorkloadPattern,
    WorkloadProfile,
)


def _engine(**kw) -> CloudCommitmentPlanner:
    return CloudCommitmentPlanner(**kw)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestPricingModel:
    """Test every PricingModel member."""

    def test_on_demand(self):
        assert PricingModel.ON_DEMAND == "on_demand"

    def test_reserved_1yr(self):
        assert PricingModel.RESERVED_1YR == "reserved_1yr"

    def test_reserved_3yr(self):
        assert PricingModel.RESERVED_3YR == "reserved_3yr"

    def test_savings_plan(self):
        assert PricingModel.SAVINGS_PLAN == "savings_plan"

    def test_spot(self):
        assert PricingModel.SPOT == "spot"


class TestWorkloadPattern:
    """Test every WorkloadPattern member."""

    def test_steady_state(self):
        assert WorkloadPattern.STEADY_STATE == "steady_state"

    def test_burst(self):
        assert WorkloadPattern.BURST == "burst"

    def test_cyclic(self):
        assert WorkloadPattern.CYCLIC == "cyclic"

    def test_declining(self):
        assert WorkloadPattern.DECLINING == "declining"

    def test_unpredictable(self):
        assert WorkloadPattern.UNPREDICTABLE == "unpredictable"


class TestRecommendationConfidence:
    """Test every RecommendationConfidence member."""

    def test_high(self):
        assert RecommendationConfidence.HIGH == "high"

    def test_medium(self):
        assert RecommendationConfidence.MEDIUM == "medium"

    def test_low(self):
        assert RecommendationConfidence.LOW == "low"

    def test_speculative(self):
        assert RecommendationConfidence.SPECULATIVE == "speculative"

    def test_insufficient_data(self):
        assert RecommendationConfidence.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test model defaults."""

    def test_workload_profile_defaults(self):
        m = WorkloadProfile()
        assert m.id
        assert m.service_name == ""
        assert m.current_pricing == PricingModel.ON_DEMAND
        assert m.pattern == WorkloadPattern.STEADY_STATE
        assert m.monthly_cost == 0.0
        assert m.avg_utilization_pct == 0.0
        assert m.peak_utilization_pct == 0.0
        assert m.created_at > 0

    def test_commitment_recommendation_defaults(self):
        m = CommitmentRecommendation()
        assert m.id
        assert m.workload_id == ""
        assert m.recommended_pricing == PricingModel.ON_DEMAND
        assert m.confidence == RecommendationConfidence.MEDIUM
        assert m.estimated_savings_pct == 0.0
        assert m.estimated_monthly_savings == 0.0
        assert m.rationale == ""

    def test_commitment_plan_report_defaults(self):
        m = CommitmentPlanReport()
        assert m.total_workloads == 0
        assert m.total_monthly_cost == 0.0
        assert m.potential_savings == 0.0
        assert m.savings_pct == 0.0
        assert m.by_pricing == {}
        assert m.by_pattern == {}
        assert m.recommendations_count == 0
        assert m.recommendations == []


# ---------------------------------------------------------------------------
# register_workload
# ---------------------------------------------------------------------------


class TestRegisterWorkload:
    """Test CloudCommitmentPlanner.register_workload."""

    def test_basic_registration(self):
        eng = _engine()
        wl = eng.register_workload(
            service_name="api-server",
            current_pricing=PricingModel.ON_DEMAND,
            pattern=WorkloadPattern.STEADY_STATE,
            monthly_cost=1000.0,
            avg_utilization_pct=85.0,
            peak_utilization_pct=90.0,
        )
        assert wl.service_name == "api-server"
        assert wl.monthly_cost == 1000.0
        assert wl.avg_utilization_pct == 85.0
        assert eng.get_workload(wl.id) is wl

    def test_eviction_on_overflow(self):
        eng = _engine(max_workloads=2)
        w1 = eng.register_workload(service_name="svc-1")
        eng.register_workload(service_name="svc-2")
        eng.register_workload(service_name="svc-3")
        assert eng.get_workload(w1.id) is None
        assert len(eng.list_workloads()) == 2


# ---------------------------------------------------------------------------
# get_workload
# ---------------------------------------------------------------------------


class TestGetWorkload:
    """Test CloudCommitmentPlanner.get_workload."""

    def test_found(self):
        eng = _engine()
        wl = eng.register_workload(service_name="db")
        assert eng.get_workload(wl.id) is wl

    def test_not_found(self):
        eng = _engine()
        assert eng.get_workload("nonexistent") is None


# ---------------------------------------------------------------------------
# list_workloads
# ---------------------------------------------------------------------------


class TestListWorkloads:
    """Test CloudCommitmentPlanner.list_workloads."""

    def test_all(self):
        eng = _engine()
        eng.register_workload(service_name="a")
        eng.register_workload(service_name="b")
        assert len(eng.list_workloads()) == 2

    def test_filter_by_pattern(self):
        eng = _engine()
        eng.register_workload(pattern=WorkloadPattern.BURST)
        eng.register_workload(pattern=WorkloadPattern.CYCLIC)
        eng.register_workload(pattern=WorkloadPattern.BURST)
        result = eng.list_workloads(pattern=WorkloadPattern.BURST)
        assert len(result) == 2

    def test_filter_by_pricing(self):
        eng = _engine()
        eng.register_workload(current_pricing=PricingModel.SPOT)
        eng.register_workload(current_pricing=PricingModel.ON_DEMAND)
        result = eng.list_workloads(current_pricing=PricingModel.SPOT)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# recommend_pricing_model
# ---------------------------------------------------------------------------


class TestRecommendPricingModel:
    """Test CloudCommitmentPlanner.recommend_pricing_model."""

    def test_steady_state_high_util_recommends_reserved_3yr(self):
        eng = _engine()
        wl = eng.register_workload(
            pattern=WorkloadPattern.STEADY_STATE,
            avg_utilization_pct=85.0,
            monthly_cost=1000.0,
        )
        rec = eng.recommend_pricing_model(wl.id)
        assert rec is not None
        assert rec.recommended_pricing == PricingModel.RESERVED_3YR
        assert rec.confidence == RecommendationConfidence.HIGH
        assert rec.estimated_savings_pct == 40.0
        assert rec.estimated_monthly_savings == 400.0

    def test_burst_recommends_spot(self):
        eng = _engine()
        wl = eng.register_workload(
            pattern=WorkloadPattern.BURST,
            monthly_cost=500.0,
        )
        rec = eng.recommend_pricing_model(wl.id)
        assert rec is not None
        assert rec.recommended_pricing == PricingModel.SPOT
        assert rec.confidence == RecommendationConfidence.MEDIUM

    def test_cyclic_recommends_savings_plan(self):
        eng = _engine()
        wl = eng.register_workload(pattern=WorkloadPattern.CYCLIC, monthly_cost=800.0)
        rec = eng.recommend_pricing_model(wl.id)
        assert rec is not None
        assert rec.recommended_pricing == PricingModel.SAVINGS_PLAN

    def test_declining_recommends_on_demand(self):
        eng = _engine()
        wl = eng.register_workload(pattern=WorkloadPattern.DECLINING, monthly_cost=200.0)
        rec = eng.recommend_pricing_model(wl.id)
        assert rec is not None
        assert rec.recommended_pricing == PricingModel.ON_DEMAND
        assert rec.confidence == RecommendationConfidence.LOW

    def test_not_found_returns_none(self):
        eng = _engine()
        assert eng.recommend_pricing_model("missing") is None


# ---------------------------------------------------------------------------
# calculate_optimal_mix
# ---------------------------------------------------------------------------


class TestCalculateOptimalMix:
    """Test CloudCommitmentPlanner.calculate_optimal_mix."""

    def test_basic_with_multiple_workloads(self):
        eng = _engine()
        eng.register_workload(
            pattern=WorkloadPattern.STEADY_STATE,
            avg_utilization_pct=90.0,
            monthly_cost=1000.0,
        )
        eng.register_workload(
            pattern=WorkloadPattern.BURST,
            monthly_cost=500.0,
        )
        result = eng.calculate_optimal_mix()
        assert result["total_workloads"] == 2
        assert "optimal_mix" in result
        assert result["total_potential_savings"] > 0


# ---------------------------------------------------------------------------
# estimate_savings
# ---------------------------------------------------------------------------


class TestEstimateSavings:
    """Test CloudCommitmentPlanner.estimate_savings."""

    def test_basic(self):
        eng = _engine()
        wl = eng.register_workload(
            pattern=WorkloadPattern.STEADY_STATE,
            avg_utilization_pct=85.0,
            monthly_cost=1000.0,
        )
        result = eng.estimate_savings(wl.id)
        assert result["workload_id"] == wl.id
        assert result["current_cost"] == 1000.0
        assert result["estimated_savings_pct"] == 40.0
        assert result["estimated_monthly_savings"] == 400.0

    def test_not_found_returns_zero_savings(self):
        eng = _engine()
        result = eng.estimate_savings("nonexistent")
        assert result["current_cost"] == 0.0
        assert result["estimated_monthly_savings"] == 0.0


# ---------------------------------------------------------------------------
# detect_workload_pattern
# ---------------------------------------------------------------------------


class TestDetectWorkloadPattern:
    """Test CloudCommitmentPlanner.detect_workload_pattern."""

    def test_steady_state_high_avg_low_spread(self):
        eng = _engine()
        wl = eng.register_workload(avg_utilization_pct=85.0, peak_utilization_pct=90.0)
        result = eng.detect_workload_pattern(wl.id)
        assert result["detected_pattern"] == "steady_state"
        assert result["confidence"] == "high"

    def test_burst_high_peak_low_avg(self):
        eng = _engine()
        wl = eng.register_workload(avg_utilization_pct=30.0, peak_utilization_pct=95.0)
        result = eng.detect_workload_pattern(wl.id)
        assert result["detected_pattern"] == "burst"
        assert result["confidence"] == "high"

    def test_not_found_returns_unpredictable(self):
        eng = _engine()
        result = eng.detect_workload_pattern("missing")
        assert result["detected_pattern"] == "unpredictable"
        assert result["confidence"] == "insufficient_data"


# ---------------------------------------------------------------------------
# compare_commitment_scenarios
# ---------------------------------------------------------------------------


class TestCompareCommitmentScenarios:
    """Test CloudCommitmentPlanner.compare_commitment_scenarios."""

    def test_basic(self):
        eng = _engine()
        wl = eng.register_workload(monthly_cost=1000.0)
        scenarios = eng.compare_commitment_scenarios(wl.id)
        assert len(scenarios) == len(PricingModel)
        on_demand = next(s for s in scenarios if s["pricing_model"] == "on_demand")
        assert on_demand["monthly_cost"] == 1000.0
        assert on_demand["savings_pct"] == 0.0
        spot = next(s for s in scenarios if s["pricing_model"] == "spot")
        assert spot["monthly_cost"] == 400.0
        assert spot["savings_pct"] == 60.0

    def test_not_found_returns_empty(self):
        eng = _engine()
        assert eng.compare_commitment_scenarios("missing") == []


# ---------------------------------------------------------------------------
# generate_plan_report
# ---------------------------------------------------------------------------


class TestGeneratePlanReport:
    """Test CloudCommitmentPlanner.generate_plan_report."""

    def test_basic_report_with_data(self):
        eng = _engine()
        eng.register_workload(
            pattern=WorkloadPattern.STEADY_STATE,
            avg_utilization_pct=90.0,
            monthly_cost=1000.0,
        )
        eng.calculate_optimal_mix()
        report = eng.generate_plan_report()
        assert isinstance(report, CommitmentPlanReport)
        assert report.total_workloads == 1
        assert report.total_monthly_cost == 1000.0
        assert report.potential_savings > 0
        assert report.recommendations_count >= 1
        assert len(report.recommendations) >= 1


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    """Test CloudCommitmentPlanner.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        eng.register_workload(service_name="svc")
        eng.calculate_optimal_mix()
        eng.clear_data()
        assert eng.list_workloads() == []
        stats = eng.get_stats()
        assert stats["total_workloads"] == 0
        assert stats["total_recommendations"] == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    """Test CloudCommitmentPlanner.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_workloads"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["pricing_distribution"] == {}
        assert stats["pattern_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.register_workload(
            pattern=WorkloadPattern.BURST,
            current_pricing=PricingModel.SPOT,
        )
        eng.register_workload(
            pattern=WorkloadPattern.BURST,
            current_pricing=PricingModel.ON_DEMAND,
        )
        stats = eng.get_stats()
        assert stats["total_workloads"] == 2
        assert stats["pattern_distribution"]["burst"] == 2
        assert stats["pricing_distribution"]["spot"] == 1
        assert stats["pricing_distribution"]["on_demand"] == 1
