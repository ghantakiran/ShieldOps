"""Tests for shieldops.observability.observability_budget_planner — ObservabilityBudgetPlanner."""

from __future__ import annotations

from shieldops.observability.observability_budget_planner import (
    BudgetAllocation,
    BudgetCategory,
    BudgetPeriod,
    BudgetRecord,
    ObservabilityBudgetPlanner,
    ObservabilityBudgetReport,
    SpendLevel,
)


def _engine(**kw) -> ObservabilityBudgetPlanner:
    return ObservabilityBudgetPlanner(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_metrics(self):
        assert BudgetCategory.METRICS == "metrics"

    def test_category_logs(self):
        assert BudgetCategory.LOGS == "logs"

    def test_category_traces(self):
        assert BudgetCategory.TRACES == "traces"

    def test_category_alerts(self):
        assert BudgetCategory.ALERTS == "alerts"

    def test_category_dashboards(self):
        assert BudgetCategory.DASHBOARDS == "dashboards"

    def test_spend_under_budget(self):
        assert SpendLevel.UNDER_BUDGET == "under_budget"

    def test_spend_on_budget(self):
        assert SpendLevel.ON_BUDGET == "on_budget"

    def test_spend_approaching_limit(self):
        assert SpendLevel.APPROACHING_LIMIT == "approaching_limit"

    def test_spend_over_budget(self):
        assert SpendLevel.OVER_BUDGET == "over_budget"

    def test_spend_critical(self):
        assert SpendLevel.CRITICAL == "critical"

    def test_period_daily(self):
        assert BudgetPeriod.DAILY == "daily"

    def test_period_weekly(self):
        assert BudgetPeriod.WEEKLY == "weekly"

    def test_period_monthly(self):
        assert BudgetPeriod.MONTHLY == "monthly"

    def test_period_quarterly(self):
        assert BudgetPeriod.QUARTERLY == "quarterly"

    def test_period_annual(self):
        assert BudgetPeriod.ANNUAL == "annual"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_budget_record_defaults(self):
        r = BudgetRecord()
        assert r.id
        assert r.budget_id == ""
        assert r.budget_category == BudgetCategory.METRICS
        assert r.spend_level == SpendLevel.ON_BUDGET
        assert r.budget_period == BudgetPeriod.MONTHLY
        assert r.spend_amount == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_budget_allocation_defaults(self):
        a = BudgetAllocation()
        assert a.id
        assert a.budget_id == ""
        assert a.budget_category == BudgetCategory.METRICS
        assert a.allocation_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ObservabilityBudgetReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_allocations == 0
        assert r.over_budget_count == 0
        assert r.avg_spend_amount == 0.0
        assert r.by_category == {}
        assert r.by_spend_level == {}
        assert r.by_period == {}
        assert r.top_overspenders == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_budget
# ---------------------------------------------------------------------------


class TestRecordBudget:
    def test_basic(self):
        eng = _engine()
        r = eng.record_budget(
            budget_id="BUD-001",
            budget_category=BudgetCategory.LOGS,
            spend_level=SpendLevel.OVER_BUDGET,
            budget_period=BudgetPeriod.MONTHLY,
            spend_amount=15000.0,
            service="log-aggregator",
            team="platform",
        )
        assert r.budget_id == "BUD-001"
        assert r.budget_category == BudgetCategory.LOGS
        assert r.spend_level == SpendLevel.OVER_BUDGET
        assert r.budget_period == BudgetPeriod.MONTHLY
        assert r.spend_amount == 15000.0
        assert r.service == "log-aggregator"
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_budget(budget_id=f"BUD-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_budget
# ---------------------------------------------------------------------------


class TestGetBudget:
    def test_found(self):
        eng = _engine()
        r = eng.record_budget(
            budget_id="BUD-001",
            spend_level=SpendLevel.CRITICAL,
        )
        result = eng.get_budget(r.id)
        assert result is not None
        assert result.spend_level == SpendLevel.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_budget("nonexistent") is None


# ---------------------------------------------------------------------------
# list_budgets
# ---------------------------------------------------------------------------


class TestListBudgets:
    def test_list_all(self):
        eng = _engine()
        eng.record_budget(budget_id="BUD-001")
        eng.record_budget(budget_id="BUD-002")
        assert len(eng.list_budgets()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_budget(
            budget_id="BUD-001",
            budget_category=BudgetCategory.METRICS,
        )
        eng.record_budget(
            budget_id="BUD-002",
            budget_category=BudgetCategory.LOGS,
        )
        results = eng.list_budgets(
            budget_category=BudgetCategory.METRICS,
        )
        assert len(results) == 1

    def test_filter_by_spend_level(self):
        eng = _engine()
        eng.record_budget(
            budget_id="BUD-001",
            spend_level=SpendLevel.OVER_BUDGET,
        )
        eng.record_budget(
            budget_id="BUD-002",
            spend_level=SpendLevel.UNDER_BUDGET,
        )
        results = eng.list_budgets(
            spend_level=SpendLevel.OVER_BUDGET,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_budget(budget_id="BUD-001", team="sre")
        eng.record_budget(budget_id="BUD-002", team="platform")
        results = eng.list_budgets(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_budget(budget_id=f"BUD-{i}")
        assert len(eng.list_budgets(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_allocation
# ---------------------------------------------------------------------------


class TestAddAllocation:
    def test_basic(self):
        eng = _engine()
        a = eng.add_allocation(
            budget_id="BUD-001",
            budget_category=BudgetCategory.TRACES,
            allocation_score=88.0,
            threshold=75.0,
            breached=False,
            description="Within allocation",
        )
        assert a.budget_id == "BUD-001"
        assert a.budget_category == BudgetCategory.TRACES
        assert a.allocation_score == 88.0
        assert a.threshold == 75.0
        assert a.breached is False

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_allocation(budget_id=f"BUD-{i}")
        assert len(eng._allocations) == 2


# ---------------------------------------------------------------------------
# analyze_budget_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeBudgetDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_budget(
            budget_id="BUD-001",
            budget_category=BudgetCategory.METRICS,
            spend_amount=1000.0,
        )
        eng.record_budget(
            budget_id="BUD-002",
            budget_category=BudgetCategory.METRICS,
            spend_amount=2000.0,
        )
        result = eng.analyze_budget_distribution()
        assert "metrics" in result
        assert result["metrics"]["count"] == 2
        assert result["metrics"]["avg_spend_amount"] == 1500.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_budget_distribution() == {}


# ---------------------------------------------------------------------------
# identify_over_budget
# ---------------------------------------------------------------------------


class TestIdentifyOverBudget:
    def test_detects_over_budget(self):
        eng = _engine()
        eng.record_budget(
            budget_id="BUD-001",
            spend_level=SpendLevel.OVER_BUDGET,
            spend_amount=20000.0,
        )
        eng.record_budget(
            budget_id="BUD-002",
            spend_level=SpendLevel.UNDER_BUDGET,
            spend_amount=5000.0,
        )
        results = eng.identify_over_budget()
        assert len(results) == 1
        assert results[0]["budget_id"] == "BUD-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_over_budget() == []


# ---------------------------------------------------------------------------
# rank_by_spend
# ---------------------------------------------------------------------------


class TestRankBySpend:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_budget(
            budget_id="BUD-001",
            service="expensive-svc",
            spend_amount=50000.0,
        )
        eng.record_budget(
            budget_id="BUD-002",
            service="cheap-svc",
            spend_amount=1000.0,
        )
        results = eng.rank_by_spend()
        assert len(results) == 2
        assert results[0]["service"] == "expensive-svc"
        assert results[0]["avg_spend_amount"] == 50000.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_spend() == []


# ---------------------------------------------------------------------------
# detect_budget_trends
# ---------------------------------------------------------------------------


class TestDetectBudgetTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_allocation(budget_id="BUD-001", allocation_score=50.0)
        result = eng.detect_budget_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_allocation(budget_id="BUD-001", allocation_score=30.0)
        eng.add_allocation(budget_id="BUD-002", allocation_score=30.0)
        eng.add_allocation(budget_id="BUD-003", allocation_score=80.0)
        eng.add_allocation(budget_id="BUD-004", allocation_score=80.0)
        result = eng.detect_budget_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_budget_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_budget(
            budget_id="BUD-001",
            budget_category=BudgetCategory.LOGS,
            spend_level=SpendLevel.OVER_BUDGET,
            budget_period=BudgetPeriod.MONTHLY,
            spend_amount=15000.0,
            service="log-aggregator",
        )
        report = eng.generate_report()
        assert isinstance(report, ObservabilityBudgetReport)
        assert report.total_records == 1
        assert report.over_budget_count == 1
        assert len(report.top_overspenders) == 1
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
        eng.record_budget(budget_id="BUD-001")
        eng.add_allocation(budget_id="BUD-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._allocations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_allocations"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_budget(
            budget_id="BUD-001",
            budget_category=BudgetCategory.METRICS,
            team="sre",
            service="metrics-svc",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "metrics" in stats["category_distribution"]
