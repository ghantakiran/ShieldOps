"""Tests for shieldops.billing.forecast_validator — CostForecastValidator."""

from __future__ import annotations

from shieldops.billing.forecast_validator import (
    CostDomain,
    CostForecastValidator,
    ForecastAccuracy,
    ForecastPeriod,
    ForecastRecord,
    ForecastRule,
    ForecastValidationReport,
)


def _engine(**kw) -> CostForecastValidator:
    return CostForecastValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_period_daily(self):
        assert ForecastPeriod.DAILY == "daily"

    def test_period_weekly(self):
        assert ForecastPeriod.WEEKLY == "weekly"

    def test_period_monthly(self):
        assert ForecastPeriod.MONTHLY == "monthly"

    def test_period_quarterly(self):
        assert ForecastPeriod.QUARTERLY == "quarterly"

    def test_period_annual(self):
        assert ForecastPeriod.ANNUAL == "annual"

    def test_accuracy_excellent(self):
        assert ForecastAccuracy.EXCELLENT == "excellent"

    def test_accuracy_good(self):
        assert ForecastAccuracy.GOOD == "good"

    def test_accuracy_fair(self):
        assert ForecastAccuracy.FAIR == "fair"

    def test_accuracy_poor(self):
        assert ForecastAccuracy.POOR == "poor"

    def test_accuracy_unreliable(self):
        assert ForecastAccuracy.UNRELIABLE == "unreliable"

    def test_domain_compute(self):
        assert CostDomain.COMPUTE == "compute"

    def test_domain_storage(self):
        assert CostDomain.STORAGE == "storage"

    def test_domain_network(self):
        assert CostDomain.NETWORK == "network"

    def test_domain_database(self):
        assert CostDomain.DATABASE == "database"

    def test_domain_platform(self):
        assert CostDomain.PLATFORM == "platform"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_forecast_record_defaults(self):
        r = ForecastRecord()
        assert r.id
        assert r.service_name == ""
        assert r.forecast_period == ForecastPeriod.MONTHLY
        assert r.forecast_accuracy == ForecastAccuracy.FAIR
        assert r.cost_domain == CostDomain.COMPUTE
        assert r.forecasted_amount == 0.0
        assert r.actual_amount == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_forecast_rule_defaults(self):
        ru = ForecastRule()
        assert ru.id
        assert ru.service_pattern == ""
        assert ru.forecast_period == ForecastPeriod.MONTHLY
        assert ru.cost_domain == CostDomain.COMPUTE
        assert ru.max_deviation_pct == 0.0
        assert ru.description == ""
        assert ru.created_at > 0

    def test_forecast_validation_report_defaults(self):
        r = ForecastValidationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.accurate_forecasts == 0
        assert r.avg_error_pct == 0.0
        assert r.by_period == {}
        assert r.by_accuracy == {}
        assert r.by_domain == {}
        assert r.inaccurate_forecasts == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_forecast
# ---------------------------------------------------------------------------


