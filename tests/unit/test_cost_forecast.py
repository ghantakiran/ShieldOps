"""Tests for shieldops.billing.cost_forecast — CostForecastEngine."""

from __future__ import annotations

import pytest

from shieldops.billing.cost_forecast import (
    BudgetAlert,
    CostDataPoint,
    CostForecast,
    CostForecastEngine,
    ForecastConfidence,
    ForecastMethod,
)


def _engine(**kw) -> CostForecastEngine:
    return CostForecastEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ForecastMethod (3 values)

    def test_forecast_method_linear(self):
        assert ForecastMethod.LINEAR == "linear"

    def test_forecast_method_moving_average(self):
        assert ForecastMethod.MOVING_AVERAGE == "moving_average"

    def test_forecast_method_exponential(self):
        assert ForecastMethod.EXPONENTIAL == "exponential"

    # ForecastConfidence (3 values)

    def test_forecast_confidence_high(self):
        assert ForecastConfidence.HIGH == "high"

    def test_forecast_confidence_medium(self):
        assert ForecastConfidence.MEDIUM == "medium"

    def test_forecast_confidence_low(self):
        assert ForecastConfidence.LOW == "low"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cost_data_point_defaults(self):
        dp = CostDataPoint(service="web", amount=100.0)
        assert dp.id
        assert dp.service == "web"
        assert dp.amount == 100.0
        assert dp.currency == "USD"
        assert dp.period == ""
        assert dp.recorded_at > 0

    def test_cost_forecast_defaults(self):
        fc = CostForecast(
            service="web",
            method=ForecastMethod.LINEAR,
        )
        assert fc.id
        assert fc.predicted_amount == 0.0
        assert fc.confidence == ForecastConfidence.MEDIUM
        assert fc.lower_bound == 0.0
        assert fc.upper_bound == 0.0
        assert fc.data_points_used == 0
        assert fc.period == ""
        assert fc.generated_at > 0

    def test_budget_alert_defaults(self):
        alert = BudgetAlert(
            service="web",
            budget_limit=1000.0,
            forecasted_amount=1200.0,
        )
        assert alert.id
        assert alert.overage_pct == 0.0
        assert alert.message == ""
        assert alert.triggered_at > 0


# ---------------------------------------------------------------------------
# record_cost
# ---------------------------------------------------------------------------


class TestRecordCost:
    def test_basic_record(self):
        eng = _engine()
        dp = eng.record_cost("web", 100.0)
        assert dp.service == "web"
        assert dp.amount == 100.0
        assert dp.currency == "USD"

    def test_record_returns_data_point_with_id(self):
        eng = _engine()
        dp = eng.record_cost("web", 50.0)
        assert dp.id
        assert dp.recorded_at > 0

    def test_record_with_period_and_currency(self):
        eng = _engine()
        dp = eng.record_cost("db", 250.0, period="2024-01", currency="EUR")
        assert dp.period == "2024-01"
        assert dp.currency == "EUR"

    def test_record_trims_to_max_datapoints(self):
        eng = _engine(max_datapoints=3)
        eng.record_cost("s1", 10.0)
        eng.record_cost("s2", 20.0)
        eng.record_cost("s3", 30.0)
        eng.record_cost("s4", 40.0)
        eng.get_cost_history("s1")
        total = (
            len(eng.get_cost_history("s1"))
            + len(eng.get_cost_history("s2"))
            + len(eng.get_cost_history("s3"))
            + len(eng.get_cost_history("s4"))
        )
        assert total == 3


# ---------------------------------------------------------------------------
# forecast — method variants
# ---------------------------------------------------------------------------


