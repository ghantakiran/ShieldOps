"""Tests for shieldops.billing.spend_allocation — SpendAllocationEngine."""

from __future__ import annotations

from shieldops.billing.spend_allocation import (
    AllocationReport,
    AllocationStrategy,
    ChargebackModel,
    CostCategory,
    SharedCostPool,
    SpendAllocationEngine,
    TeamAllocation,
)


def _engine(**kw) -> SpendAllocationEngine:
    return SpendAllocationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # AllocationStrategy (5)
    def test_strategy_usage_based(self):
        assert AllocationStrategy.USAGE_BASED == "usage_based"

    def test_strategy_headcount_based(self):
        assert AllocationStrategy.HEADCOUNT_BASED == "headcount_based"

    def test_strategy_even_split(self):
        assert AllocationStrategy.EVEN_SPLIT == "even_split"

    def test_strategy_weighted(self):
        assert AllocationStrategy.WEIGHTED == "weighted"

    def test_strategy_custom_formula(self):
        assert AllocationStrategy.CUSTOM_FORMULA == "custom_formula"

    # CostCategory (6)
    def test_category_shared_infrastructure(self):
        assert CostCategory.SHARED_INFRASTRUCTURE == "shared_infrastructure"

    def test_category_dedicated_resources(self):
        assert CostCategory.DEDICATED_RESOURCES == "dedicated_resources"

    def test_category_platform_overhead(self):
        assert CostCategory.PLATFORM_OVERHEAD == "platform_overhead"

    def test_category_network_transfer(self):
        assert CostCategory.NETWORK_TRANSFER == "network_transfer"

    def test_category_support_costs(self):
        assert CostCategory.SUPPORT_COSTS == "support_costs"

    def test_category_license_fees(self):
        assert CostCategory.LICENSE_FEES == "license_fees"

    # ChargebackModel (5)
    def test_chargeback_showback(self):
        assert ChargebackModel.SHOWBACK == "showback"

    def test_chargeback_chargeback(self):
        assert ChargebackModel.CHARGEBACK == "chargeback"

    def test_chargeback_hybrid(self):
        assert ChargebackModel.HYBRID == "hybrid"

    def test_chargeback_direct(self):
        assert ChargebackModel.DIRECT == "direct"

    def test_chargeback_tiered(self):
        assert ChargebackModel.TIERED == "tiered"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_shared_cost_pool_defaults(self):
        p = SharedCostPool()
        assert p.id
        assert p.pool_name == ""
        assert p.total_cost == 0.0
        assert p.category == CostCategory.SHARED_INFRASTRUCTURE
        assert p.strategy == AllocationStrategy.EVEN_SPLIT
        assert p.chargeback_model == ChargebackModel.SHOWBACK
        assert p.created_at > 0

    def test_team_allocation_defaults(self):
        a = TeamAllocation()
        assert a.id
        assert a.pool_id == ""
        assert a.team_name == ""
        assert a.allocation_pct == 0.0
        assert a.allocated_amount == 0.0
        assert a.usage_units == 0.0
        assert a.headcount == 0
        assert a.created_at > 0

    def test_allocation_report_defaults(self):
        r = AllocationReport()
        assert r.total_pools == 0
        assert r.total_cost_allocated == 0.0
        assert r.team_count == 0
        assert r.strategy_distribution == {}
        assert r.largest_pool == ""
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# register_pool
# ---------------------------------------------------------------------------


class TestRegisterPool:
    def test_basic_register(self):
        eng = _engine()
        pool = eng.register_pool(
            pool_name="shared-infra",
            total_cost=10000.0,
            category=CostCategory.SHARED_INFRASTRUCTURE,
            strategy=AllocationStrategy.EVEN_SPLIT,
        )
        assert pool.pool_name == "shared-infra"
        assert pool.total_cost == 10000.0
        assert pool.category == CostCategory.SHARED_INFRASTRUCTURE
        assert pool.strategy == AllocationStrategy.EVEN_SPLIT

    def test_eviction_at_max(self):
        eng = _engine(max_pools=3)
        for i in range(5):
            eng.register_pool(pool_name=f"pool-{i}", total_cost=float(i * 1000))
        assert len(eng._pools) == 3


