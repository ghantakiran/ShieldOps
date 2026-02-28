"""Tests for shieldops.billing.infra_cost_allocator — InfrastructureCostAllocator."""

from __future__ import annotations

from shieldops.billing.infra_cost_allocator import (
    AllocationAccuracy,
    AllocationMethod,
    AllocationRecord,
    AllocationSplit,
    CostCategory,
    InfraCostAllocatorReport,
    InfrastructureCostAllocator,
)


def _engine(**kw) -> InfrastructureCostAllocator:
    return InfrastructureCostAllocator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # AllocationMethod (5)
    def test_method_direct(self):
        assert AllocationMethod.DIRECT == "direct"

    def test_method_proportional(self):
        assert AllocationMethod.PROPORTIONAL == "proportional"

    def test_method_usage_based(self):
        assert AllocationMethod.USAGE_BASED == "usage_based"

    def test_method_fixed_split(self):
        assert AllocationMethod.FIXED_SPLIT == "fixed_split"

    def test_method_hybrid(self):
        assert AllocationMethod.HYBRID == "hybrid"

    # CostCategory (5)
    def test_category_compute(self):
        assert CostCategory.COMPUTE == "compute"

    def test_category_storage(self):
        assert CostCategory.STORAGE == "storage"

    def test_category_network(self):
        assert CostCategory.NETWORK == "network"

    def test_category_database(self):
        assert CostCategory.DATABASE == "database"

    def test_category_platform_services(self):
        assert CostCategory.PLATFORM_SERVICES == "platform_services"

    # AllocationAccuracy (5)
    def test_accuracy_exact(self):
        assert AllocationAccuracy.EXACT == "exact"

    def test_accuracy_high(self):
        assert AllocationAccuracy.HIGH == "high"

    def test_accuracy_moderate(self):
        assert AllocationAccuracy.MODERATE == "moderate"

    def test_accuracy_low(self):
        assert AllocationAccuracy.LOW == "low"

    def test_accuracy_estimated(self):
        assert AllocationAccuracy.ESTIMATED == "estimated"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_allocation_record_defaults(self):
        r = AllocationRecord()
        assert r.id
        assert r.resource_id == ""
        assert r.resource_name == ""
        assert r.team == ""
        assert r.service == ""
        assert r.cost_category == CostCategory.COMPUTE
        assert r.allocation_method == AllocationMethod.DIRECT
        assert r.total_cost == 0.0
        assert r.allocated_cost == 0.0
        assert r.unallocated_cost == 0.0
        assert r.accuracy == AllocationAccuracy.HIGH
        assert r.created_at > 0

    def test_allocation_split_defaults(self):
        r = AllocationSplit()
        assert r.id
        assert r.resource_id == ""
        assert r.team == ""
        assert r.split_pct == 0.0
        assert r.split_cost == 0.0
        assert r.allocation_method == AllocationMethod.PROPORTIONAL
        assert r.created_at > 0

    def test_report_defaults(self):
        r = InfraCostAllocatorReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_splits == 0
        assert r.total_cost == 0.0
        assert r.total_allocated == 0.0
        assert r.total_unallocated == 0.0
        assert r.unallocated_pct == 0.0
        assert r.by_cost_category == {}
        assert r.by_allocation_method == {}
        assert r.by_accuracy == {}
        assert r.top_cost_teams == []
        assert r.unallocated_resources == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_allocation
# -------------------------------------------------------------------


