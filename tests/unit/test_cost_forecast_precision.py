"""Tests for shieldops.billing.cost_forecast_precision — CostForecastPrecision."""

from __future__ import annotations

from shieldops.billing.cost_forecast_precision import (
    BiasDirection,
    CostForecastPrecision,
    CostForecastReport,
    ForecastAccuracy,
    ForecastPeriod,
    PrecisionAnalysis,
    PrecisionRecord,
)


def _engine(**kw) -> CostForecastPrecision:
    return CostForecastPrecision(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_accuracy_excellent(self):
        assert ForecastAccuracy.EXCELLENT == "excellent"

    def test_accuracy_good(self):
        assert ForecastAccuracy.GOOD == "good"

    def test_accuracy_acceptable(self):
        assert ForecastAccuracy.ACCEPTABLE == "acceptable"

    def test_accuracy_poor(self):
        assert ForecastAccuracy.POOR == "poor"

    def test_accuracy_unreliable(self):
        assert ForecastAccuracy.UNRELIABLE == "unreliable"

    def test_bias_over_forecast(self):
        assert BiasDirection.OVER_FORECAST == "over_forecast"

    def test_bias_under_forecast(self):
        assert BiasDirection.UNDER_FORECAST == "under_forecast"

    def test_bias_calibrated(self):
        assert BiasDirection.CALIBRATED == "calibrated"

    def test_bias_volatile(self):
        assert BiasDirection.VOLATILE == "volatile"

    def test_bias_trending(self):
        assert BiasDirection.TRENDING == "trending"

    def test_period_weekly(self):
        assert ForecastPeriod.WEEKLY == "weekly"

    def test_period_monthly(self):
        assert ForecastPeriod.MONTHLY == "monthly"

    def test_period_quarterly(self):
        assert ForecastPeriod.QUARTERLY == "quarterly"

    def test_period_semi_annual(self):
        assert ForecastPeriod.SEMI_ANNUAL == "semi_annual"

    def test_period_annual(self):
        assert ForecastPeriod.ANNUAL == "annual"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_precision_record_defaults(self):
        r = PrecisionRecord()
        assert r.id
        assert r.forecast_name == ""
        assert r.forecast_accuracy == ForecastAccuracy.EXCELLENT
        assert r.bias_direction == BiasDirection.CALIBRATED
        assert r.forecast_period == ForecastPeriod.MONTHLY
        assert r.precision_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_precision_analysis_defaults(self):
        a = PrecisionAnalysis()
        assert a.id
        assert a.forecast_name == ""
        assert a.forecast_accuracy == ForecastAccuracy.EXCELLENT
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_cost_forecast_report_defaults(self):
        r = CostForecastReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_precision_count == 0
        assert r.avg_precision_score == 0.0
        assert r.by_accuracy == {}
        assert r.by_bias == {}
        assert r.by_period == {}
        assert r.top_imprecise == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_precision
# ---------------------------------------------------------------------------


class TestRecordPrecision:
    def test_basic(self):
        eng = _engine()
        r = eng.record_precision(
            forecast_name="compute-forecast-q1",
            forecast_accuracy=ForecastAccuracy.POOR,
            bias_direction=BiasDirection.OVER_FORECAST,
            forecast_period=ForecastPeriod.QUARTERLY,
            precision_score=45.0,
            service="api-gateway",
            team="sre",
        )
        assert r.forecast_name == "compute-forecast-q1"
        assert r.forecast_accuracy == ForecastAccuracy.POOR
        assert r.bias_direction == BiasDirection.OVER_FORECAST
        assert r.forecast_period == ForecastPeriod.QUARTERLY
        assert r.precision_score == 45.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_precision(forecast_name=f"forecast-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_precision
# ---------------------------------------------------------------------------


class TestGetPrecision:
    def test_found(self):
        eng = _engine()
        r = eng.record_precision(
            forecast_name="compute-forecast-q1",
            forecast_accuracy=ForecastAccuracy.GOOD,
        )
        result = eng.get_precision(r.id)
        assert result is not None
        assert result.forecast_accuracy == ForecastAccuracy.GOOD

    def test_not_found(self):
        eng = _engine()
        assert eng.get_precision("nonexistent") is None


# ---------------------------------------------------------------------------
# list_precisions
# ---------------------------------------------------------------------------


class TestListPrecisions:
    def test_list_all(self):
        eng = _engine()
        eng.record_precision(forecast_name="forecast-1")
        eng.record_precision(forecast_name="forecast-2")
        assert len(eng.list_precisions()) == 2

    def test_filter_by_accuracy(self):
        eng = _engine()
        eng.record_precision(
            forecast_name="forecast-1",
            forecast_accuracy=ForecastAccuracy.POOR,
        )
        eng.record_precision(
            forecast_name="forecast-2",
            forecast_accuracy=ForecastAccuracy.EXCELLENT,
        )
        results = eng.list_precisions(
            forecast_accuracy=ForecastAccuracy.POOR,
        )
        assert len(results) == 1

    def test_filter_by_bias(self):
        eng = _engine()
        eng.record_precision(
            forecast_name="forecast-1",
            bias_direction=BiasDirection.OVER_FORECAST,
        )
        eng.record_precision(
            forecast_name="forecast-2",
            bias_direction=BiasDirection.UNDER_FORECAST,
        )
        results = eng.list_precisions(
            bias_direction=BiasDirection.OVER_FORECAST,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_precision(forecast_name="forecast-1", team="sre")
        eng.record_precision(forecast_name="forecast-2", team="platform")
        results = eng.list_precisions(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_precision(forecast_name=f"forecast-{i}")
        assert len(eng.list_precisions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            forecast_name="compute-forecast-q1",
            forecast_accuracy=ForecastAccuracy.UNRELIABLE,
            analysis_score=35.0,
            threshold=85.0,
            breached=True,
            description="Forecast precision critically low",
        )
        assert a.forecast_name == "compute-forecast-q1"
        assert a.forecast_accuracy == ForecastAccuracy.UNRELIABLE
        assert a.analysis_score == 35.0
        assert a.threshold == 85.0
        assert a.breached is True
        assert a.description == "Forecast precision critically low"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(forecast_name=f"forecast-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_precision_distribution
# ---------------------------------------------------------------------------


class TestAnalyzePrecisionDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_precision(
            forecast_name="forecast-1",
            forecast_accuracy=ForecastAccuracy.POOR,
            precision_score=40.0,
        )
        eng.record_precision(
            forecast_name="forecast-2",
            forecast_accuracy=ForecastAccuracy.POOR,
            precision_score=50.0,
        )
        result = eng.analyze_precision_distribution()
        assert "poor" in result
        assert result["poor"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_precision_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_precision_forecasts
# ---------------------------------------------------------------------------


class TestIdentifyLowPrecisionForecasts:
    def test_detects_low_precision(self):
        eng = _engine(precision_accuracy_threshold=85.0)
        eng.record_precision(
            forecast_name="forecast-1",
            precision_score=50.0,
        )
        eng.record_precision(
            forecast_name="forecast-2",
            precision_score=90.0,
        )
        results = eng.identify_low_precision_forecasts()
        assert len(results) == 1
        assert results[0]["forecast_name"] == "forecast-1"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_precision_forecasts() == []


# ---------------------------------------------------------------------------
# rank_by_precision
# ---------------------------------------------------------------------------


class TestRankByPrecision:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_precision(
            forecast_name="forecast-1",
            service="api-gateway",
            precision_score=90.0,
        )
        eng.record_precision(
            forecast_name="forecast-2",
            service="payments",
            precision_score=30.0,
        )
        results = eng.rank_by_precision()
        assert len(results) == 2
        assert results[0]["service"] == "payments"
        assert results[0]["avg_precision_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_precision() == []


# ---------------------------------------------------------------------------
# detect_precision_trends
# ---------------------------------------------------------------------------


class TestDetectPrecisionTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(
                forecast_name="forecast-1",
                analysis_score=50.0,
            )
        result = eng.detect_precision_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(forecast_name="forecast-1", analysis_score=30.0)
        eng.add_analysis(forecast_name="forecast-2", analysis_score=30.0)
        eng.add_analysis(forecast_name="forecast-3", analysis_score=80.0)
        eng.add_analysis(forecast_name="forecast-4", analysis_score=80.0)
        result = eng.detect_precision_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_precision_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(precision_accuracy_threshold=85.0)
        eng.record_precision(
            forecast_name="compute-forecast-q1",
            forecast_accuracy=ForecastAccuracy.POOR,
            bias_direction=BiasDirection.OVER_FORECAST,
            forecast_period=ForecastPeriod.QUARTERLY,
            precision_score=45.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CostForecastReport)
        assert report.total_records == 1
        assert report.low_precision_count == 1
        assert len(report.top_imprecise) == 1
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
        eng.record_precision(forecast_name="forecast-1")
        eng.add_analysis(forecast_name="forecast-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["accuracy_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_precision(
            forecast_name="compute-forecast-q1",
            forecast_accuracy=ForecastAccuracy.POOR,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "poor" in stats["accuracy_distribution"]