# ---------------------------------------------------------------------------
# get_pool
# ---------------------------------------------------------------------------


class TestGetPool:
    def test_found(self):
        eng = _engine()
        pool = eng.register_pool(pool_name="k8s-cluster", total_cost=5000.0)
        assert eng.get_pool(pool.id) is not None
        assert eng.get_pool(pool.id).pool_name == "k8s-cluster"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_pool("nonexistent") is None


# ---------------------------------------------------------------------------
# list_pools
# ---------------------------------------------------------------------------


class TestListPools:
    def test_list_all(self):
        eng = _engine()
        eng.register_pool("pool-a", 1000.0)
        eng.register_pool("pool-b", 2000.0)
        assert len(eng.list_pools()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.register_pool("a", 1000.0, category=CostCategory.SHARED_INFRASTRUCTURE)
        eng.register_pool("b", 2000.0, category=CostCategory.LICENSE_FEES)
        results = eng.list_pools(category=CostCategory.LICENSE_FEES)
        assert len(results) == 1
        assert results[0].pool_name == "b"

    def test_filter_by_strategy(self):
        eng = _engine()
        eng.register_pool("a", 1000.0, strategy=AllocationStrategy.EVEN_SPLIT)
        eng.register_pool("b", 2000.0, strategy=AllocationStrategy.USAGE_BASED)
        results = eng.list_pools(strategy=AllocationStrategy.USAGE_BASED)
        assert len(results) == 1
        assert results[0].pool_name == "b"


# ---------------------------------------------------------------------------
# add_team_allocation
# ---------------------------------------------------------------------------


class TestAddTeamAllocation:
    def test_basic_add_with_auto_calculated_amount(self):
        eng = _engine()
        pool = eng.register_pool("shared", 10000.0)
        alloc = eng.add_team_allocation(
            pool_id=pool.id,
            team_name="platform",
            allocation_pct=25.0,
        )
        assert alloc is not None
        assert alloc.team_name == "platform"
        assert alloc.allocation_pct == 25.0
        # 10000.0 * 25.0 / 100 = 2500.0
        assert alloc.allocated_amount == 2500.0


# ---------------------------------------------------------------------------
# calculate_allocations
# ---------------------------------------------------------------------------


class TestCalculateAllocations:
    def test_even_split(self):
        eng = _engine()
        pool = eng.register_pool("shared", 9000.0, strategy=AllocationStrategy.EVEN_SPLIT)
        eng.add_team_allocation(pool.id, "team-a")
        eng.add_team_allocation(pool.id, "team-b")
        eng.add_team_allocation(pool.id, "team-c")
        allocs = eng.calculate_allocations(pool.id)
        assert len(allocs) == 3
        for a in allocs:
            assert a.allocated_amount == 3000.0

    def test_usage_based(self):
        eng = _engine()
        pool = eng.register_pool("shared", 10000.0, strategy=AllocationStrategy.USAGE_BASED)
        eng.add_team_allocation(pool.id, "team-a", usage_units=300.0)
        eng.add_team_allocation(pool.id, "team-b", usage_units=700.0)
        allocs = eng.calculate_allocations(pool.id)
        assert len(allocs) == 2
        # team-a: 300/1000 * 10000 = 3000
        a_alloc = [a for a in allocs if a.team_name == "team-a"][0]
        b_alloc = [a for a in allocs if a.team_name == "team-b"][0]
        assert a_alloc.allocated_amount == 3000.0
        assert b_alloc.allocated_amount == 7000.0

    def test_headcount_based(self):
        eng = _engine()
        pool = eng.register_pool("shared", 5000.0, strategy=AllocationStrategy.HEADCOUNT_BASED)
        eng.add_team_allocation(pool.id, "team-a", headcount=10)
        eng.add_team_allocation(pool.id, "team-b", headcount=40)
        allocs = eng.calculate_allocations(pool.id)
        assert len(allocs) == 2
        a_alloc = [a for a in allocs if a.team_name == "team-a"][0]
        b_alloc = [a for a in allocs if a.team_name == "team-b"][0]
        # team-a: 10/50 * 5000 = 1000
        assert a_alloc.allocated_amount == 1000.0
        assert b_alloc.allocated_amount == 4000.0


# ---------------------------------------------------------------------------
# get_team_total_spend
# ---------------------------------------------------------------------------


class TestGetTeamTotalSpend:
    def test_across_pools(self):
        eng = _engine()
        pool_a = eng.register_pool("infra", 10000.0)
        pool_b = eng.register_pool("licenses", 2000.0)
        eng.add_team_allocation(pool_a.id, "platform", allocation_pct=50.0)
        eng.add_team_allocation(pool_b.id, "platform", allocation_pct=25.0)
        result = eng.get_team_total_spend("platform")
        assert result["team_name"] == "platform"
        # 10000*0.50 + 2000*0.25 = 5000 + 500 = 5500
        assert result["total_allocated"] == 5500.0
        assert result["pool_count"] == 2
        assert len(result["pool_breakdown"]) == 2


# ---------------------------------------------------------------------------
# compare_team_allocations
# ---------------------------------------------------------------------------


class TestCompareTeamAllocations:
    def test_multiple_teams(self):
        eng = _engine()
        pool = eng.register_pool("shared", 10000.0)
        eng.add_team_allocation(pool.id, "team-a", allocation_pct=60.0)
        eng.add_team_allocation(pool.id, "team-b", allocation_pct=40.0)
        comparisons = eng.compare_team_allocations()
        assert len(comparisons) == 2
        # Sorted descending by total_allocated
        assert comparisons[0]["team_name"] == "team-a"
        assert comparisons[0]["total_allocated"] == 6000.0
        assert comparisons[1]["team_name"] == "team-b"
        assert comparisons[1]["total_allocated"] == 4000.0


# ---------------------------------------------------------------------------
# detect_allocation_anomalies
# ---------------------------------------------------------------------------


class TestDetectAllocationAnomalies:
    def test_team_with_dominant_allocation(self):
        eng = _engine()
        pool = eng.register_pool("shared", 10000.0)
        eng.add_team_allocation(pool.id, "big-team", allocation_pct=70.0)
        eng.add_team_allocation(pool.id, "small-team", allocation_pct=30.0)
        anomalies = eng.detect_allocation_anomalies()
        dominant = [a for a in anomalies if a["type"] == "dominant_allocation"]
        assert len(dominant) == 1
        assert dominant[0]["team_name"] == "big-team"
        assert dominant[0]["allocation_pct"] == 70.0


# ---------------------------------------------------------------------------
# generate_allocation_report
# ---------------------------------------------------------------------------


class TestGenerateAllocationReport:
    def test_basic_report(self):
        eng = _engine()
        pool = eng.register_pool("shared", 10000.0, strategy=AllocationStrategy.EVEN_SPLIT)
        eng.add_team_allocation(pool.id, "team-a", allocation_pct=60.0)
        eng.add_team_allocation(pool.id, "team-b", allocation_pct=40.0)
        report = eng.generate_allocation_report()
        assert report.total_pools == 1
        assert report.total_cost_allocated > 0
        assert report.team_count == 2
        assert AllocationStrategy.EVEN_SPLIT in report.strategy_distribution
        assert report.largest_pool == "shared"
        assert report.generated_at > 0
        assert len(report.recommendations) > 0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        pool = eng.register_pool("shared", 5000.0)
        eng.add_team_allocation(pool.id, "team-a", allocation_pct=50.0)
        assert len(eng._pools) == 1
        assert len(eng._allocations) == 1
        eng.clear_data()
        assert len(eng._pools) == 0
        assert len(eng._allocations) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_pools"] == 0
        assert stats["total_allocations"] == 0
        assert stats["unique_teams"] == 0
        assert stats["category_distribution"] == {}
        assert stats["strategy_distribution"] == {}
        assert stats["team_allocation_counts"] == {}

    def test_populated(self):
        eng = _engine()
        pool = eng.register_pool("shared", 8000.0)
        eng.add_team_allocation(pool.id, "team-a", allocation_pct=50.0)
        stats = eng.get_stats()
        assert stats["total_pools"] == 1
        assert stats["total_allocations"] == 1
        assert stats["unique_teams"] == 1
        assert stats["max_pools"] == 50000
        assert stats["min_allocation_threshold"] == 0.01
