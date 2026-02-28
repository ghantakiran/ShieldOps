"""Tests for shieldops.sla.error_budget_allocator — ErrorBudgetAllocator."""

from __future__ import annotations

from shieldops.sla.error_budget_allocator import (
    AllocationPolicy,
    AllocationRecord,
    AllocationStrategy,
    BudgetAllocatorReport,
    BudgetStatus,
    ConsumptionRate,
    ErrorBudgetAllocator,
)


def _engine(**kw) -> ErrorBudgetAllocator:
    return ErrorBudgetAllocator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # AllocationStrategy (5)
    def test_strategy_proportional(self):
        assert AllocationStrategy.PROPORTIONAL == "proportional"

    def test_strategy_risk_weighted(self):
        assert AllocationStrategy.RISK_WEIGHTED == "risk_weighted"

    def test_strategy_equal(self):
        assert AllocationStrategy.EQUAL == "equal"

    def test_strategy_priority(self):
        assert AllocationStrategy.PRIORITY_BASED == "priority_based"

    def test_strategy_dynamic(self):
        assert AllocationStrategy.DYNAMIC == "dynamic"

    # BudgetStatus (5)
    def test_status_healthy(self):
        assert BudgetStatus.HEALTHY == "healthy"

    def test_status_warning(self):
        assert BudgetStatus.WARNING == "warning"

    def test_status_critical(self):
        assert BudgetStatus.CRITICAL == "critical"

    def test_status_exhausted(self):
        assert BudgetStatus.EXHAUSTED == "exhausted"

    def test_status_frozen(self):
        assert BudgetStatus.FROZEN == "frozen"

    # ConsumptionRate (5)
    def test_consumption_underspending(self):
        assert ConsumptionRate.UNDERSPENDING == "underspending"

    def test_consumption_normal(self):
        assert ConsumptionRate.NORMAL == "normal"

    def test_consumption_elevated(self):
        assert ConsumptionRate.ELEVATED == "elevated"

    def test_consumption_rapid(self):
        assert ConsumptionRate.RAPID == "rapid"

    def test_consumption_burst(self):
        assert ConsumptionRate.BURST == "burst"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_allocation_record_defaults(self):
        r = AllocationRecord()
        assert r.id
        assert r.service_name == ""
        assert r.strategy == AllocationStrategy.PROPORTIONAL
        assert r.status == BudgetStatus.HEALTHY
        assert r.consumption == ConsumptionRate.NORMAL
        assert r.budget_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_allocation_policy_defaults(self):
        r = AllocationPolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.strategy == AllocationStrategy.PROPORTIONAL
        assert r.status == BudgetStatus.HEALTHY
        assert r.freeze_threshold_pct == 5.0
        assert r.alert_threshold_pct == 20.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = BudgetAllocatorReport()
        assert r.total_allocations == 0
        assert r.total_policies == 0
        assert r.healthy_rate_pct == 0.0
        assert r.by_strategy == {}
        assert r.by_status == {}
        assert r.exhausted_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_allocation
# -------------------------------------------------------------------


