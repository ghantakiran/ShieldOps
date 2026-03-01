"""Tests for shieldops.billing.procurement_optimizer — ProcurementOptimizer."""

from __future__ import annotations

from shieldops.billing.procurement_optimizer import (
    OptimizationAction,
    OptimizationOpportunity,
    ProcurementOptimizer,
    ProcurementRecord,
    ProcurementReport,
    ProcurementStatus,
    ProcurementType,
)


def _engine(**kw) -> ProcurementOptimizer:
    return ProcurementOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_reserved_capacity(self):
        assert ProcurementType.RESERVED_CAPACITY == "reserved_capacity"

    def test_type_on_demand(self):
        assert ProcurementType.ON_DEMAND == "on_demand"

    def test_type_spot(self):
        assert ProcurementType.SPOT == "spot"

    def test_type_marketplace(self):
        assert ProcurementType.MARKETPLACE == "marketplace"

    def test_type_enterprise(self):
        assert ProcurementType.ENTERPRISE == "enterprise"

    def test_status_optimal(self):
        assert ProcurementStatus.OPTIMAL == "optimal"

    def test_status_suboptimal(self):
        assert ProcurementStatus.SUBOPTIMAL == "suboptimal"

    def test_status_wasteful(self):
        assert ProcurementStatus.WASTEFUL == "wasteful"

    def test_status_expiring(self):
        assert ProcurementStatus.EXPIRING == "expiring"

    def test_status_needs_review(self):
        assert ProcurementStatus.NEEDS_REVIEW == "needs_review"

    def test_action_rightsize(self):
        assert OptimizationAction.RIGHTSIZE == "rightsize"

    def test_action_terminate(self):
        assert OptimizationAction.TERMINATE == "terminate"

    def test_action_convert_ri(self):
        assert OptimizationAction.CONVERT_RI == "convert_ri"

    def test_action_switch_region(self):
        assert OptimizationAction.SWITCH_REGION == "switch_region"

    def test_action_negotiate(self):
        assert OptimizationAction.NEGOTIATE == "negotiate"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_procurement_record_defaults(self):
        r = ProcurementRecord()
        assert r.id
        assert r.resource_name == ""
        assert r.procurement_type == ProcurementType.ON_DEMAND
        assert r.procurement_status == ProcurementStatus.NEEDS_REVIEW
        assert r.optimization_action == OptimizationAction.RIGHTSIZE
        assert r.waste_pct == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_optimization_opportunity_defaults(self):
        o = OptimizationOpportunity()
        assert o.id
        assert o.opportunity_name == ""
        assert o.procurement_type == ProcurementType.ON_DEMAND
        assert o.estimated_savings == 0.0
        assert o.avg_waste_pct == 0.0
        assert o.description == ""
        assert o.created_at > 0

    def test_procurement_report_defaults(self):
        r = ProcurementReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_opportunities == 0
        assert r.wasteful_procurements == 0
        assert r.avg_waste_pct == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_action == {}
        assert r.top_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_procurement
# ---------------------------------------------------------------------------


