"""Tests for shieldops.billing.budget_manager — InfrastructureCostBudgetManager."""

from __future__ import annotations

from shieldops.billing.budget_manager import (
    Budget,
    BudgetPeriod,
    BudgetStatus,
    BurnRateReport,
    InfrastructureCostBudgetManager,
    SpendCategory,
    SpendEntry,
)


def _engine(**kw) -> InfrastructureCostBudgetManager:
    return InfrastructureCostBudgetManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_period_monthly(self):
        assert BudgetPeriod.MONTHLY == "monthly"

    def test_period_quarterly(self):
        assert BudgetPeriod.QUARTERLY == "quarterly"

    def test_period_annual(self):
        assert BudgetPeriod.ANNUAL == "annual"

    def test_status_on_track(self):
        assert BudgetStatus.ON_TRACK == "on_track"

    def test_status_warning(self):
        assert BudgetStatus.WARNING == "warning"

    def test_status_over_budget(self):
        assert BudgetStatus.OVER_BUDGET == "over_budget"

    def test_status_exhausted(self):
        assert BudgetStatus.EXHAUSTED == "exhausted"

    def test_category_compute(self):
        assert SpendCategory.COMPUTE == "compute"

    def test_category_storage(self):
        assert SpendCategory.STORAGE == "storage"

    def test_category_network(self):
        assert SpendCategory.NETWORK == "network"

    def test_category_database(self):
        assert SpendCategory.DATABASE == "database"

    def test_category_other(self):
        assert SpendCategory.OTHER == "other"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_budget_defaults(self):
        b = Budget(name="team-a-budget")
        assert b.id
        assert b.name == "team-a-budget"
        assert b.period == BudgetPeriod.MONTHLY
        assert b.status == BudgetStatus.ON_TRACK
        assert b.limit_amount == 0.0
        assert b.spent_amount == 0.0
        assert b.owner == ""
        assert b.team == ""

    def test_spend_entry_defaults(self):
        e = SpendEntry(budget_id="b-1", amount=100.0)
        assert e.id
        assert e.category == SpendCategory.OTHER
        assert e.description == ""

    def test_burn_rate_defaults(self):
        r = BurnRateReport(budget_id="b-1")
        assert r.burn_rate_per_day == 0.0
        assert r.days_remaining is None
        assert r.remaining == 0.0
        assert r.spent_amount == 0.0
        assert r.status == BudgetStatus.ON_TRACK


# ---------------------------------------------------------------------------
# create_budget
# ---------------------------------------------------------------------------


