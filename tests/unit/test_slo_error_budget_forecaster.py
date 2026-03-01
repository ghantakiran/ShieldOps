"""Tests for shieldops.sla.slo_error_budget_forecaster — SLOErrorBudgetForecaster."""

from __future__ import annotations

from shieldops.sla.slo_error_budget_forecaster import (
    BudgetForecast,
    DepletionRate,
    ForecastHorizon,
    ForecastMetric,
    ForecastRecord,
    SLOErrorBudgetForecaster,
    SLOErrorBudgetForecastReport,
)


def _engine(**kw) -> SLOErrorBudgetForecaster:
    return SLOErrorBudgetForecaster(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_forecast_safe(self):
        assert BudgetForecast.SAFE == "safe"

    def test_forecast_caution(self):
        assert BudgetForecast.CAUTION == "caution"

    def test_forecast_warning(self):
        assert BudgetForecast.WARNING == "warning"

    def test_forecast_critical(self):
        assert BudgetForecast.CRITICAL == "critical"

    def test_forecast_exhausted(self):
        assert BudgetForecast.EXHAUSTED == "exhausted"

    def test_rate_accelerating(self):
        assert DepletionRate.ACCELERATING == "accelerating"

    def test_rate_steady(self):
        assert DepletionRate.STEADY == "steady"

    def test_rate_decelerating(self):
        assert DepletionRate.DECELERATING == "decelerating"

    def test_rate_recovering(self):
        assert DepletionRate.RECOVERING == "recovering"

    def test_rate_stable(self):
        assert DepletionRate.STABLE == "stable"

    def test_horizon_one_day(self):
        assert ForecastHorizon.ONE_DAY == "one_day"

    def test_horizon_one_week(self):
        assert ForecastHorizon.ONE_WEEK == "one_week"

    def test_horizon_one_month(self):
        assert ForecastHorizon.ONE_MONTH == "one_month"

    def test_horizon_one_quarter(self):
        assert ForecastHorizon.ONE_QUARTER == "one_quarter"

    def test_horizon_one_year(self):
        assert ForecastHorizon.ONE_YEAR == "one_year"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_forecast_record_defaults(self):
        r = ForecastRecord()
        assert r.id
        assert r.forecast_id == ""
        assert r.budget_forecast == BudgetForecast.SAFE
        assert r.depletion_rate == DepletionRate.STABLE
        assert r.forecast_horizon == ForecastHorizon.ONE_MONTH
        assert r.remaining_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_forecast_metric_defaults(self):
        m = ForecastMetric()
        assert m.id
        assert m.forecast_id == ""
        assert m.budget_forecast == BudgetForecast.SAFE
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_forecast_report_defaults(self):
        r = SLOErrorBudgetForecastReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.critical_forecasts == 0
        assert r.avg_remaining_pct == 0.0
        assert r.by_forecast == {}
        assert r.by_rate == {}
        assert r.by_horizon == {}
        assert r.top_depleting == []
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
            forecast_id="FC-001",
            budget_forecast=BudgetForecast.CRITICAL,
            depletion_rate=DepletionRate.ACCELERATING,
            forecast_horizon=ForecastHorizon.ONE_WEEK,
            remaining_pct=10.0,
            service="api-gateway",
            team="sre",
        )
        assert r.forecast_id == "FC-001"
        assert r.budget_forecast == BudgetForecast.CRITICAL
        assert r.depletion_rate == DepletionRate.ACCELERATING
        assert r.forecast_horizon == ForecastHorizon.ONE_WEEK
        assert r.remaining_pct == 10.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_forecast(forecast_id=f"FC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_forecast
# ---------------------------------------------------------------------------


class TestGetForecast:
    def test_found(self):
        eng = _engine()
        r = eng.record_forecast(
            forecast_id="FC-001",
            budget_forecast=BudgetForecast.CRITICAL,
        )
        result = eng.get_forecast(r.id)
        assert result is not None
        assert result.budget_forecast == BudgetForecast.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_forecast("nonexistent") is None


# ---------------------------------------------------------------------------
# list_forecasts
# ---------------------------------------------------------------------------


class TestListForecasts:
    def test_list_all(self):
        eng = _engine()
        eng.record_forecast(forecast_id="FC-001")
        eng.record_forecast(forecast_id="FC-002")
        assert len(eng.list_forecasts()) == 2

    def test_filter_by_forecast(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            budget_forecast=BudgetForecast.SAFE,
        )
        eng.record_forecast(
            forecast_id="FC-002",
            budget_forecast=BudgetForecast.CRITICAL,
        )
        results = eng.list_forecasts(
            budget_forecast=BudgetForecast.SAFE,
        )
        assert len(results) == 1

    def test_filter_by_rate(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            depletion_rate=DepletionRate.ACCELERATING,
        )
        eng.record_forecast(
            forecast_id="FC-002",
            depletion_rate=DepletionRate.STABLE,
        )
        results = eng.list_forecasts(
            depletion_rate=DepletionRate.ACCELERATING,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_forecast(forecast_id="FC-001", team="sre")
        eng.record_forecast(forecast_id="FC-002", team="platform")
        results = eng.list_forecasts(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_forecast(forecast_id=f"FC-{i}")
        assert len(eng.list_forecasts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            forecast_id="FC-001",
            budget_forecast=BudgetForecast.WARNING,
            metric_score=45.0,
            threshold=50.0,
            breached=True,
            description="budget burn rate",
        )
        assert m.forecast_id == "FC-001"
        assert m.budget_forecast == BudgetForecast.WARNING
        assert m.metric_score == 45.0
        assert m.threshold == 50.0
        assert m.breached is True
        assert m.description == "budget burn rate"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(forecast_id=f"FC-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_forecast_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeForecastDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            budget_forecast=BudgetForecast.SAFE,
            remaining_pct=80.0,
        )
        eng.record_forecast(
            forecast_id="FC-002",
            budget_forecast=BudgetForecast.SAFE,
            remaining_pct=60.0,
        )
        result = eng.analyze_forecast_distribution()
        assert "safe" in result
        assert result["safe"]["count"] == 2
        assert result["safe"]["avg_remaining_pct"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_forecast_distribution() == {}


# ---------------------------------------------------------------------------
# identify_critical_forecasts
# ---------------------------------------------------------------------------


class TestIdentifyCriticalForecasts:
    def test_detects_critical(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            budget_forecast=BudgetForecast.CRITICAL,
        )
        eng.record_forecast(
            forecast_id="FC-002",
            budget_forecast=BudgetForecast.SAFE,
        )
        results = eng.identify_critical_forecasts()
        assert len(results) == 1
        assert results[0]["forecast_id"] == "FC-001"

    def test_detects_exhausted(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            budget_forecast=BudgetForecast.EXHAUSTED,
        )
        results = eng.identify_critical_forecasts()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_forecasts() == []


# ---------------------------------------------------------------------------
# rank_by_remaining
# ---------------------------------------------------------------------------


class TestRankByRemaining:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_forecast(forecast_id="FC-001", service="api", remaining_pct=80.0)
        eng.record_forecast(forecast_id="FC-002", service="web", remaining_pct=20.0)
        results = eng.rank_by_remaining()
        assert len(results) == 2
        assert results[0]["service"] == "web"
        assert results[0]["avg_remaining_pct"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_remaining() == []


# ---------------------------------------------------------------------------
# detect_forecast_trends
# ---------------------------------------------------------------------------


class TestDetectForecastTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(forecast_id="FC-001", metric_score=50.0)
        result = eng.detect_forecast_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_metric(forecast_id="FC-001", metric_score=20.0)
        eng.add_metric(forecast_id="FC-002", metric_score=20.0)
        eng.add_metric(forecast_id="FC-003", metric_score=80.0)
        eng.add_metric(forecast_id="FC-004", metric_score=80.0)
        result = eng.detect_forecast_trends()
        assert result["trend"] == "improving"
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
            forecast_id="FC-001",
            budget_forecast=BudgetForecast.CRITICAL,
            depletion_rate=DepletionRate.ACCELERATING,
            forecast_horizon=ForecastHorizon.ONE_WEEK,
            remaining_pct=5.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SLOErrorBudgetForecastReport)
        assert report.total_records == 1
        assert report.critical_forecasts == 1
        assert len(report.top_depleting) == 1
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
        eng.record_forecast(forecast_id="FC-001")
        eng.add_metric(forecast_id="FC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["forecast_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            budget_forecast=BudgetForecast.SAFE,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_forecasts"] == 1
        assert "safe" in stats["forecast_distribution"]
