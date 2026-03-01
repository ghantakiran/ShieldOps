"""Tests for shieldops.billing.cost_alloc_validator — CostAllocationValidator."""

from __future__ import annotations

from shieldops.billing.cost_alloc_validator import (
    AllocationRecord,
    AllocationRule,
    AllocationStatus,
    AllocationType,
    CostAllocationReport,
    CostAllocationValidator,
    CostCategory,
)


def _engine(**kw) -> CostAllocationValidator:
    return CostAllocationValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_direct(self):
        assert AllocationType.DIRECT == "direct"

    def test_type_shared(self):
        assert AllocationType.SHARED == "shared"

    def test_type_proportional(self):
        assert AllocationType.PROPORTIONAL == "proportional"

    def test_type_fixed(self):
        assert AllocationType.FIXED == "fixed"

    def test_type_usage_based(self):
        assert AllocationType.USAGE_BASED == "usage_based"

    def test_status_valid(self):
        assert AllocationStatus.VALID == "valid"

    def test_status_invalid(self):
        assert AllocationStatus.INVALID == "invalid"

    def test_status_pending_review(self):
        assert AllocationStatus.PENDING_REVIEW == "pending_review"

    def test_status_adjusted(self):
        assert AllocationStatus.ADJUSTED == "adjusted"

    def test_status_disputed(self):
        assert AllocationStatus.DISPUTED == "disputed"

    def test_category_compute(self):
        assert CostCategory.COMPUTE == "compute"

    def test_category_storage(self):
        assert CostCategory.STORAGE == "storage"

    def test_category_network(self):
        assert CostCategory.NETWORK == "network"

    def test_category_license(self):
        assert CostCategory.LICENSE == "license"

    def test_category_support(self):
        assert CostCategory.SUPPORT == "support"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_allocation_record_defaults(self):
        r = AllocationRecord()
        assert r.id
        assert r.service_name == ""
        assert r.allocation_type == AllocationType.DIRECT
        assert r.status == AllocationStatus.PENDING_REVIEW
        assert r.cost_category == CostCategory.COMPUTE
        assert r.allocated_amount == 0.0
        assert r.actual_amount == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_allocation_rule_defaults(self):
        r = AllocationRule()
        assert r.id
        assert r.service_pattern == ""
        assert r.allocation_type == AllocationType.DIRECT
        assert r.cost_category == CostCategory.COMPUTE
        assert r.allocation_pct == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_cost_allocation_report_defaults(self):
        r = CostAllocationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.valid_allocations == 0
        assert r.variance_pct == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.high_variance == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_allocation
# ---------------------------------------------------------------------------