class TestCreateBudget:
    def test_basic_create(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        assert budget.name == "team-a"
        assert budget.limit_amount == 10000.0
        assert eng.get_budget(budget.id) is not None

    def test_unique_ids(self):
        eng = _engine()
        b1 = eng.create_budget("team-a", 10000.0)
        b2 = eng.create_budget("team-b", 5000.0)
        assert b1.id != b2.id

    def test_evicts_at_max(self):
        eng = _engine(max_budgets=2)
        b1 = eng.create_budget("t-1", 100.0)
        eng.create_budget("t-2", 200.0)
        eng.create_budget("t-3", 300.0)
        assert eng.get_budget(b1.id) is None

    def test_create_with_kwargs(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 5000.0, team="platform", owner="alice")
        assert budget.team == "platform"
        assert budget.owner == "alice"

    def test_get_budget_not_found(self):
        eng = _engine()
        assert eng.get_budget("nonexistent") is None


# ---------------------------------------------------------------------------
# list_budgets
# ---------------------------------------------------------------------------


class TestListBudgets:
    def test_list_all(self):
        eng = _engine()
        eng.create_budget("t-a", 100.0, team="platform")
        eng.create_budget("t-b", 200.0, team="infra")
        assert len(eng.list_budgets()) == 2

    def test_filter_by_team(self):
        eng = _engine()
        eng.create_budget("t-a", 100.0, team="platform")
        eng.create_budget("t-b", 200.0, team="infra")
        results = eng.list_budgets(team="platform")
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        b1 = eng.create_budget("t-a", 1000.0)
        eng.create_budget("t-b", 10000.0)
        eng.record_spend(b1.id, 1000.0)
        results = eng.list_budgets(status=BudgetStatus.EXHAUSTED)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# record_spend
# ---------------------------------------------------------------------------


class TestRecordSpend:
    def test_basic_spend(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        entry = eng.record_spend(budget.id, 1000.0, category=SpendCategory.COMPUTE)
        assert entry is not None
        assert entry.amount == 1000.0
        assert eng.get_budget(budget.id).spent_amount == 1000.0

    def test_spend_not_found(self):
        eng = _engine()
        assert eng.record_spend("nonexistent", 100.0) is None

    def test_warning_threshold(self):
        eng = _engine(warning_threshold=0.8)
        budget = eng.create_budget("team-a", 1000.0)
        eng.record_spend(budget.id, 850.0)
        assert eng.get_budget(budget.id).status == BudgetStatus.WARNING

    def test_exhausted(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 1000.0)
        eng.record_spend(budget.id, 1000.0)
        assert eng.get_budget(budget.id).status == BudgetStatus.EXHAUSTED

    def test_over_budget(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 1000.0)
        eng.record_spend(budget.id, 960.0)
        assert eng.get_budget(budget.id).status == BudgetStatus.OVER_BUDGET

    def test_cumulative_spend(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        eng.record_spend(budget.id, 100.0)
        eng.record_spend(budget.id, 200.0)
        assert eng.get_budget(budget.id).spent_amount == 300.0

    def test_spend_with_description(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        entry = eng.record_spend(budget.id, 500.0, description="GPU instances")
        assert entry.description == "GPU instances"


# ---------------------------------------------------------------------------
# burn rate
# ---------------------------------------------------------------------------


class TestComputeBurnRate:
    def test_basic_burn_rate(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        eng.record_spend(budget.id, 1000.0)
        report = eng.compute_burn_rate(budget.id)
        assert report is not None
        assert report.spent_amount == 1000.0
        assert report.remaining == 9000.0

    def test_not_found(self):
        eng = _engine()
        assert eng.compute_burn_rate("nonexistent") is None

    def test_no_entries(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        report = eng.compute_burn_rate(budget.id)
        assert report.burn_rate_per_day == 0.0
        assert report.remaining == 10000.0

    def test_burn_rate_includes_budget_name(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        report = eng.compute_burn_rate(budget.id)
        assert report.budget_name == "team-a"


# ---------------------------------------------------------------------------
# adjust_limit / check_status / over_budget / stats
# ---------------------------------------------------------------------------


class TestAdjustLimit:
    def test_adjust(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        result = eng.adjust_limit(budget.id, 5000.0)
        assert result is not None
        assert result.limit_amount == 5000.0

    def test_adjust_not_found(self):
        eng = _engine()
        assert eng.adjust_limit("nonexistent", 5000.0) is None

    def test_adjust_triggers_status_update(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        eng.record_spend(budget.id, 900.0)
        assert eng.get_budget(budget.id).status == BudgetStatus.ON_TRACK
        eng.adjust_limit(budget.id, 1000.0)
        assert eng.get_budget(budget.id).status == BudgetStatus.WARNING


class TestCheckStatus:
    def test_check(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        status = eng.check_budget_status(budget.id)
        assert status == BudgetStatus.ON_TRACK

    def test_not_found(self):
        eng = _engine()
        assert eng.check_budget_status("nonexistent") is None


class TestOverBudgetAlerts:
    def test_alerts(self):
        eng = _engine()
        b1 = eng.create_budget("team-a", 1000.0)
        eng.create_budget("team-b", 10000.0)
        eng.record_spend(b1.id, 1000.0)
        alerts = eng.get_over_budget_alerts()
        assert len(alerts) == 1

    def test_no_alerts(self):
        eng = _engine()
        eng.create_budget("team-a", 10000.0)
        assert eng.get_over_budget_alerts() == []

    def test_both_over_and_exhausted(self):
        eng = _engine()
        b1 = eng.create_budget("team-a", 1000.0)
        b2 = eng.create_budget("team-b", 1000.0)
        eng.record_spend(b1.id, 1000.0)  # exhausted
        eng.record_spend(b2.id, 960.0)  # over_budget
        alerts = eng.get_over_budget_alerts()
        assert len(alerts) == 2


class TestListSpendEntries:
    def test_list_entries(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        eng.record_spend(budget.id, 100.0)
        eng.record_spend(budget.id, 200.0)
        entries = eng.list_spend_entries(budget.id)
        assert len(entries) == 2

    def test_filter_by_category(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 10000.0)
        eng.record_spend(budget.id, 100.0, category=SpendCategory.COMPUTE)
        eng.record_spend(budget.id, 200.0, category=SpendCategory.STORAGE)
        entries = eng.list_spend_entries(budget.id, category=SpendCategory.COMPUTE)
        assert len(entries) == 1

    def test_limit(self):
        eng = _engine()
        budget = eng.create_budget("team-a", 100000.0)
        for _ in range(10):
            eng.record_spend(budget.id, 10.0)
        entries = eng.list_spend_entries(budget.id, limit=3)
        assert len(entries) == 3


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_budgets"] == 0
        assert stats["total_entries"] == 0
        assert stats["total_limit"] == 0.0
        assert stats["total_spent"] == 0.0

    def test_populated_stats(self):
        eng = _engine()
        b = eng.create_budget("team-a", 10000.0)
        eng.record_spend(b.id, 500.0)
        stats = eng.get_stats()
        assert stats["total_budgets"] == 1
        assert stats["total_entries"] == 1
        assert stats["total_spent"] == 500.0
        assert stats["total_limit"] == 10000.0

    def test_period_distribution(self):
        eng = _engine()
        eng.create_budget("t-a", 1000.0, period=BudgetPeriod.MONTHLY)
        eng.create_budget("t-b", 5000.0, period=BudgetPeriod.QUARTERLY)
        stats = eng.get_stats()
        assert stats["period_distribution"][BudgetPeriod.MONTHLY] == 1
        assert stats["period_distribution"][BudgetPeriod.QUARTERLY] == 1