class TestRecordProcurement:
    def test_basic(self):
        eng = _engine()
        r = eng.record_procurement(
            resource_name="ec2-prod-01",
            procurement_type=ProcurementType.RESERVED_CAPACITY,
            procurement_status=ProcurementStatus.OPTIMAL,
            optimization_action=OptimizationAction.RIGHTSIZE,
            waste_pct=5.0,
            team="infra",
        )
        assert r.resource_name == "ec2-prod-01"
        assert r.procurement_type == ProcurementType.RESERVED_CAPACITY
        assert r.procurement_status == ProcurementStatus.OPTIMAL
        assert r.optimization_action == OptimizationAction.RIGHTSIZE
        assert r.waste_pct == 5.0
        assert r.team == "infra"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_procurement(resource_name=f"res-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_procurement
# ---------------------------------------------------------------------------


class TestGetProcurement:
    def test_found(self):
        eng = _engine()
        r = eng.record_procurement(
            resource_name="ec2-prod-01",
            procurement_type=ProcurementType.SPOT,
        )
        result = eng.get_procurement(r.id)
        assert result is not None
        assert result.procurement_type == ProcurementType.SPOT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_procurement("nonexistent") is None


# ---------------------------------------------------------------------------
# list_procurements
# ---------------------------------------------------------------------------


class TestListProcurements:
    def test_list_all(self):
        eng = _engine()
        eng.record_procurement(resource_name="res-1")
        eng.record_procurement(resource_name="res-2")
        assert len(eng.list_procurements()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_procurement(
            resource_name="res-1",
            procurement_type=ProcurementType.ON_DEMAND,
        )
        eng.record_procurement(
            resource_name="res-2",
            procurement_type=ProcurementType.SPOT,
        )
        results = eng.list_procurements(procurement_type=ProcurementType.ON_DEMAND)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_procurement(
            resource_name="res-1",
            procurement_status=ProcurementStatus.OPTIMAL,
        )
        eng.record_procurement(
            resource_name="res-2",
            procurement_status=ProcurementStatus.WASTEFUL,
        )
        results = eng.list_procurements(status=ProcurementStatus.OPTIMAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_procurement(resource_name="res-1", team="infra")
        eng.record_procurement(resource_name="res-2", team="platform")
        results = eng.list_procurements(team="infra")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_procurement(resource_name=f"res-{i}")
        assert len(eng.list_procurements(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_opportunity
# ---------------------------------------------------------------------------


class TestAddOpportunity:
    def test_basic(self):
        eng = _engine()
        o = eng.add_opportunity(
            opportunity_name="switch-to-ri",
            procurement_type=ProcurementType.RESERVED_CAPACITY,
            estimated_savings=5000.0,
            avg_waste_pct=25.0,
            description="Convert on-demand to RI",
        )
        assert o.opportunity_name == "switch-to-ri"
        assert o.procurement_type == ProcurementType.RESERVED_CAPACITY
        assert o.estimated_savings == 5000.0
        assert o.avg_waste_pct == 25.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_opportunity(opportunity_name=f"opp-{i}")
        assert len(eng._opportunities) == 2


# ---------------------------------------------------------------------------
# analyze_procurement_efficiency
# ---------------------------------------------------------------------------


class TestAnalyzeProcurementEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_procurement(
            resource_name="res-1",
            procurement_type=ProcurementType.ON_DEMAND,
            waste_pct=15.0,
        )
        eng.record_procurement(
            resource_name="res-2",
            procurement_type=ProcurementType.ON_DEMAND,
            waste_pct=25.0,
        )
        result = eng.analyze_procurement_efficiency()
        assert "on_demand" in result
        assert result["on_demand"]["count"] == 2
        assert result["on_demand"]["avg_waste_pct"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_procurement_efficiency() == {}


# ---------------------------------------------------------------------------
# identify_waste
# ---------------------------------------------------------------------------


class TestIdentifyWaste:
    def test_detects_wasteful(self):
        eng = _engine()
        eng.record_procurement(
            resource_name="res-1",
            procurement_status=ProcurementStatus.WASTEFUL,
            waste_pct=40.0,
        )
        eng.record_procurement(
            resource_name="res-2",
            procurement_status=ProcurementStatus.OPTIMAL,
        )
        results = eng.identify_waste()
        assert len(results) == 1
        assert results[0]["resource_name"] == "res-1"

    def test_detects_expiring(self):
        eng = _engine()
        eng.record_procurement(
            resource_name="res-1",
            procurement_status=ProcurementStatus.EXPIRING,
        )
        results = eng.identify_waste()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_waste() == []


# ---------------------------------------------------------------------------
# rank_by_savings_potential
# ---------------------------------------------------------------------------


class TestRankBySavingsPotential:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_procurement(resource_name="r-1", team="infra", waste_pct=30.0)
        eng.record_procurement(resource_name="r-2", team="infra", waste_pct=20.0)
        eng.record_procurement(resource_name="r-3", team="platform", waste_pct=10.0)
        results = eng.rank_by_savings_potential()
        assert len(results) == 2
        assert results[0]["team"] == "infra"
        assert results[0]["avg_waste_pct"] == 25.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_savings_potential() == []


# ---------------------------------------------------------------------------
# detect_procurement_trends
# ---------------------------------------------------------------------------


class TestDetectProcurementTrends:
    def test_stable(self):
        eng = _engine()
        for s in [20.0, 20.0, 20.0, 20.0]:
            eng.add_opportunity(opportunity_name="o", avg_waste_pct=s)
        result = eng.detect_procurement_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [10.0, 10.0, 40.0, 40.0]:
            eng.add_opportunity(opportunity_name="o", avg_waste_pct=s)
        result = eng.detect_procurement_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_procurement_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_procurement(
            resource_name="res-1",
            procurement_type=ProcurementType.ON_DEMAND,
            procurement_status=ProcurementStatus.WASTEFUL,
            waste_pct=25.0,
            team="infra",
        )
        report = eng.generate_report()
        assert isinstance(report, ProcurementReport)
        assert report.total_records == 1
        assert report.wasteful_procurements == 1
        assert report.avg_waste_pct == 25.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable limits" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_procurement(resource_name="res-1")
        eng.add_opportunity(opportunity_name="o1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._opportunities) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_opportunities"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_procurement(
            resource_name="res-1",
            procurement_type=ProcurementType.ON_DEMAND,
            team="infra",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_resources"] == 1
        assert "on_demand" in stats["type_distribution"]