class TestForecast:
    def test_linear_extrapolation_two_points(self):
        eng = _engine()
        eng.record_cost("web", 100.0)
        eng.record_cost("web", 120.0)
        fc = eng.forecast("web", method="linear", periods_ahead=1)
        # slope = (120 - 100) / 1 = 20; predicted = 120 + 20*1 = 140
        assert fc.predicted_amount == pytest.approx(140.0, abs=0.01)

    def test_linear_extrapolation_three_points(self):
        eng = _engine()
        eng.record_cost("web", 100.0)
        eng.record_cost("web", 110.0)
        eng.record_cost("web", 120.0)
        fc = eng.forecast("web", method="linear", periods_ahead=2)
        # slope = (120 - 100) / 2 = 10; predicted = 120 + 10*2 = 140
        assert fc.predicted_amount == pytest.approx(140.0, abs=0.01)

    def test_moving_average(self):
        eng = _engine()
        for val in [10.0, 20.0, 30.0, 40.0, 50.0]:
            eng.record_cost("web", val)
        fc = eng.forecast("web", method="moving_average")
        # avg of last 5: (10+20+30+40+50)/5 = 30
        assert fc.predicted_amount == pytest.approx(30.0, abs=0.01)

    def test_moving_average_uses_last_five(self):
        eng = _engine()
        for val in [5.0, 10.0, 20.0, 30.0, 40.0, 50.0]:
            eng.record_cost("web", val)
        fc = eng.forecast("web", method="moving_average")
        # last 5: 10, 20, 30, 40, 50 => avg=30
        assert fc.predicted_amount == pytest.approx(30.0, abs=0.01)

    def test_exponential_moving_average(self):
        eng = _engine()
        for val in [100.0, 110.0, 120.0]:
            eng.record_cost("web", val)
        fc = eng.forecast("web", method="exponential")
        # alpha=0.3; ema=100; ema=0.3*110+0.7*100=103; ema=0.3*120+0.7*103=108.1
        assert fc.predicted_amount == pytest.approx(108.1, abs=0.01)

    def test_no_data_returns_zero(self):
        eng = _engine()
        fc = eng.forecast("empty_svc")
        assert fc.predicted_amount == 0.0

    def test_predicted_never_negative(self):
        eng = _engine()
        eng.record_cost("web", 100.0)
        eng.record_cost("web", 10.0)
        # slope = (10-100)/1 = -90; predicted = 10 + -90*2 = -170 => clamped to 0
        fc = eng.forecast("web", method="linear", periods_ahead=2)
        assert fc.predicted_amount >= 0.0

    def test_single_point_linear_returns_same_value(self):
        eng = _engine()
        eng.record_cost("web", 42.0)
        fc = eng.forecast("web", method="linear", periods_ahead=3)
        assert fc.predicted_amount == pytest.approx(42.0, abs=0.01)


# ---------------------------------------------------------------------------
# confidence
# ---------------------------------------------------------------------------


class TestConfidence:
    def test_high_confidence_with_ten_plus_points(self):
        eng = _engine()
        for i in range(10):
            eng.record_cost("web", 100.0 + i)
        fc = eng.forecast("web")
        assert fc.confidence == ForecastConfidence.HIGH

    def test_medium_confidence_with_five_points(self):
        eng = _engine()
        for i in range(5):
            eng.record_cost("web", 100.0 + i)
        fc = eng.forecast("web")
        assert fc.confidence == ForecastConfidence.MEDIUM

    def test_low_confidence_with_few_points(self):
        eng = _engine()
        eng.record_cost("web", 100.0)
        eng.record_cost("web", 110.0)
        fc = eng.forecast("web")
        assert fc.confidence == ForecastConfidence.LOW


# ---------------------------------------------------------------------------
# bounds
# ---------------------------------------------------------------------------


class TestBounds:
    def test_lower_bound(self):
        eng = _engine()
        eng.record_cost("web", 100.0)
        fc = eng.forecast("web")
        assert fc.lower_bound == pytest.approx(
            fc.predicted_amount * 0.85,
            abs=0.01,
        )

    def test_upper_bound(self):
        eng = _engine()
        eng.record_cost("web", 100.0)
        fc = eng.forecast("web")
        assert fc.upper_bound == pytest.approx(
            fc.predicted_amount * 1.15,
            abs=0.01,
        )


# ---------------------------------------------------------------------------
# set_budget / check_budgets
# ---------------------------------------------------------------------------


class TestSetBudget:
    def test_stores_budget_for_service(self):
        eng = _engine()
        eng.set_budget("web", 5000.0)
        # Budget is stored — check_budgets should reference it
        stats = eng.get_stats()
        assert stats["total_budgets"] == 1