class TestRecordAllocation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_allocation(
            "svc-a",
            strategy=(AllocationStrategy.RISK_WEIGHTED),
            status=BudgetStatus.HEALTHY,
        )
        assert r.service_name == "svc-a"
        assert r.strategy == AllocationStrategy.RISK_WEIGHTED

    def test_with_consumption(self):
        eng = _engine()
        r = eng.record_allocation(
            "svc-b",
            consumption=ConsumptionRate.RAPID,
        )
        assert r.consumption == ConsumptionRate.RAPID

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_allocation(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_allocation
# -------------------------------------------------------------------


class TestGetAllocation:
    def test_found(self):
        eng = _engine()
        r = eng.record_allocation("svc-a")
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
        eng.record_allocation("svc-a")
        eng.record_allocation("svc-b")
        assert len(eng.list_allocations()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_allocation("svc-a")
        eng.record_allocation("svc-b")
        results = eng.list_allocations(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_strategy(self):
        eng = _engine()
        eng.record_allocation(
            "svc-a",
            strategy=AllocationStrategy.EQUAL,
        )
        eng.record_allocation(
            "svc-b",
            strategy=(AllocationStrategy.PROPORTIONAL),
        )
        results = eng.list_allocations(strategy=AllocationStrategy.EQUAL)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "budget-freeze",
            strategy=(AllocationStrategy.RISK_WEIGHTED),
            status=BudgetStatus.WARNING,
            freeze_threshold_pct=3.0,
            alert_threshold_pct=15.0,
        )
        assert p.policy_name == "budget-freeze"
        assert p.freeze_threshold_pct == 3.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_budget_health
# -------------------------------------------------------------------


class TestAnalyzeBudgetHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_allocation(
            "svc-a",
            status=BudgetStatus.HEALTHY,
            budget_pct=30.0,
        )
        eng.record_allocation(
            "svc-a",
            status=BudgetStatus.EXHAUSTED,
            budget_pct=90.0,
        )
        result = eng.analyze_budget_health("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["allocation_count"] == 2
        assert result["healthy_count"] == 1
        assert result["healthy_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_budget_health("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_exhausted_budgets
# -------------------------------------------------------------------


class TestIdentifyExhaustedBudgets:
    def test_with_exhausted(self):
        eng = _engine()
        eng.record_allocation(
            "svc-a",
            status=BudgetStatus.EXHAUSTED,
        )
        eng.record_allocation(
            "svc-a",
            status=BudgetStatus.CRITICAL,
        )
        eng.record_allocation(
            "svc-b",
            status=BudgetStatus.HEALTHY,
        )
        results = eng.identify_exhausted_budgets()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_exhausted_budgets() == []


# -------------------------------------------------------------------
# rank_by_budget_usage
# -------------------------------------------------------------------


class TestRankByBudgetUsage:
    def test_with_data(self):
        eng = _engine()
        eng.record_allocation("svc-a", budget_pct=80.0)
        eng.record_allocation("svc-a", budget_pct=60.0)
        eng.record_allocation("svc-b", budget_pct=30.0)
        results = eng.rank_by_budget_usage()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_budget_pct"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_budget_usage() == []


# -------------------------------------------------------------------
# detect_budget_anomalies
# -------------------------------------------------------------------


class TestDetectBudgetAnomalies:
    def test_with_anomalies(self):
        eng = _engine()
        for _ in range(5):
            eng.record_allocation(
                "svc-a",
                status=BudgetStatus.WARNING,
            )
        eng.record_allocation(
            "svc-b",
            status=BudgetStatus.HEALTHY,
        )
        results = eng.detect_budget_anomalies()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["anomaly_detected"] is True

    def test_no_anomalies(self):
        eng = _engine()
        eng.record_allocation(
            "svc-a",
            status=BudgetStatus.WARNING,
        )
        assert eng.detect_budget_anomalies() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_allocation(
            "svc-a",
            status=BudgetStatus.HEALTHY,
        )
        eng.record_allocation(
            "svc-b",
            status=BudgetStatus.EXHAUSTED,
        )
        eng.record_allocation(
            "svc-b",
            status=BudgetStatus.EXHAUSTED,
        )
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_allocations == 3
        assert report.total_policies == 1
        assert report.by_strategy != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_allocations == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_allocation("svc-a")
        eng.add_policy("policy-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_allocations"] == 0
        assert stats["total_policies"] == 0
        assert stats["strategy_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_allocation(
            "svc-a",
            strategy=(AllocationStrategy.PROPORTIONAL),
        )
        eng.record_allocation(
            "svc-b",
            strategy=AllocationStrategy.EQUAL,
        )
        eng.add_policy("p1")
        stats = eng.get_stats()
        assert stats["total_allocations"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_services"] == 2