class TestRecordAllocation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_allocation(
            service_name="api-gateway",
            allocation_type=AllocationType.SHARED,
            status=AllocationStatus.VALID,
            cost_category=CostCategory.COMPUTE,
            allocated_amount=1000.0,
            actual_amount=1050.0,
            team="platform",
        )
        assert r.service_name == "api-gateway"
        assert r.allocation_type == AllocationType.SHARED
        assert r.status == AllocationStatus.VALID
        assert r.cost_category == CostCategory.COMPUTE
        assert r.allocated_amount == 1000.0
        assert r.actual_amount == 1050.0
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_allocation(service_name=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_allocation
# ---------------------------------------------------------------------------


class TestGetAllocation:
    def test_found(self):
        eng = _engine()
        r = eng.record_allocation(
            service_name="api-gateway",
            status=AllocationStatus.VALID,
        )
        result = eng.get_allocation(r.id)
        assert result is not None
        assert result.status == AllocationStatus.VALID

    def test_not_found(self):
        eng = _engine()
        assert eng.get_allocation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_allocations
# ---------------------------------------------------------------------------


class TestListAllocations:
    def test_list_all(self):
        eng = _engine()
        eng.record_allocation(service_name="svc-1")
        eng.record_allocation(service_name="svc-2")
        assert len(eng.list_allocations()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_allocation(
            service_name="svc-1",
            allocation_type=AllocationType.SHARED,
        )
        eng.record_allocation(
            service_name="svc-2",
            allocation_type=AllocationType.FIXED,
        )
        results = eng.list_allocations(allocation_type=AllocationType.SHARED)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_allocation(
            service_name="svc-1",
            status=AllocationStatus.VALID,
        )
        eng.record_allocation(
            service_name="svc-2",
            status=AllocationStatus.INVALID,
        )
        results = eng.list_allocations(status=AllocationStatus.VALID)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_allocation(service_name="svc-1", team="sre")
        eng.record_allocation(service_name="svc-2", team="platform")
        results = eng.list_allocations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_allocation(service_name=f"svc-{i}")
        assert len(eng.list_allocations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        r = eng.add_rule(
            service_pattern="api-*",
            allocation_type=AllocationType.PROPORTIONAL,
            cost_category=CostCategory.NETWORK,
            allocation_pct=25.0,
            description="API traffic split",
        )
        assert r.service_pattern == "api-*"
        assert r.allocation_type == AllocationType.PROPORTIONAL
        assert r.cost_category == CostCategory.NETWORK
        assert r.allocation_pct == 25.0
        assert r.description == "API traffic split"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(service_pattern=f"pat-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_allocation_accuracy
# ---------------------------------------------------------------------------


class TestAnalyzeAllocationAccuracy:
    def test_with_data(self):
        eng = _engine()
        eng.record_allocation(
            service_name="svc-1",
            allocation_type=AllocationType.DIRECT,
            allocated_amount=100.0,
            actual_amount=110.0,
        )
        eng.record_allocation(
            service_name="svc-2",
            allocation_type=AllocationType.DIRECT,
            allocated_amount=200.0,
            actual_amount=220.0,
        )
        result = eng.analyze_allocation_accuracy()
        assert "direct" in result
        assert result["direct"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_allocation_accuracy() == {}


# ---------------------------------------------------------------------------
# identify_high_variance
# ---------------------------------------------------------------------------


class TestIdentifyHighVariance:
    def test_detects_high_variance(self):
        eng = _engine(max_variance_pct=10.0)
        eng.record_allocation(
            service_name="svc-1",
            allocated_amount=100.0,
            actual_amount=150.0,
        )
        eng.record_allocation(
            service_name="svc-2",
            allocated_amount=100.0,
            actual_amount=105.0,
        )
        results = eng.identify_high_variance()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-1"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_variance() == []


# ---------------------------------------------------------------------------
# rank_by_variance
# ---------------------------------------------------------------------------


class TestRankByVariance:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_allocation(service_name="svc-1", team="sre")
        eng.record_allocation(service_name="svc-2", team="sre")
        eng.record_allocation(service_name="svc-3", team="platform")
        results = eng.rank_by_variance()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["allocation_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_variance() == []


# ---------------------------------------------------------------------------
# detect_allocation_trends
# ---------------------------------------------------------------------------


class TestDetectAllocationTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [10.0, 10.0, 10.0, 10.0]:
            eng.add_rule(service_pattern="p", allocation_pct=pct)
        result = eng.detect_allocation_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for pct in [5.0, 5.0, 20.0, 20.0]:
            eng.add_rule(service_pattern="p", allocation_pct=pct)
        result = eng.detect_allocation_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_allocation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_variance_pct=5.0)
        eng.record_allocation(
            service_name="svc-1",
            allocation_type=AllocationType.DIRECT,
            status=AllocationStatus.VALID,
            cost_category=CostCategory.COMPUTE,
            allocated_amount=100.0,
            actual_amount=120.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, CostAllocationReport)
        assert report.total_records == 1
        assert report.valid_allocations == 1
        assert report.variance_pct == 20.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_allocation(service_name="svc-1")
        eng.add_rule(service_pattern="p1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_allocation(
            service_name="api-gateway",
            allocation_type=AllocationType.SHARED,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "shared" in stats["type_distribution"]
