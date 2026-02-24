"""Tests for shieldops.billing.resource_waste — ResourceWasteDetector."""

from __future__ import annotations

from shieldops.billing.resource_waste import (
    ResourceType,
    ResourceWasteDetector,
    WasteCategory,
    WasteRecord,
    WasteReport,
    WasteSeverity,
    WasteSummary,
)


def _engine(**kw) -> ResourceWasteDetector:
    return ResourceWasteDetector(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # WasteCategory (5 values)

    def test_waste_category_idle(self):
        assert WasteCategory.IDLE == "idle"

    def test_waste_category_underutilized(self):
        assert WasteCategory.UNDERUTILIZED == "underutilized"

    def test_waste_category_orphaned(self):
        assert WasteCategory.ORPHANED == "orphaned"

    def test_waste_category_oversized(self):
        assert WasteCategory.OVERSIZED == "oversized"

    def test_waste_category_unattached(self):
        assert WasteCategory.UNATTACHED == "unattached"

    # ResourceType (5 values)

    def test_resource_type_compute(self):
        assert ResourceType.COMPUTE == "compute"

    def test_resource_type_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_resource_type_database(self):
        assert ResourceType.DATABASE == "database"

    def test_resource_type_network(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_type_container(self):
        assert ResourceType.CONTAINER == "container"

    # WasteSeverity (5 values)

    def test_severity_negligible(self):
        assert WasteSeverity.NEGLIGIBLE == "negligible"

    def test_severity_low(self):
        assert WasteSeverity.LOW == "low"

    def test_severity_moderate(self):
        assert WasteSeverity.MODERATE == "moderate"

    def test_severity_high(self):
        assert WasteSeverity.HIGH == "high"

    def test_severity_critical(self):
        assert WasteSeverity.CRITICAL == "critical"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_waste_record_defaults(self):
        rec = WasteRecord()
        assert rec.id
        assert rec.resource_id == ""
        assert rec.resource_type == ResourceType.COMPUTE
        assert rec.waste_category == WasteCategory.IDLE
        assert rec.severity == WasteSeverity.LOW
        assert rec.utilization_pct == 0.0
        assert rec.estimated_monthly_waste == 0.0
        assert rec.service_name == ""
        assert rec.region == ""
        assert rec.last_active == 0.0
        assert rec.created_at > 0

    def test_waste_summary_defaults(self):
        s = WasteSummary()
        assert s.resource_type == ResourceType.COMPUTE
        assert s.waste_category == WasteCategory.IDLE
        assert s.total_resources == 0
        assert s.total_monthly_waste == 0.0
        assert s.avg_utilization_pct == 0.0
        assert s.severity == WasteSeverity.LOW
        assert s.created_at > 0

    def test_waste_report_defaults(self):
        report = WasteReport()
        assert report.total_resources_scanned == 0
        assert report.total_waste_detected == 0
        assert report.total_monthly_waste == 0.0
        assert report.by_category == {}
        assert report.by_type == {}
        assert report.by_severity == {}
        assert report.top_wasters == []
        assert report.recommendations == []
        assert report.generated_at > 0


# -------------------------------------------------------------------
# record_waste
# -------------------------------------------------------------------


class TestRecordWaste:
    def test_basic_record(self):
        eng = _engine()
        rec = eng.record_waste(
            resource_id="i-123",
            estimated_monthly_waste=500.0,
        )
        assert rec.resource_id == "i-123"
        assert rec.estimated_monthly_waste == 500.0
        assert len(eng.list_waste()) == 1

    def test_record_assigns_unique_ids(self):
        eng = _engine()
        r1 = eng.record_waste(resource_id="i-1")
        r2 = eng.record_waste(resource_id="i-2")
        assert r1.id != r2.id

    def test_severity_auto_computed(self):
        eng = _engine()
        rec = eng.record_waste(
            resource_id="i-big",
            estimated_monthly_waste=15000.0,
        )
        assert rec.severity == WasteSeverity.CRITICAL

    def test_eviction_at_max_records(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            rec = eng.record_waste(
                resource_id=f"i-{i}",
            )
            ids.append(rec.id)
        records = eng.list_waste(limit=100)
        assert len(records) == 3
        found = {r.id for r in records}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_waste
# -------------------------------------------------------------------


class TestGetWaste:
    def test_get_existing(self):
        eng = _engine()
        rec = eng.record_waste(resource_id="i-123")
        found = eng.get_waste(rec.id)
        assert found is not None
        assert found.id == rec.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_waste("nonexistent") is None


# -------------------------------------------------------------------
# list_waste
# -------------------------------------------------------------------


class TestListWaste:
    def test_list_all(self):
        eng = _engine()
        eng.record_waste(resource_id="i-1")
        eng.record_waste(resource_id="i-2")
        eng.record_waste(resource_id="i-3")
        assert len(eng.list_waste()) == 3

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-1",
            resource_type=ResourceType.COMPUTE,
        )
        eng.record_waste(
            resource_id="i-2",
            resource_type=ResourceType.STORAGE,
        )
        eng.record_waste(
            resource_id="i-3",
            resource_type=ResourceType.COMPUTE,
        )
        results = eng.list_waste(
            resource_type=ResourceType.COMPUTE,
        )
        assert len(results) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-1",
            waste_category=WasteCategory.IDLE,
        )
        eng.record_waste(
            resource_id="i-2",
            waste_category=WasteCategory.ORPHANED,
        )
        results = eng.list_waste(
            waste_category=WasteCategory.IDLE,
        )
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_waste(resource_id=f"i-{i}")
        results = eng.list_waste(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# calculate_total_waste
# -------------------------------------------------------------------


class TestCalculateTotalWaste:
    def test_basic_total(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-1",
            estimated_monthly_waste=100.50,
        )
        eng.record_waste(
            resource_id="i-2",
            estimated_monthly_waste=200.25,
        )
        assert eng.calculate_total_waste() == 300.75

    def test_empty(self):
        eng = _engine()
        assert eng.calculate_total_waste() == 0.0


# -------------------------------------------------------------------
# rank_by_waste_cost
# -------------------------------------------------------------------


class TestRankByWasteCost:
    def test_ranking_order(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-small",
            estimated_monthly_waste=50.0,
        )
        eng.record_waste(
            resource_id="i-big",
            estimated_monthly_waste=5000.0,
        )
        eng.record_waste(
            resource_id="i-mid",
            estimated_monthly_waste=500.0,
        )
        ranked = eng.rank_by_waste_cost()
        assert ranked[0].resource_id == "i-big"
        assert ranked[1].resource_id == "i-mid"
        assert ranked[2].resource_id == "i-small"

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_waste(
                resource_id=f"i-{i}",
                estimated_monthly_waste=float(i * 100),
            )
        ranked = eng.rank_by_waste_cost(limit=3)
        assert len(ranked) == 3


# -------------------------------------------------------------------
# detect_idle_resources
# -------------------------------------------------------------------


class TestDetectIdleResources:
    def test_finds_idle(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-idle",
            utilization_pct=2.0,
        )
        eng.record_waste(
            resource_id="i-active",
            utilization_pct=80.0,
        )
        idle = eng.detect_idle_resources()
        assert len(idle) == 1
        assert idle[0].resource_id == "i-idle"

    def test_custom_threshold(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-1",
            utilization_pct=15.0,
        )
        idle = eng.detect_idle_resources(
            threshold_pct=20.0,
        )
        assert len(idle) == 1

    def test_no_idle(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-1",
            utilization_pct=90.0,
        )
        idle = eng.detect_idle_resources()
        assert len(idle) == 0


# -------------------------------------------------------------------
# identify_orphaned_resources
# -------------------------------------------------------------------


class TestIdentifyOrphanedResources:
    def test_finds_orphaned(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-orphan",
            waste_category=WasteCategory.ORPHANED,
        )
        eng.record_waste(
            resource_id="i-normal",
            waste_category=WasteCategory.IDLE,
        )
        orphaned = eng.identify_orphaned_resources()
        assert len(orphaned) == 1
        assert orphaned[0].resource_id == "i-orphan"

    def test_no_orphaned(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-1",
            waste_category=WasteCategory.IDLE,
        )
        assert eng.identify_orphaned_resources() == []


# -------------------------------------------------------------------
# estimate_savings_potential
# -------------------------------------------------------------------


class TestEstimateSavingsPotential:
    def test_basic_savings(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-1",
            waste_category=WasteCategory.IDLE,
            resource_type=ResourceType.COMPUTE,
            estimated_monthly_waste=1000.0,
        )
        eng.record_waste(
            resource_id="i-2",
            waste_category=WasteCategory.ORPHANED,
            resource_type=ResourceType.STORAGE,
            estimated_monthly_waste=500.0,
        )
        savings = eng.estimate_savings_potential()
        assert savings["total_monthly_savings"] == 1500.0
        assert savings["annual_savings"] == 18000.0
        assert savings["by_category"]["idle"] == 1000.0
        assert savings["by_type"]["compute"] == 1000.0

    def test_empty_savings(self):
        eng = _engine()
        savings = eng.estimate_savings_potential()
        assert savings["total_monthly_savings"] == 0.0
        assert savings["annual_savings"] == 0.0


# -------------------------------------------------------------------
# generate_waste_report
# -------------------------------------------------------------------


class TestGenerateWasteReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-1",
            waste_category=WasteCategory.IDLE,
            estimated_monthly_waste=1000.0,
        )
        eng.record_waste(
            resource_id="i-2",
            waste_category=WasteCategory.ORPHANED,
            estimated_monthly_waste=500.0,
        )
        report = eng.generate_waste_report()
        assert report.total_resources_scanned == 2
        assert report.total_waste_detected == 2
        assert report.total_monthly_waste == 1500.0
        assert "idle" in report.by_category
        assert len(report.top_wasters) <= 5
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_waste_report()
        assert report.total_resources_scanned == 0
        assert report.total_monthly_waste == 0.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_waste(resource_id="i-1")
        eng.record_waste(resource_id="i-2")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_waste()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_monthly_waste"] == 0.0
        assert stats["idle_threshold_pct"] == 5.0
        assert stats["category_distribution"] == {}
        assert stats["type_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_waste(
            resource_id="i-1",
            waste_category=WasteCategory.IDLE,
            resource_type=ResourceType.COMPUTE,
            estimated_monthly_waste=100.0,
        )
        eng.record_waste(
            resource_id="i-2",
            waste_category=WasteCategory.ORPHANED,
            resource_type=ResourceType.STORAGE,
            estimated_monthly_waste=200.0,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_monthly_waste"] == 300.0
        assert "idle" in stats["category_distribution"]
        assert "compute" in stats["type_distribution"]
