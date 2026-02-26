"""Tests for shieldops.analytics.capacity_demand — CapacityDemandModeler."""

from __future__ import annotations

from shieldops.analytics.capacity_demand import (
    CapacityDemandModeler,
    CapacityDemandReport,
    DemandPattern,
    DemandRecord,
    ResourceType,
    SupplyGap,
    SupplyStatus,
)


def _engine(**kw) -> CapacityDemandModeler:
    return CapacityDemandModeler(**kw)


class TestEnums:
    def test_pattern_steady(self):
        assert DemandPattern.STEADY == "steady"

    def test_pattern_cyclical(self):
        assert DemandPattern.CYCLICAL == "cyclical"

    def test_pattern_growing(self):
        assert DemandPattern.GROWING == "growing"

    def test_pattern_declining(self):
        assert DemandPattern.DECLINING == "declining"

    def test_pattern_spiky(self):
        assert DemandPattern.SPIKY == "spiky"

    def test_resource_compute(self):
        assert ResourceType.COMPUTE == "compute"

    def test_resource_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_resource_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_resource_network(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_gpu(self):
        assert ResourceType.GPU == "gpu"

    def test_status_surplus(self):
        assert SupplyStatus.SURPLUS == "surplus"

    def test_status_balanced(self):
        assert SupplyStatus.BALANCED == "balanced"

    def test_status_tight(self):
        assert SupplyStatus.TIGHT == "tight"

    def test_status_deficit(self):
        assert SupplyStatus.DEFICIT == "deficit"

    def test_status_critical(self):
        assert SupplyStatus.CRITICAL == "critical"


class TestModels:
    def test_demand_record_defaults(self):
        r = DemandRecord()
        assert r.id
        assert r.service_name == ""
        assert r.resource_type == ResourceType.COMPUTE
        assert r.demand_pattern == DemandPattern.STEADY
        assert r.current_usage_pct == 0.0
        assert r.peak_usage_pct == 0.0
        assert r.supply_status == SupplyStatus.BALANCED
        assert r.details == ""
        assert r.created_at > 0

    def test_supply_gap_defaults(self):
        r = SupplyGap()
        assert r.id
        assert r.service_name == ""
        assert r.resource_type == ResourceType.COMPUTE
        assert r.gap_pct == 0.0
        assert r.projected_deficit_date == ""
        assert r.mitigation == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = CapacityDemandReport()
        assert r.total_demands == 0
        assert r.total_supply_gaps == 0
        assert r.avg_usage_pct == 0.0
        assert r.by_resource_type == {}
        assert r.by_supply_status == {}
        assert r.deficit_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordDemand:
    def test_basic(self):
        eng = _engine()
        r = eng.record_demand("svc-a", current_usage_pct=96.0)
        assert r.service_name == "svc-a"
        assert r.supply_status == SupplyStatus.CRITICAL

    def test_auto_status_balanced(self):
        eng = _engine()
        r = eng.record_demand("svc-b", current_usage_pct=50.0)
        assert r.supply_status == SupplyStatus.BALANCED

    def test_explicit_status(self):
        eng = _engine()
        r = eng.record_demand("svc-c", supply_status=SupplyStatus.SURPLUS)
        assert r.supply_status == SupplyStatus.SURPLUS

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_demand(f"svc-{i}")
        assert len(eng._records) == 3


class TestGetDemand:
    def test_found(self):
        eng = _engine()
        r = eng.record_demand("svc-a")
        assert eng.get_demand(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_demand("nonexistent") is None


class TestListDemands:
    def test_list_all(self):
        eng = _engine()
        eng.record_demand("svc-a")
        eng.record_demand("svc-b")
        assert len(eng.list_demands()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_demand("svc-a")
        eng.record_demand("svc-b")
        results = eng.list_demands(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_resource(self):
        eng = _engine()
        eng.record_demand("svc-a", resource_type=ResourceType.GPU)
        eng.record_demand("svc-b", resource_type=ResourceType.COMPUTE)
        results = eng.list_demands(resource_type=ResourceType.GPU)
        assert len(results) == 1


class TestRecordSupplyGap:
    def test_basic(self):
        eng = _engine()
        g = eng.record_supply_gap("svc-a", gap_pct=15.0)
        assert g.service_name == "svc-a"
        assert g.gap_pct == 15.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_supply_gap(f"svc-{i}")
        assert len(eng._supply_gaps) == 2


class TestAnalyzeDemandPattern:
    def test_with_data(self):
        eng = _engine()
        eng.record_demand(
            "svc-a",
            demand_pattern=DemandPattern.GROWING,
            current_usage_pct=80.0,
        )
        result = eng.analyze_demand_pattern("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["demand_pattern"] == "growing"

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_demand_pattern("ghost")
        assert result["status"] == "no_data"


class TestIdentifySupplyDeficits:
    def test_with_deficits(self):
        eng = _engine()
        eng.record_demand("svc-a", current_usage_pct=96.0)
        eng.record_demand("svc-b", current_usage_pct=50.0)
        results = eng.identify_supply_deficits()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_supply_deficits() == []


class TestRankByPeakUsage:
    def test_with_data(self):
        eng = _engine()
        eng.record_demand("svc-a", peak_usage_pct=60.0)
        eng.record_demand("svc-b", peak_usage_pct=95.0)
        results = eng.rank_by_peak_usage()
        assert results[0]["peak_usage_pct"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_peak_usage() == []


class TestForecastDemandGrowth:
    def test_with_growing(self):
        eng = _engine()
        eng.record_demand(
            "svc-a",
            demand_pattern=DemandPattern.GROWING,
            current_usage_pct=60.0,
            peak_usage_pct=80.0,
        )
        eng.record_demand("svc-b", demand_pattern=DemandPattern.STEADY)
        results = eng.forecast_demand_growth()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.forecast_demand_growth() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_demand("svc-a", current_usage_pct=96.0)
        eng.record_demand(
            "svc-b",
            demand_pattern=DemandPattern.GROWING,
            current_usage_pct=50.0,
        )
        eng.record_supply_gap("svc-a")
        report = eng.generate_report()
        assert report.total_demands == 2
        assert report.total_supply_gaps == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_demands == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_demand("svc-a")
        eng.record_supply_gap("svc-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._supply_gaps) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_demands"] == 0
        assert stats["total_supply_gaps"] == 0
        assert stats["resource_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_demand("svc-a", resource_type=ResourceType.COMPUTE)
        eng.record_demand("svc-b", resource_type=ResourceType.GPU)
        eng.record_supply_gap("svc-a")
        stats = eng.get_stats()
        assert stats["total_demands"] == 2
        assert stats["total_supply_gaps"] == 1
        assert stats["unique_services"] == 2