class TestRecordForecast:
    def test_basic(self):
        eng = _engine()
        r = eng.record_forecast(
            service_name="api-gateway",
            forecast_period=ForecastPeriod.MONTHLY,
            forecast_accuracy=ForecastAccuracy.GOOD,
            cost_domain=CostDomain.COMPUTE,
            forecasted_amount=1000.0,
            actual_amount=1050.0,
            team="platform",
        )
        assert r.service_name == "api-gateway"
        assert r.forecast_period == ForecastPeriod.MONTHLY
        assert r.forecast_accuracy == ForecastAccuracy.GOOD
        assert r.cost_domain == CostDomain.COMPUTE
        assert r.forecasted_amount == 1000.0
        assert r.actual_amount == 1050.0
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_forecast(service_name=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_forecast
# ---------------------------------------------------------------------------


class TestGetForecast:
    def test_found(self):
        eng = _engine()
        r = eng.record_forecast(
            service_name="api-gateway",
            forecast_accuracy=ForecastAccuracy.EXCELLENT,
        )
        result = eng.get_forecast(r.id)
        assert result is not None
        assert result.forecast_accuracy == ForecastAccuracy.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_forecast("nonexistent") is None


# ---------------------------------------------------------------------------
# list_forecasts
# ---------------------------------------------------------------------------


class TestListForecasts:
    def test_list_all(self):
        eng = _engine()
        eng.record_forecast(service_name="svc-a")
        eng.record_forecast(service_name="svc-b")
        assert len(eng.list_forecasts()) == 2

    def test_filter_by_period(self):
        eng = _engine()
        eng.record_forecast(
            service_name="svc-a",
            forecast_period=ForecastPeriod.DAILY,
        )
        eng.record_forecast(
            service_name="svc-b",
            forecast_period=ForecastPeriod.ANNUAL,
        )
        results = eng.list_forecasts(period=ForecastPeriod.DAILY)
        assert len(results) == 1

    def test_filter_by_accuracy(self):
        eng = _engine()
        eng.record_forecast(
            service_name="svc-a",
            forecast_accuracy=ForecastAccuracy.EXCELLENT,
        )
        eng.record_forecast(
            service_name="svc-b",
            forecast_accuracy=ForecastAccuracy.POOR,
        )
        results = eng.list_forecasts(accuracy=ForecastAccuracy.EXCELLENT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_forecast(service_name="svc-a", team="platform")
        eng.record_forecast(service_name="svc-b", team="infra")
        results = eng.list_forecasts(team="platform")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_forecast(service_name=f"svc-{i}")
        assert len(eng.list_forecasts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        ru = eng.add_rule(
            service_pattern="api-*",
            forecast_period=ForecastPeriod.MONTHLY,
            cost_domain=CostDomain.COMPUTE,
            max_deviation_pct=15.0,
            description="Monthly compute budget",
        )
        assert ru.service_pattern == "api-*"
        assert ru.forecast_period == ForecastPeriod.MONTHLY
        assert ru.cost_domain == CostDomain.COMPUTE
        assert ru.max_deviation_pct == 15.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(service_pattern=f"pat-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_forecast_accuracy
# ---------------------------------------------------------------------------


class TestAnalyzeForecastAccuracy:
    def test_with_data(self):
        eng = _engine()
        eng.record_forecast(
            service_name="svc-a",
            forecast_period=ForecastPeriod.MONTHLY,
            forecasted_amount=100.0,
            actual_amount=110.0,
        )
        eng.record_forecast(
            service_name="svc-b",
            forecast_period=ForecastPeriod.MONTHLY,
            forecasted_amount=200.0,
            actual_amount=200.0,
        )
        result = eng.analyze_forecast_accuracy()
        assert "monthly" in result
        assert result["monthly"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_forecast_accuracy() == {}


# ---------------------------------------------------------------------------
# identify_inaccurate_forecasts
# ---------------------------------------------------------------------------


class TestIdentifyInaccurateForecasts:
    def test_detects_poor(self):
        eng = _engine()
        eng.record_forecast(
            service_name="svc-a",
            forecast_accuracy=ForecastAccuracy.POOR,
        )
        eng.record_forecast(
            service_name="svc-b",
            forecast_accuracy=ForecastAccuracy.EXCELLENT,
        )
        results = eng.identify_inaccurate_forecasts()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_detects_unreliable(self):
        eng = _engine()
        eng.record_forecast(
            service_name="svc-a",
            forecast_accuracy=ForecastAccuracy.UNRELIABLE,
        )
        results = eng.identify_inaccurate_forecasts()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_inaccurate_forecasts() == []


# ---------------------------------------------------------------------------
# rank_by_error
# ---------------------------------------------------------------------------


class TestRankByError:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_forecast(
            service_name="svc-a",
            team="platform",
            forecasted_amount=100.0,
            actual_amount=200.0,
        )
        eng.record_forecast(
            service_name="svc-b",
            team="platform",
            forecasted_amount=100.0,
            actual_amount=120.0,
        )
        eng.record_forecast(
            service_name="svc-c",
            team="infra",
            forecasted_amount=100.0,
            actual_amount=105.0,
        )
        results = eng.rank_by_error()
        assert len(results) == 2
        assert results[0]["team"] == "platform"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_error() == []


# ---------------------------------------------------------------------------
# detect_forecast_trends
# ---------------------------------------------------------------------------


class TestDetectForecastTrends:
    def test_stable(self):
        eng = _engine()
        for d in [10.0, 10.0, 10.0, 10.0]:
            eng.add_rule(service_pattern="p", max_deviation_pct=d)
        result = eng.detect_forecast_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for d in [5.0, 5.0, 20.0, 20.0]:
            eng.add_rule(service_pattern="p", max_deviation_pct=d)
        result = eng.detect_forecast_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_forecast_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_forecast(
            service_name="api-gateway",
            forecast_period=ForecastPeriod.MONTHLY,
            forecast_accuracy=ForecastAccuracy.POOR,
            cost_domain=CostDomain.COMPUTE,
            forecasted_amount=100.0,
            actual_amount=200.0,
            team="platform",
        )
        report = eng.generate_report()
        assert isinstance(report, ForecastValidationReport)
        assert report.total_records == 1
        assert report.accurate_forecasts == 0
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
        eng.record_forecast(service_name="svc-a")
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
        assert stats["period_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_forecast(
            service_name="api-gateway",
            forecast_period=ForecastPeriod.MONTHLY,
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "monthly" in stats["period_distribution"]
