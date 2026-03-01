"""Tests for shieldops.billing.cost_allocation_validator — CostAllocationValidator."""

from __future__ import annotations

from shieldops.billing.cost_allocation_validator import (
    AllocationCheck,
    AllocationMethod,
    AllocationRecord,
    AllocationStatus,
    CostAllocationReport,
    CostAllocationValidator,
    CostCenter,
)


def _engine(**kw) -> CostAllocationValidator:
    return CostAllocationValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_valid(self):
        assert AllocationStatus.VALID == "valid"

    def test_status_misattributed(self):
        assert AllocationStatus.MISATTRIBUTED == "misattributed"

    def test_status_unallocated(self):
        assert AllocationStatus.UNALLOCATED == "unallocated"

    def test_status_disputed(self):
        assert AllocationStatus.DISPUTED == "disputed"

    def test_status_pending(self):
        assert AllocationStatus.PENDING == "pending"

    def test_method_tag_based(self):
        assert AllocationMethod.TAG_BASED == "tag_based"

    def test_method_usage_based(self):
        assert AllocationMethod.USAGE_BASED == "usage_based"

    def test_method_proportional(self):
        assert AllocationMethod.PROPORTIONAL == "proportional"

    def test_method_fixed(self):
        assert AllocationMethod.FIXED == "fixed"

    def test_method_hybrid(self):
        assert AllocationMethod.HYBRID == "hybrid"

    def test_center_engineering(self):
        assert CostCenter.ENGINEERING == "engineering"

    def test_center_operations(self):
        assert CostCenter.OPERATIONS == "operations"

    def test_center_security(self):
        assert CostCenter.SECURITY == "security"

    def test_center_data(self):
        assert CostCenter.DATA == "data"

    def test_center_infrastructure(self):
        assert CostCenter.INFRASTRUCTURE == "infrastructure"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_allocation_record_defaults(self):
        r = AllocationRecord()
        assert r.id
        assert r.allocation_id == ""
        assert r.allocation_status == AllocationStatus.PENDING
        assert r.allocation_method == AllocationMethod.TAG_BASED
        assert r.cost_center == CostCenter.ENGINEERING
        assert r.accuracy_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_allocation_check_defaults(self):
        c = AllocationCheck()
        assert c.id
        assert c.allocation_id == ""
        assert c.allocation_status == AllocationStatus.PENDING
        assert c.check_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_cost_allocation_report_defaults(self):
        r = CostAllocationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_checks == 0
        assert r.invalid_count == 0
        assert r.avg_accuracy_pct == 0.0
        assert r.by_status == {}
        assert r.by_method == {}
        assert r.by_center == {}
        assert r.top_invalid == []
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
            allocation_id="ALC-001",
            allocation_status=AllocationStatus.MISATTRIBUTED,
            allocation_method=AllocationMethod.USAGE_BASED,
            cost_center=CostCenter.OPERATIONS,
            accuracy_pct=65.0,
            service="api-gateway",
            team="sre",
        )
        assert r.allocation_id == "ALC-001"
        assert r.allocation_status == AllocationStatus.MISATTRIBUTED
        assert r.allocation_method == AllocationMethod.USAGE_BASED
        assert r.cost_center == CostCenter.OPERATIONS
        assert r.accuracy_pct == 65.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_allocation(allocation_id=f"ALC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_allocation
# ---------------------------------------------------------------------------


class TestGetAllocation:
    def test_found(self):
        eng = _engine()
        r = eng.record_allocation(
            allocation_id="ALC-001",
            allocation_status=AllocationStatus.VALID,
        )
        result = eng.get_allocation(r.id)
        assert result is not None
        assert result.allocation_status == AllocationStatus.VALID

    def test_not_found(self):
        eng = _engine()
        assert eng.get_allocation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_allocations
# ---------------------------------------------------------------------------


class TestListAllocations:
    def test_list_all(self):
        eng = _engine()
        eng.record_allocation(allocation_id="ALC-001")
        eng.record_allocation(allocation_id="ALC-002")
        assert len(eng.list_allocations()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_allocation(
            allocation_id="ALC-001",
            allocation_status=AllocationStatus.MISATTRIBUTED,
        )
        eng.record_allocation(
            allocation_id="ALC-002",
            allocation_status=AllocationStatus.VALID,
        )
        results = eng.list_allocations(
            allocation_status=AllocationStatus.MISATTRIBUTED,
        )
        assert len(results) == 1

    def test_filter_by_method(self):
        eng = _engine()
        eng.record_allocation(
            allocation_id="ALC-001",
            allocation_method=AllocationMethod.TAG_BASED,
        )
        eng.record_allocation(
            allocation_id="ALC-002",
            allocation_method=AllocationMethod.USAGE_BASED,
        )
        results = eng.list_allocations(
            allocation_method=AllocationMethod.TAG_BASED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_allocation(allocation_id="ALC-001", team="sre")
        eng.record_allocation(allocation_id="ALC-002", team="platform")
        results = eng.list_allocations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_allocation(allocation_id=f"ALC-{i}")
        assert len(eng.list_allocations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_check
# ---------------------------------------------------------------------------


class TestAddCheck:
    def test_basic(self):
        eng = _engine()
        c = eng.add_check(
            allocation_id="ALC-001",
            allocation_status=AllocationStatus.MISATTRIBUTED,
            check_score=45.0,
            threshold=90.0,
            breached=True,
            description="Cost misattributed to wrong team",
        )
        assert c.allocation_id == "ALC-001"
        assert c.allocation_status == AllocationStatus.MISATTRIBUTED
        assert c.check_score == 45.0
        assert c.threshold == 90.0
        assert c.breached is True
        assert c.description == "Cost misattributed to wrong team"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_check(allocation_id=f"ALC-{i}")
        assert len(eng._checks) == 2


# ---------------------------------------------------------------------------
# analyze_allocation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeAllocationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_allocation(
            allocation_id="ALC-001",
            allocation_status=AllocationStatus.MISATTRIBUTED,
            accuracy_pct=60.0,
        )
        eng.record_allocation(
            allocation_id="ALC-002",
            allocation_status=AllocationStatus.MISATTRIBUTED,
            accuracy_pct=70.0,
        )
        result = eng.analyze_allocation_distribution()
        assert "misattributed" in result
        assert result["misattributed"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_allocation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_invalid_allocations
# ---------------------------------------------------------------------------


class TestIdentifyInvalidAllocations:
    def test_detects_invalid(self):
        eng = _engine()
        eng.record_allocation(
            allocation_id="ALC-001",
            allocation_status=AllocationStatus.MISATTRIBUTED,
        )
        eng.record_allocation(
            allocation_id="ALC-002",
            allocation_status=AllocationStatus.VALID,
        )
        results = eng.identify_invalid_allocations()
        assert len(results) == 1
        assert results[0]["allocation_id"] == "ALC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_invalid_allocations() == []


# ---------------------------------------------------------------------------
# rank_by_accuracy
# ---------------------------------------------------------------------------


class TestRankByAccuracy:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_allocation(
            allocation_id="ALC-001",
            service="api-gateway",
            accuracy_pct=95.0,
        )
        eng.record_allocation(
            allocation_id="ALC-002",
            service="payments",
            accuracy_pct=60.0,
        )
        results = eng.rank_by_accuracy()
        assert len(results) == 2
        assert results[0]["service"] == "payments"
        assert results[0]["avg_accuracy_pct"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_accuracy() == []


# ---------------------------------------------------------------------------
# detect_allocation_trends
# ---------------------------------------------------------------------------


class TestDetectAllocationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_check(
                allocation_id="ALC-001",
                check_score=50.0,
            )
        result = eng.detect_allocation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_check(allocation_id="ALC-001", check_score=30.0)
        eng.add_check(allocation_id="ALC-002", check_score=30.0)
        eng.add_check(allocation_id="ALC-003", check_score=80.0)
        eng.add_check(allocation_id="ALC-004", check_score=80.0)
        result = eng.detect_allocation_trends()
        assert result["trend"] == "improving"
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
        eng = _engine()
        eng.record_allocation(
            allocation_id="ALC-001",
            allocation_status=AllocationStatus.MISATTRIBUTED,
            allocation_method=AllocationMethod.USAGE_BASED,
            cost_center=CostCenter.OPERATIONS,
            accuracy_pct=65.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CostAllocationReport)
        assert report.total_records == 1
        assert report.invalid_count == 1
        assert len(report.top_invalid) == 1
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
        eng.record_allocation(allocation_id="ALC-001")
        eng.add_check(allocation_id="ALC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._checks) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_checks"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_allocation(
            allocation_id="ALC-001",
            allocation_status=AllocationStatus.MISATTRIBUTED,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "misattributed" in stats["status_distribution"]