class TestRecordAllocation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_allocation("ec2-001")
        assert r.resource_id == "ec2-001"
        assert r.cost_category == CostCategory.COMPUTE

    def test_with_params(self):
        eng = _engine()
        r = eng.record_allocation(
            "rds-001",
            resource_name="prod-postgres",
            team="platform",
            service="auth-svc",
            cost_category=CostCategory.DATABASE,
            allocation_method=AllocationMethod.USAGE_BASED,
            total_cost=5000.0,
            allocated_cost=4800.0,
            unallocated_cost=200.0,
            accuracy=AllocationAccuracy.EXACT,
        )
        assert r.cost_category == CostCategory.DATABASE
        assert r.total_cost == 5000.0
        assert r.allocated_cost == 4800.0
        assert r.accuracy == AllocationAccuracy.EXACT

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_allocation("ec2-001")
        r2 = eng.record_allocation("ec2-002")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_allocation(f"resource-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_allocation
# -------------------------------------------------------------------


class TestGetAllocation:
    def test_found(self):
        eng = _engine()
        r = eng.record_allocation("ec2-001")
        assert eng.get_allocation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_allocation("nonexistent") is None


# -------------------------------------------------------------------
# list_allocations
# -------------------------------------------------------------------


class TestListAllocations:
    def test_list_all(self):
        eng = _engine()
        eng.record_allocation("r-a")
        eng.record_allocation("r-b")
        assert len(eng.list_allocations()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_allocation("r-a", cost_category=CostCategory.STORAGE)
        eng.record_allocation("r-b", cost_category=CostCategory.COMPUTE)
        results = eng.list_allocations(cost_category=CostCategory.STORAGE)
        assert len(results) == 1
        assert results[0].cost_category == CostCategory.STORAGE

    def test_filter_by_method(self):
        eng = _engine()
        eng.record_allocation("r-a", allocation_method=AllocationMethod.DIRECT)
        eng.record_allocation("r-b", allocation_method=AllocationMethod.HYBRID)
        results = eng.list_allocations(allocation_method=AllocationMethod.HYBRID)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_allocation("r-a", team="alpha")
        eng.record_allocation("r-b", team="beta")
        results = eng.list_allocations(team="alpha")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_allocation(f"r-{i}")
        assert len(eng.list_allocations(limit=4)) == 4


# -------------------------------------------------------------------
# add_split
# -------------------------------------------------------------------


class TestAddSplit:
    def test_basic(self):
        eng = _engine()
        s = eng.add_split("ec2-001")
        assert s.resource_id == "ec2-001"
        assert s.allocation_method == AllocationMethod.PROPORTIONAL

    def test_with_params(self):
        eng = _engine()
        s = eng.add_split(
            "s3-bucket-001",
            team="data-team",
            split_pct=60.0,
            split_cost=3000.0,
            allocation_method=AllocationMethod.USAGE_BASED,
        )
        assert s.team == "data-team"
        assert s.split_pct == 60.0
        assert s.split_cost == 3000.0

    def test_unique_ids(self):
        eng = _engine()
        s1 = eng.add_split("r-a")
        s2 = eng.add_split("r-b")
        assert s1.id != s2.id


# -------------------------------------------------------------------
# analyze_allocation_by_team
# -------------------------------------------------------------------


class TestAnalyzeAllocationByTeam:
    def test_empty(self):
        eng = _engine()
        assert eng.analyze_allocation_by_team() == []

    def test_with_data(self):
        eng = _engine()
        eng.record_allocation("r-a", team="alpha", total_cost=1000.0, allocated_cost=950.0)
        eng.record_allocation("r-b", team="alpha", total_cost=500.0, allocated_cost=490.0)
        eng.record_allocation("r-c", team="beta", total_cost=2000.0, allocated_cost=1800.0)
        results = eng.analyze_allocation_by_team()
        assert len(results) == 2
        assert results[0]["team"] == "beta"  # highest cost
        assert results[0]["total_cost"] == 2000.0

    def test_sorted_descending(self):
        eng = _engine()
        eng.record_allocation("r-x", team="cheap-team", total_cost=100.0)
        eng.record_allocation("r-y", team="expensive-team", total_cost=9000.0)
        results = eng.analyze_allocation_by_team()
        assert results[0]["total_cost"] >= results[-1]["total_cost"]


# -------------------------------------------------------------------
# identify_unallocated_costs
# -------------------------------------------------------------------


class TestIdentifyUnallocatedCosts:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_unallocated_costs() == []

    def test_below_threshold(self):
        eng = _engine(max_unallocated_pct=5.0)
        eng.record_allocation("r-a", total_cost=1000.0, unallocated_cost=30.0)  # 3% < 5%
        assert eng.identify_unallocated_costs() == []

    def test_above_threshold(self):
        eng = _engine(max_unallocated_pct=5.0)
        eng.record_allocation("ec2-001", total_cost=1000.0, unallocated_cost=200.0)  # 20% > 5%
        results = eng.identify_unallocated_costs()
        assert len(results) == 1
        assert results[0]["resource_id"] == "ec2-001"
        assert results[0]["unallocated_pct"] == 20.0

    def test_sorted_by_unallocated_cost_descending(self):
        eng = _engine(max_unallocated_pct=5.0)
        eng.record_allocation("r-cheap", total_cost=100.0, unallocated_cost=50.0)
        eng.record_allocation("r-expensive", total_cost=10000.0, unallocated_cost=5000.0)
        results = eng.identify_unallocated_costs()
        assert results[0]["unallocated_cost"] >= results[-1]["unallocated_cost"]


# -------------------------------------------------------------------
# rank_by_cost_share
# -------------------------------------------------------------------


class TestRankByCostShare:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cost_share() == []

    def test_with_data(self):
        eng = _engine()
        eng.record_allocation("r-a", team="alpha", total_cost=7000.0)
        eng.record_allocation("r-b", team="beta", total_cost=3000.0)
        results = eng.rank_by_cost_share()
        assert len(results) == 2
        assert results[0]["team"] == "alpha"
        assert results[0]["cost_share_pct"] == 70.0
        assert results[1]["cost_share_pct"] == 30.0

    def test_untagged_resources(self):
        eng = _engine()
        eng.record_allocation("r-a", total_cost=500.0)  # no team
        results = eng.rank_by_cost_share()
        assert len(results) == 1
        assert results[0]["team"] == "_untagged"


# -------------------------------------------------------------------
# detect_allocation_drift
# -------------------------------------------------------------------


class TestDetectAllocationDrift:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_allocation("r-a", total_cost=100.0)
        result = eng.detect_allocation_drift()
        assert result["drift_detected"] is False
        assert result["reason"] == "insufficient_data"

    def test_no_drift(self):
        eng = _engine()
        for _ in range(8):
            eng.record_allocation("r", total_cost=100.0, unallocated_cost=2.0)
        result = eng.detect_allocation_drift()
        assert result["drift_detected"] is False

    def test_drift_detected(self):
        eng = _engine()
        # First half: low unallocated
        for _ in range(4):
            eng.record_allocation("r", total_cost=100.0, unallocated_cost=2.0)
        # Second half: high unallocated
        for _ in range(4):
            eng.record_allocation("r", total_cost=100.0, unallocated_cost=40.0)
        result = eng.detect_allocation_drift()
        assert result["drift_detected"] is True
        assert result["delta_pct"] > 5.0


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert isinstance(report, InfraCostAllocatorReport)
        assert report.total_records == 0
        assert report.recommendations

    def test_with_data(self):
        eng = _engine(max_unallocated_pct=5.0)
        eng.record_allocation(
            "ec2-001",
            team="platform",
            cost_category=CostCategory.COMPUTE,
            total_cost=8000.0,
            allocated_cost=7500.0,
            unallocated_cost=500.0,
            accuracy=AllocationAccuracy.HIGH,
        )
        eng.record_allocation(
            "rds-001",
            team="data",
            cost_category=CostCategory.DATABASE,
            total_cost=3000.0,
            allocated_cost=3000.0,
            unallocated_cost=0.0,
            accuracy=AllocationAccuracy.EXACT,
        )
        eng.add_split("ec2-001", team="platform", split_pct=80.0)
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_splits == 1
        assert report.total_cost == 11000.0
        assert report.by_cost_category

    def test_recommendations_for_high_unallocated(self):
        eng = _engine(max_unallocated_pct=5.0)
        eng.record_allocation("r-a", total_cost=1000.0, unallocated_cost=900.0)
        report = eng.generate_report()
        assert any("unallocated" in rec.lower() for rec in report.recommendations)


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_records_and_splits(self):
        eng = _engine()
        eng.record_allocation("r-a", total_cost=100.0)
        eng.add_split("r-a", team="alpha")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._splits) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_splits"] == 0
        assert stats["total_cost"] == 0.0
        assert stats["unallocated_pct"] == 0.0

    def test_populated(self):
        eng = _engine(max_unallocated_pct=5.0)
        eng.record_allocation(
            "ec2-001",
            team="alpha",
            cost_category=CostCategory.COMPUTE,
            total_cost=10000.0,
            allocated_cost=9800.0,
            unallocated_cost=200.0,
        )
        eng.record_allocation(
            "s3-001",
            team="beta",
            cost_category=CostCategory.STORAGE,
            total_cost=2000.0,
            allocated_cost=2000.0,
            unallocated_cost=0.0,
        )
        eng.add_split("ec2-001", team="alpha", split_pct=70.0)
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_splits"] == 1
        assert stats["total_cost"] == 12000.0
        assert stats["max_unallocated_pct"] == 5.0
        assert stats["unique_teams"] == 2
        assert "compute" in stats["category_distribution"]
