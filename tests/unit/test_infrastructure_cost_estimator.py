"""Tests for InfrastructureCostEstimator."""

from __future__ import annotations

from shieldops.billing.infrastructure_cost_estimator import (
    CostImpact,
    EstimationConfidence,
    InfrastructureCostEstimator,
    PricingModel,
)


def _engine(**kw) -> InfrastructureCostEstimator:
    return InfrastructureCostEstimator(**kw)


class TestEnums:
    def test_cost_impact_values(self):
        for v in CostImpact:
            assert isinstance(v.value, str)

    def test_estimation_confidence_values(self):
        for v in EstimationConfidence:
            assert isinstance(v.value, str)

    def test_pricing_model_values(self):
        for v in PricingModel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(change_id="c1")
        assert r.change_id == "c1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(change_id=f"c-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            change_id="c1",
            cost_delta=150.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "change_id")
        assert a.is_surprise is True

    def test_not_surprise(self):
        eng = _engine()
        r = eng.add_record(
            change_id="c1",
            cost_delta=50.0,
        )
        a = eng.process(r.id)
        assert a.is_surprise is False

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(change_id="c1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(change_id="c1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(change_id="c1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestEstimatePlanCostImpact:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            change_id="c1",
            estimated_monthly_cost=500.0,
            cost_delta=200.0,
        )
        result = eng.estimate_plan_cost_impact()
        assert len(result) == 1
        assert result[0]["total_delta"] == 200.0

    def test_empty(self):
        r = _engine().estimate_plan_cost_impact()
        assert r == []


class TestDetectCostSurprises:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            change_id="c1",
            cost_delta=500.0,
        )
        result = eng.detect_cost_surprises()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().detect_cost_surprises()
        assert r == []


class TestRankChangesByCostDelta:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(change_id="c1", cost_delta=100.0)
        eng.add_record(change_id="c2", cost_delta=300.0)
        result = eng.rank_changes_by_cost_delta()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_changes_by_cost_delta()
        assert r == []
