"""Tests for shieldops.operations.capacity_intelligence_engine — CapacityIntelligenceEngine."""

from __future__ import annotations

from shieldops.operations.capacity_intelligence_engine import (
    CapacityIntelligenceEngine,
    CapacityRisk,
    ResourceType,
    SizingAction,
)


def _engine(**kw) -> CapacityIntelligenceEngine:
    return CapacityIntelligenceEngine(**kw)


class TestEnums:
    def test_resource_type(self):
        assert ResourceType.CPU == "cpu"

    def test_sizing_action(self):
        assert SizingAction.DOWNSIZE == "downsize"

    def test_capacity_risk(self):
        assert CapacityRisk.HEALTHY == "healthy"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(
            name="api-cpu", resource_type=ResourceType.CPU, current_utilization_pct=75.0
        )
        assert rec.name == "api-cpu"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"r-{i}", resource_type=ResourceType.MEMORY)
        assert len(eng._records) == 3


class TestRightSizing:
    def test_basic(self):
        eng = _engine()
        eng.record_item(
            name="r-1",
            resource_type=ResourceType.CPU,
            current_utilization_pct=20.0,
            allocated_units=100.0,
        )
        result = eng.recommend_right_sizing()
        assert isinstance(result, list)


class TestExhaustion:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="r-1", projected_exhaustion_days=30)
        result = eng.predict_exhaustion()
        assert isinstance(result, list)


class TestCostEfficiency:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="r-1", monthly_cost=500.0, current_utilization_pct=80.0)
        result = eng.calculate_cost_efficiency()
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="r-1", resource_type=ResourceType.CPU)
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="r-1", resource_type=ResourceType.CPU)
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="r-1", resource_type=ResourceType.CPU)
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
