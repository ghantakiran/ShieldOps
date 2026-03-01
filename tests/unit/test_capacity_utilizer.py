"""Tests for shieldops.billing.capacity_utilizer — CapacityUtilizationOptimizer."""

from __future__ import annotations

from shieldops.billing.capacity_utilizer import (
    CapacityUtilizationOptimizer,
    CapacityUtilizerReport,
    OptimizationAction,
    OptimizationSuggestion,
    ResourceType,
    UtilizationBand,
    UtilizationRecord,
)


def _engine(**kw) -> CapacityUtilizationOptimizer:
    return CapacityUtilizationOptimizer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ResourceType (5)
    def test_type_compute(self):
        assert ResourceType.COMPUTE == "compute"

    def test_type_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_type_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_type_network(self):
        assert ResourceType.NETWORK == "network"

    def test_type_gpu(self):
        assert ResourceType.GPU == "gpu"

    # UtilizationBand (5)
    def test_band_over_provisioned(self):
        assert UtilizationBand.OVER_PROVISIONED == "over_provisioned"

    def test_band_optimal(self):
        assert UtilizationBand.OPTIMAL == "optimal"

    def test_band_under_utilized(self):
        assert UtilizationBand.UNDER_UTILIZED == "under_utilized"

    def test_band_idle(self):
        assert UtilizationBand.IDLE == "idle"

    def test_band_unknown(self):
        assert UtilizationBand.UNKNOWN == "unknown"

    # OptimizationAction (5)
    def test_action_downsize(self):
        assert OptimizationAction.DOWNSIZE == "downsize"

    def test_action_upsize(self):
        assert OptimizationAction.UPSIZE == "upsize"

    def test_action_terminate(self):
        assert OptimizationAction.TERMINATE == "terminate"

    def test_action_rightsize(self):
        assert OptimizationAction.RIGHTSIZE == "rightsize"

    def test_action_schedule(self):
        assert OptimizationAction.SCHEDULE == "schedule"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_utilization_record_defaults(self):
        r = UtilizationRecord()
        assert r.id
        assert r.resource_id == ""
        assert r.resource_type == ResourceType.COMPUTE
        assert r.utilization_pct == 0.0
        assert r.band == UtilizationBand.OPTIMAL
        assert r.team == ""
        assert r.recommended_action == OptimizationAction.RIGHTSIZE
        assert r.potential_savings == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_optimization_suggestion_defaults(self):
        r = OptimizationSuggestion()
        assert r.id
        assert r.resource_id == ""
        assert r.action == OptimizationAction.RIGHTSIZE
        assert r.current_size == ""
        assert r.recommended_size == ""
        assert r.estimated_savings == 0.0
        assert r.confidence_pct == 0.0
        assert r.created_at > 0

    def test_capacity_utilizer_report_defaults(self):
        r = CapacityUtilizerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_suggestions == 0
        assert r.avg_utilization_pct == 0.0
        assert r.by_resource_type == {}
        assert r.by_band == {}
        assert r.by_action == {}
        assert r.total_savings_potential == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_utilization
# -------------------------------------------------------------------


