"""Tests for ServiceLevelIntelligence."""

from __future__ import annotations

from shieldops.observability.service_level_intelligence import (
    ErrorBudgetStatus,
    ReliabilityTrend,
    ServiceLevelIntelligence,
    SloMaturity,
)


def _engine(**kw) -> ServiceLevelIntelligence:
    return ServiceLevelIntelligence(**kw)


class TestEnums:
    def test_slo_maturity(self):
        assert SloMaturity.ADHOC == "adhoc"
        assert SloMaturity.OPTIMIZED == "optimized"

    def test_error_budget_status(self):
        assert ErrorBudgetStatus.HEALTHY == "healthy"
        assert ErrorBudgetStatus.EXHAUSTED == "exhausted"

    def test_reliability_trend(self):
        assert ReliabilityTrend.IMPROVING == "improving"
        assert ReliabilityTrend.VOLATILE == "volatile"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="slo-1", service="api")
        assert rec.name == "slo-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"s-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="slo-1", score=88.0)
        result = eng.process("slo-1")
        assert result["key"] == "slo-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(name="s1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

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
        eng.add_record(name="s1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(name="s1", service="api")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestComputeErrorBudgetVelocity:
    def test_basic(self):
        eng = _engine()
        eng.add_record(name="s1", service="api", burn_rate=1.5)
        result = eng.compute_error_budget_velocity()
        assert isinstance(result, dict)
        assert "api" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_error_budget_velocity()
        assert result["status"] == "no_data"


class TestPredictBudgetExhaustion:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            service="api",
            burn_rate=0.5,
            error_budget_remaining=50.0,
        )
        result = eng.predict_budget_exhaustion()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_no_risk(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            service="api",
            burn_rate=0.001,
            error_budget_remaining=100.0,
        )
        result = eng.predict_budget_exhaustion()
        assert isinstance(result, list)


class TestRecommendSloAdjustments:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            service="api",
            error_budget_remaining=10.0,
            burn_rate=3.0,
        )
        result = eng.recommend_slo_adjustments()
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "suggestion" in result[0]
