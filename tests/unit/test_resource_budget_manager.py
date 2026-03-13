"""Tests for ResourceBudgetManager."""

from __future__ import annotations

from shieldops.operations.resource_budget_manager import (
    AllocationStrategy,
    BudgetStatus,
    ResourceBudgetManager,
    ResourceType,
)


def _engine(**kw) -> ResourceBudgetManager:
    return ResourceBudgetManager(**kw)


class TestEnums:
    def test_resource_type_values(self):
        assert isinstance(ResourceType.GPU, str)
        assert isinstance(ResourceType.CPU, str)
        assert isinstance(ResourceType.MEMORY, str)
        assert isinstance(ResourceType.STORAGE, str)

    def test_allocation_strategy_values(self):
        assert isinstance(AllocationStrategy.FIXED, str)
        assert isinstance(AllocationStrategy.ELASTIC, str)
        assert isinstance(AllocationStrategy.PRIORITY, str)
        assert isinstance(AllocationStrategy.FAIR_SHARE, str)

    def test_budget_status_values(self):
        assert isinstance(BudgetStatus.UNDER_BUDGET, str)
        assert isinstance(BudgetStatus.AT_LIMIT, str)
        assert isinstance(BudgetStatus.OVER_BUDGET, str)
        assert isinstance(BudgetStatus.EXHAUSTED, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="budget-001",
            resource_type=ResourceType.GPU,
            allocated=100.0,
            consumed=50.0,
        )
        assert r.name == "budget-001"
        assert r.allocated == 100.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(name=f"b-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="b1", allocated=100.0, consumed=50.0)
        result = eng.process(r.id)
        assert "analysis_id" in result

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="b1")
        report = eng.generate_report()
        assert report.total_records > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        assert "total_records" in eng.get_stats()

    def test_populated_count(self):
        eng = _engine()
        eng.record_item(name="b1")
        eng.record_item(name="b2")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(name="b1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAllocateExperimentBudget:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="b1", allocated=100.0, consumed=40.0)
        result = eng.allocate_experiment_budget("b1")
        assert result["remaining"] == 60.0

    def test_empty(self):
        eng = _engine()
        result = eng.allocate_experiment_budget("b1")
        assert result["status"] == "no_data"


class TestComputeUtilizationEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="b1", allocated=100.0, consumed=80.0)
        result = eng.compute_utilization_efficiency("b1")
        assert result["efficiency"] == 0.8

    def test_empty(self):
        eng = _engine()
        result = eng.compute_utilization_efficiency("b1")
        assert result["status"] == "no_data"


class TestForecastBudgetExhaustion:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="b1", allocated=100.0, consumed=95.0)
        result = eng.forecast_budget_exhaustion("b1")
        assert result["risk"] == "high"

    def test_empty(self):
        eng = _engine()
        result = eng.forecast_budget_exhaustion("b1")
        assert result["status"] == "no_data"