class TestCheckBudgets:
    def test_triggers_alert_when_forecast_exceeds_threshold(self):
        eng = _engine(budget_alert_threshold=0.9)
        for _ in range(3):
            eng.record_cost("web", 1000.0)
        eng.set_budget("web", 1000.0)
        alerts = eng.check_budgets()
        assert len(alerts) >= 1
        assert alerts[0].service == "web"
        assert alerts[0].budget_limit == 1000.0
        assert alerts[0].forecasted_amount > 0

    def test_no_alert_when_under_threshold(self):
        eng = _engine(budget_alert_threshold=0.9)
        eng.record_cost("web", 100.0)
        eng.set_budget("web", 10000.0)
        alerts = eng.check_budgets()
        assert len(alerts) == 0

    def test_no_alert_when_no_data(self):
        eng = _engine()
        eng.set_budget("web", 5000.0)
        alerts = eng.check_budgets()
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# get_forecast
# ---------------------------------------------------------------------------


class TestGetForecast:
    def test_found(self):
        eng = _engine()
        eng.record_cost("web", 100.0)
        fc = eng.forecast("web")
        result = eng.get_forecast(fc.id)
        assert result is not None
        assert result.id == fc.id

    def test_not_found_returns_none(self):
        eng = _engine()
        assert eng.get_forecast("nonexistent") is None


# ---------------------------------------------------------------------------
# list_forecasts
# ---------------------------------------------------------------------------


class TestListForecasts:
    def test_filter_by_service(self):
        eng = _engine()
        eng.record_cost("web", 100.0)
        eng.record_cost("db", 200.0)
        eng.forecast("web")
        eng.forecast("db")
        results = eng.list_forecasts(service="web")
        assert len(results) == 1
        assert results[0].service == "web"

    def test_respects_limit(self):
        eng = _engine()
        for i in range(5):
            eng.record_cost("web", 100.0 + i)
            eng.forecast("web")
        results = eng.list_forecasts(limit=2)
        assert len(results) == 2

    def test_list_all_when_no_filter(self):
        eng = _engine()
        eng.record_cost("web", 100.0)
        eng.record_cost("db", 200.0)
        eng.forecast("web")
        eng.forecast("db")
        results = eng.list_forecasts()
        assert len(results) == 2


# ---------------------------------------------------------------------------
# get_cost_history
# ---------------------------------------------------------------------------


class TestGetCostHistory:
    def test_returns_for_service(self):
        eng = _engine()
        eng.record_cost("web", 100.0)
        eng.record_cost("db", 200.0)
        history = eng.get_cost_history("web")
        assert len(history) == 1
        assert history[0].service == "web"

    def test_respects_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_cost("web", float(i))
        history = eng.get_cost_history("web", limit=3)
        assert len(history) == 3


# ---------------------------------------------------------------------------
# get_alerts
# ---------------------------------------------------------------------------


class TestGetAlerts:
    def test_filter_by_service(self):
        eng = _engine(budget_alert_threshold=0.9)
        eng.record_cost("web", 1000.0)
        eng.record_cost("db", 2000.0)
        eng.set_budget("web", 1000.0)
        eng.set_budget("db", 2000.0)
        eng.check_budgets()
        web_alerts = eng.get_alerts(service="web")
        for a in web_alerts:
            assert a.service == "web"

    def test_all_alerts_when_no_filter(self):
        eng = _engine(budget_alert_threshold=0.9)
        eng.record_cost("web", 1000.0)
        eng.set_budget("web", 1000.0)
        eng.check_budgets()
        all_alerts = eng.get_alerts()
        assert len(all_alerts) >= 1


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_datapoints"] == 0
        assert stats["total_forecasts"] == 0
        assert stats["total_alerts"] == 0
        assert stats["total_budgets"] == 0
        assert stats["services_tracked"] == 0
        assert stats["total_recorded_cost"] == 0.0

    def test_stats_populated(self):
        eng = _engine()
        eng.record_cost("web", 100.0)
        eng.record_cost("web", 200.0)
        eng.record_cost("db", 50.0)
        eng.forecast("web")
        stats = eng.get_stats()
        assert stats["total_datapoints"] == 3
        assert stats["total_forecasts"] == 1
        assert stats["services_tracked"] == 2
        assert stats["total_recorded_cost"] == pytest.approx(
            350.0,
            abs=0.01,
        )