class TestRecordUtilization:
    def test_basic(self):
        eng = _engine()
        r = eng.record_utilization(
            "res-1",
            resource_type=ResourceType.MEMORY,
            band=UtilizationBand.UNDER_UTILIZED,
        )
        assert r.resource_id == "res-1"
        assert r.resource_type == ResourceType.MEMORY

    def test_with_savings(self):
        eng = _engine()
        r = eng.record_utilization("res-2", potential_savings=500.0)
        assert r.potential_savings == 500.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_utilization(f"res-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_utilization
# -------------------------------------------------------------------


class TestGetUtilization:
    def test_found(self):
        eng = _engine()
        r = eng.record_utilization("res-1")
        assert eng.get_utilization(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_utilization("nonexistent") is None


# -------------------------------------------------------------------
# list_utilizations
# -------------------------------------------------------------------


class TestListUtilizations:
    def test_list_all(self):
        eng = _engine()
        eng.record_utilization("res-1")
        eng.record_utilization("res-2")
        assert len(eng.list_utilizations()) == 2

    def test_filter_by_resource_type(self):
        eng = _engine()
        eng.record_utilization("res-1", resource_type=ResourceType.GPU)
        eng.record_utilization("res-2", resource_type=ResourceType.COMPUTE)
        results = eng.list_utilizations(resource_type=ResourceType.GPU)
        assert len(results) == 1

    def test_filter_by_band(self):
        eng = _engine()
        eng.record_utilization("res-1", band=UtilizationBand.IDLE)
        eng.record_utilization("res-2", band=UtilizationBand.OPTIMAL)
        results = eng.list_utilizations(band=UtilizationBand.IDLE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_utilization("res-1", team="alpha")
        eng.record_utilization("res-2", team="beta")
        results = eng.list_utilizations(team="alpha")
        assert len(results) == 1


# -------------------------------------------------------------------
# add_suggestion
# -------------------------------------------------------------------


class TestAddSuggestion:
    def test_basic(self):
        eng = _engine()
        s = eng.add_suggestion(
            "res-1",
            action=OptimizationAction.DOWNSIZE,
            current_size="xlarge",
            recommended_size="medium",
            estimated_savings=200.0,
            confidence_pct=85.0,
        )
        assert s.resource_id == "res-1"
        assert s.action == OptimizationAction.DOWNSIZE
        assert s.estimated_savings == 200.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_suggestion(f"res-{i}")
        assert len(eng._suggestions) == 2


# -------------------------------------------------------------------
# analyze_utilization_by_type
# -------------------------------------------------------------------


class TestAnalyzeUtilizationByType:
    def test_with_data(self):
        eng = _engine()
        eng.record_utilization("r1", resource_type=ResourceType.COMPUTE, utilization_pct=60.0)
        eng.record_utilization("r2", resource_type=ResourceType.COMPUTE, utilization_pct=80.0)
        eng.record_utilization("r3", resource_type=ResourceType.MEMORY, utilization_pct=30.0)
        results = eng.analyze_utilization_by_type()
        assert len(results) == 2
        assert results[0]["resource_type"] == "compute"
        assert results[0]["avg_utilization_pct"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_utilization_by_type() == []


# -------------------------------------------------------------------
# identify_optimization_opportunities
# -------------------------------------------------------------------


class TestIdentifyOptimizationOpportunities:
    def test_with_opportunities(self):
        eng = _engine()
        eng.record_utilization("r1", band=UtilizationBand.UNDER_UTILIZED, potential_savings=300.0)
        eng.record_utilization("r2", band=UtilizationBand.IDLE, potential_savings=500.0)
        eng.record_utilization("r3", band=UtilizationBand.OPTIMAL, potential_savings=0.0)
        results = eng.identify_optimization_opportunities()
        assert len(results) == 2
        assert results[0]["potential_savings"] == 500.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_optimization_opportunities() == []


# -------------------------------------------------------------------
# rank_by_savings_potential
# -------------------------------------------------------------------


class TestRankBySavingsPotential:
    def test_with_data(self):
        eng = _engine()
        eng.record_utilization("r1", team="alpha", potential_savings=400.0)
        eng.record_utilization("r2", team="alpha", potential_savings=200.0)
        eng.record_utilization("r3", team="beta", potential_savings=50.0)
        results = eng.rank_by_savings_potential()
        assert results[0]["team"] == "alpha"
        assert results[0]["total_savings"] == 600.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_savings_potential() == []


# -------------------------------------------------------------------
# detect_utilization_trends
# -------------------------------------------------------------------


class TestDetectUtilizationTrends:
    def test_increasing_trend(self):
        eng = _engine()
        eng.record_utilization("r1", team="alpha", utilization_pct=20.0)
        eng.record_utilization("r2", team="alpha", utilization_pct=22.0)
        eng.record_utilization("r3", team="alpha", utilization_pct=40.0)
        eng.record_utilization("r4", team="alpha", utilization_pct=45.0)
        results = eng.detect_utilization_trends()
        assert len(results) == 1
        assert results[0]["trend"] == "increasing"

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_utilization("r1", team="alpha", utilization_pct=50.0)
        results = eng.detect_utilization_trends()
        assert len(results) == 1
        assert results[0]["trend"] == "insufficient_data"

    def test_stable_trend(self):
        eng = _engine()
        eng.record_utilization("r1", team="alpha", utilization_pct=50.0)
        eng.record_utilization("r2", team="alpha", utilization_pct=51.0)
        eng.record_utilization("r3", team="alpha", utilization_pct=50.0)
        eng.record_utilization("r4", team="alpha", utilization_pct=52.0)
        results = eng.detect_utilization_trends()
        assert results[0]["trend"] == "stable"


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_utilization(
            "r1",
            resource_type=ResourceType.COMPUTE,
            band=UtilizationBand.UNDER_UTILIZED,
            potential_savings=300.0,
        )
        eng.record_utilization(
            "r2",
            resource_type=ResourceType.MEMORY,
            band=UtilizationBand.OPTIMAL,
            potential_savings=0.0,
        )
        eng.add_suggestion("r1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_suggestions == 1
        assert report.by_resource_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_utilization("r1")
        eng.add_suggestion("r1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._suggestions) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_suggestions"] == 0
        assert stats["resource_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_utilization("r1", resource_type=ResourceType.COMPUTE)
        eng.record_utilization("r2", resource_type=ResourceType.GPU)
        eng.add_suggestion("r1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_suggestions"] == 1
        assert stats["unique_resources"] == 2
