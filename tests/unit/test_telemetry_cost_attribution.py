"""Tests for TelemetryCostAttribution."""

from __future__ import annotations

from shieldops.billing.telemetry_cost_attribution import (
    AttributionMethod,
    CostDriver,
    CostTrend,
    TelemetryCostAttribution,
)


def _engine(**kw) -> TelemetryCostAttribution:
    return TelemetryCostAttribution(**kw)


class TestEnums:
    def test_cost_driver_values(self):
        for v in CostDriver:
            assert isinstance(v.value, str)

    def test_attribution_method_values(self):
        for v in AttributionMethod:
            assert isinstance(v.value, str)

    def test_cost_trend_values(self):
        for v in CostTrend:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(name="test-001", score=80.0)
        assert r.name == "test-001"
        assert r.score == 80.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(name=f"item-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(name="test", score=40.0)
        result = eng.process(r.id)
        assert result["status"] == "processed"

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=50.0)
        report = eng.generate_report()
        assert report.total_records > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated_count(self):
        eng = _engine()
        eng.add_record(name="a")
        eng.add_record(name="b")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(name="a")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAttributeTelemetryCosts:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            cost_driver=CostDriver.INGESTION_VOLUME,
            score=90.0,
        )
        result = eng.attribute_telemetry_costs()
        assert "ingestion_volume" in result

    def test_empty(self):
        eng = _engine()
        assert eng.attribute_telemetry_costs() == {}


class TestIdentifyCostHotspots:
    def test_with_data(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=30.0)
        result = eng.identify_cost_hotspots()
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_cost_hotspots() == []


class TestRecommendCostReduction:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(name="a", service="svc-a", score=30.0)
        result = eng.recommend_cost_reduction()
        assert len(result) > 0

    def test_empty(self):
        eng = _engine()
        assert eng.recommend_cost_reduction() == []
