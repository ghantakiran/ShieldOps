"""Tests for ErrorBudgetBurnIntelligence."""

from __future__ import annotations

from shieldops.sla.error_budget_burn_intelligence import (
    BudgetStatus,
    BurnCause,
    BurnRate,
    ErrorBudgetBurnIntelligence,
)


def _engine(**kw) -> ErrorBudgetBurnIntelligence:
    return ErrorBudgetBurnIntelligence(**kw)


class TestEnums:
    def test_burn_rate_values(self):
        for v in BurnRate:
            assert isinstance(v.value, str)

    def test_budget_status_values(self):
        for v in BudgetStatus:
            assert isinstance(v.value, str)

    def test_burn_cause_values(self):
        for v in BurnCause:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(service_id="s1")
        assert r.service_id == "s1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(service_id=f"s-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.add_record(
            service_id="s1",
            burn_rate=BurnRate.FAST,
            budget_status=BudgetStatus.CRITICAL,
            budget_total=100.0,
            budget_consumed=80.0,
        )
        assert r.budget_consumed == 80.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(service_id="s1", budget_total=100.0, budget_consumed=30.0)
        a = eng.process(r.id)
        assert hasattr(a, "service_id")
        assert a.service_id == "s1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_accelerated_burn(self):
        eng = _engine()
        r = eng.add_record(service_id="s1", burn_rate=BurnRate.FAST)
        a = eng.process(r.id)
        assert a.accelerated is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeBurnRateTrajectory:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(service_id="s1", burn_velocity=5.0)
        result = eng.compute_burn_rate_trajectory()
        assert len(result) == 1
        assert result[0]["service_id"] == "s1"

    def test_empty(self):
        assert _engine().compute_burn_rate_trajectory() == []


class TestDetectAcceleratedBurn:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            service_id="s1",
            burn_rate=BurnRate.FAST,
            burn_velocity=10.0,
            budget_total=100.0,
            budget_consumed=80.0,
        )
        result = eng.detect_accelerated_burn()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_accelerated_burn() == []


class TestRankServicesByBudgetRemaining:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(service_id="s1", budget_total=100.0, budget_consumed=80.0)
        eng.add_record(service_id="s2", budget_total=100.0, budget_consumed=20.0)
        result = eng.rank_services_by_budget_remaining()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_services_by_budget_remaining() == []
