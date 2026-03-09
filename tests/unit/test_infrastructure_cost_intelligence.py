"""Tests for InfrastructureCostIntelligence."""

from __future__ import annotations

from shieldops.analytics.infrastructure_cost_intelligence import (
    CostCategory,
    InfrastructureCostIntelligence,
    OptimizationPriority,
    WasteType,
)


def _engine(**kw) -> InfrastructureCostIntelligence:
    return InfrastructureCostIntelligence(**kw)


class TestEnums:
    def test_cost_category(self):
        assert CostCategory.COMPUTE == "compute"

    def test_waste_type(self):
        assert WasteType.IDLE_RESOURCE == "idle_resource"

    def test_optimization_priority(self):
        assert OptimizationPriority.HIGH == "high"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(
            name="api-compute", cost_category=CostCategory.COMPUTE, monthly_cost=5000.0
        )
        assert rec.name == "api-compute"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"cost-{i}")
        assert len(eng._records) == 3


class TestCostAttribution:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="c1", team="platform", monthly_cost=5000.0)
        result = eng.attribute_costs()
        assert isinstance(result, dict)


class TestDetectWaste:
    def test_basic(self):
        eng = _engine()
        eng.record_item(
            name="c1",
            waste_type=WasteType.IDLE_RESOURCE,
            utilization_pct=5.0,
            potential_savings=100.0,
        )
        result = eng.detect_waste()
        assert isinstance(result, list)


class TestCostTrend:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="c1", monthly_cost=5000.0)
        result = eng.forecast_cost_trend()
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="c1", monthly_cost=1000.0)
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="c1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="c1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
