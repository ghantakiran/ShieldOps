"""Tests for shieldops.sla.error_budget_forecast — ErrorBudgetForecaster."""

from __future__ import annotations

from shieldops.sla.error_budget_forecast import (
    BudgetForecast,
    BudgetSnapshot,
    BudgetStatus,
    BurnRate,
    ErrorBudgetForecaster,
    ErrorBudgetForecastReport,
    ForecastHorizon,
)


def _engine(**kw) -> ErrorBudgetForecaster:
    return ErrorBudgetForecaster(**kw)


class TestEnums:
    def test_status_healthy(self):
        assert BudgetStatus.HEALTHY == "healthy"

    def test_status_cautious(self):
        assert BudgetStatus.CAUTIOUS == "cautious"

    def test_status_at_risk(self):
        assert BudgetStatus.AT_RISK == "at_risk"

    def test_status_exhausting(self):
        assert BudgetStatus.EXHAUSTING == "exhausting"

    def test_status_exhausted(self):
        assert BudgetStatus.EXHAUSTED == "exhausted"

    def test_burn_slow(self):
        assert BurnRate.SLOW == "slow"

    def test_burn_normal(self):
        assert BurnRate.NORMAL == "normal"

    def test_burn_elevated(self):
        assert BurnRate.ELEVATED == "elevated"

    def test_burn_fast(self):
        assert BurnRate.FAST == "fast"

    def test_burn_critical(self):
        assert BurnRate.CRITICAL == "critical"

    def test_horizon_one_day(self):
        assert ForecastHorizon.ONE_DAY == "one_day"

    def test_horizon_one_week(self):
        assert ForecastHorizon.ONE_WEEK == "one_week"

    def test_horizon_two_weeks(self):
        assert ForecastHorizon.TWO_WEEKS == "two_weeks"

    def test_horizon_one_month(self):
        assert ForecastHorizon.ONE_MONTH == "one_month"

    def test_horizon_one_quarter(self):
        assert ForecastHorizon.ONE_QUARTER == "one_quarter"


class TestModels:
    def test_snapshot_defaults(self):
        r = BudgetSnapshot()
        assert r.id
        assert r.slo_name == ""
        assert r.budget_remaining_pct == 100.0
        assert r.burn_rate == BurnRate.NORMAL
        assert r.status == BudgetStatus.HEALTHY
        assert r.error_count == 0
        assert r.total_requests == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_forecast_defaults(self):
        r = BudgetForecast()
        assert r.id
        assert r.slo_name == ""
        assert r.horizon == ForecastHorizon.ONE_WEEK
        assert r.projected_remaining_pct == 0.0
        assert r.exhaustion_days == 0.0
        assert r.confidence_pct == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = ErrorBudgetForecastReport()
        assert r.total_snapshots == 0
        assert r.total_forecasts == 0
        assert r.avg_remaining_pct == 0.0
        assert r.by_status == {}
        assert r.by_burn_rate == {}
        assert r.at_risk_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordSnapshot:
    def test_basic(self):
        eng = _engine()
        r = eng.record_snapshot("slo-a", budget_remaining_pct=90.0)
        assert r.slo_name == "slo-a"
        assert r.status == BudgetStatus.HEALTHY

    def test_auto_status_at_risk(self):
        eng = _engine()
        r = eng.record_snapshot("slo-b", budget_remaining_pct=35.0)
        assert r.status == BudgetStatus.AT_RISK

    def test_auto_status_exhausted(self):
        eng = _engine()
        r = eng.record_snapshot("slo-c", budget_remaining_pct=0.0)
        assert r.status == BudgetStatus.EXHAUSTED

    def test_explicit_status(self):
        eng = _engine()
        r = eng.record_snapshot("slo-d", status=BudgetStatus.CAUTIOUS)
        assert r.status == BudgetStatus.CAUTIOUS

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_snapshot(f"slo-{i}")
        assert len(eng._records) == 3


class TestGetSnapshot:
    def test_found(self):
        eng = _engine()
        r = eng.record_snapshot("slo-a")
        assert eng.get_snapshot(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_snapshot("nonexistent") is None


class TestListSnapshots:
    def test_list_all(self):
        eng = _engine()
        eng.record_snapshot("slo-a")
        eng.record_snapshot("slo-b")
        assert len(eng.list_snapshots()) == 2

    def test_filter_by_slo(self):
        eng = _engine()
        eng.record_snapshot("slo-a")
        eng.record_snapshot("slo-b")
        results = eng.list_snapshots(slo_name="slo-a")
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_snapshot("slo-a", budget_remaining_pct=90.0)
        eng.record_snapshot("slo-b", budget_remaining_pct=10.0)
        results = eng.list_snapshots(status=BudgetStatus.HEALTHY)
        assert len(results) == 1


class TestCreateForecast:
    def test_basic(self):
        eng = _engine()
        f = eng.create_forecast(
            "slo-a",
            exhaustion_days=14.0,
            confidence_pct=85.0,
        )
        assert f.slo_name == "slo-a"
        assert f.exhaustion_days == 14.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.create_forecast(f"slo-{i}")
        assert len(eng._forecasts) == 2


class TestAnalyzeBudgetHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_snapshot(
            "slo-a",
            budget_remaining_pct=25.0,
            burn_rate=BurnRate.FAST,
        )
        result = eng.analyze_budget_health("slo-a")
        assert result["slo_name"] == "slo-a"
        assert result["burn_rate"] == "fast"

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_budget_health("ghost")
        assert result["status"] == "no_data"


class TestIdentifyAtRiskBudgets:
    def test_with_at_risk(self):
        eng = _engine()
        eng.record_snapshot("slo-a", budget_remaining_pct=90.0)
        eng.record_snapshot("slo-b", budget_remaining_pct=10.0)
        results = eng.identify_at_risk_budgets()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_at_risk_budgets() == []


class TestRankByBurnRate:
    def test_with_data(self):
        eng = _engine()
        eng.record_snapshot("slo-a", burn_rate=BurnRate.SLOW)
        eng.record_snapshot("slo-b", burn_rate=BurnRate.CRITICAL)
        results = eng.rank_by_burn_rate()
        assert results[0]["burn_rate"] == "critical"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_burn_rate() == []


class TestProjectExhaustionTimeline:
    def test_with_data(self):
        eng = _engine()
        eng.create_forecast("slo-a", exhaustion_days=30.0)
        eng.create_forecast("slo-b", exhaustion_days=7.0)
        results = eng.project_exhaustion_timeline()
        assert results[0]["exhaustion_days"] == 7.0

    def test_empty(self):
        eng = _engine()
        assert eng.project_exhaustion_timeline() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_snapshot("slo-a", budget_remaining_pct=10.0)
        eng.record_snapshot("slo-b", burn_rate=BurnRate.CRITICAL)
        eng.create_forecast("slo-a")
        report = eng.generate_report()
        assert report.total_snapshots == 2
        assert report.total_forecasts == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_snapshots == 0
        assert "healthy" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_snapshot("slo-a")
        eng.create_forecast("slo-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._forecasts) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_snapshots"] == 0
        assert stats["total_forecasts"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_snapshot("slo-a", budget_remaining_pct=90.0)
        eng.record_snapshot("slo-b", budget_remaining_pct=10.0)
        eng.create_forecast("slo-a")
        stats = eng.get_stats()
        assert stats["total_snapshots"] == 2
        assert stats["total_forecasts"] == 1
        assert stats["unique_slos"] == 2
