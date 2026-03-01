"""Tests for shieldops.billing.cost_forecast_accuracy — CostForecastAccuracyTracker."""

from __future__ import annotations

from shieldops.billing.cost_forecast_accuracy import (
    AccuracyGrade,
    CostForecastAccuracyReport,
    CostForecastAccuracyTracker,
    DeviationCause,
    ForecastEvaluation,
    ForecastHorizon,
    ForecastRecord,
)


def _engine(**kw) -> CostForecastAccuracyTracker:
    return CostForecastAccuracyTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_horizon_daily(self):
        assert ForecastHorizon.DAILY == "daily"

    def test_horizon_weekly(self):
        assert ForecastHorizon.WEEKLY == "weekly"

    def test_horizon_monthly(self):
        assert ForecastHorizon.MONTHLY == "monthly"

    def test_horizon_quarterly(self):
        assert ForecastHorizon.QUARTERLY == "quarterly"

    def test_horizon_annual(self):
        assert ForecastHorizon.ANNUAL == "annual"

    def test_grade_excellent(self):
        assert AccuracyGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert AccuracyGrade.GOOD == "good"

    def test_grade_fair(self):
        assert AccuracyGrade.FAIR == "fair"

    def test_grade_poor(self):
        assert AccuracyGrade.POOR == "poor"

    def test_grade_unreliable(self):
        assert AccuracyGrade.UNRELIABLE == "unreliable"

    def test_cause_demand_spike(self):
        assert DeviationCause.DEMAND_SPIKE == "demand_spike"

    def test_cause_pricing_change(self):
        assert DeviationCause.PRICING_CHANGE == "pricing_change"

    def test_cause_resource_drift(self):
        assert DeviationCause.RESOURCE_DRIFT == "resource_drift"

    def test_cause_seasonal(self):
        assert DeviationCause.SEASONAL == "seasonal"

    def test_cause_anomaly(self):
        assert DeviationCause.ANOMALY == "anomaly"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_forecast_record_defaults(self):
        r = ForecastRecord()
        assert r.id
        assert r.forecast_id == ""
        assert r.forecast_horizon == ForecastHorizon.MONTHLY
        assert r.accuracy_grade == AccuracyGrade.FAIR
        assert r.deviation_cause == DeviationCause.ANOMALY
        assert r.accuracy_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_forecast_evaluation_defaults(self):
        m = ForecastEvaluation()
        assert m.id
        assert m.forecast_id == ""
        assert m.forecast_horizon == ForecastHorizon.MONTHLY
        assert m.eval_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_cost_forecast_accuracy_report_defaults(self):
        r = CostForecastAccuracyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_evaluations == 0
        assert r.inaccurate_count == 0
        assert r.avg_accuracy_pct == 0.0
        assert r.by_horizon == {}
        assert r.by_grade == {}
        assert r.by_cause == {}
        assert r.top_inaccurate == []
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
            forecast_horizon=ForecastHorizon.QUARTERLY,
            accuracy_grade=AccuracyGrade.POOR,
            deviation_cause=DeviationCause.DEMAND_SPIKE,
            accuracy_pct=45.0,
            service="api-gateway",
            team="sre",
        )
        assert r.forecast_id == "FC-001"
        assert r.forecast_horizon == ForecastHorizon.QUARTERLY
        assert r.accuracy_grade == AccuracyGrade.POOR
        assert r.deviation_cause == DeviationCause.DEMAND_SPIKE
        assert r.accuracy_pct == 45.0
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
            accuracy_grade=AccuracyGrade.POOR,
        )
        result = eng.get_forecast(r.id)
        assert result is not None
        assert result.accuracy_grade == AccuracyGrade.POOR

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

    def test_filter_by_horizon(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            forecast_horizon=ForecastHorizon.MONTHLY,
        )
        eng.record_forecast(
            forecast_id="FC-002",
            forecast_horizon=ForecastHorizon.QUARTERLY,
        )
        results = eng.list_forecasts(
            horizon=ForecastHorizon.MONTHLY,
        )
        assert len(results) == 1

    def test_filter_by_grade(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            accuracy_grade=AccuracyGrade.EXCELLENT,
        )
        eng.record_forecast(
            forecast_id="FC-002",
            accuracy_grade=AccuracyGrade.POOR,
        )
        results = eng.list_forecasts(
            grade=AccuracyGrade.EXCELLENT,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_forecast(forecast_id="FC-001", service="api-gateway")
        eng.record_forecast(forecast_id="FC-002", service="auth-svc")
        results = eng.list_forecasts(service="api-gateway")
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
# add_evaluation
# ---------------------------------------------------------------------------


class TestAddEvaluation:
    def test_basic(self):
        eng = _engine()
        m = eng.add_evaluation(
            forecast_id="FC-001",
            forecast_horizon=ForecastHorizon.QUARTERLY,
            eval_score=85.0,
            threshold=90.0,
            breached=True,
            description="Forecast accuracy below threshold",
        )
        assert m.forecast_id == "FC-001"
        assert m.forecast_horizon == ForecastHorizon.QUARTERLY
        assert m.eval_score == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "Forecast accuracy below threshold"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_evaluation(forecast_id=f"FC-{i}")
        assert len(eng._evaluations) == 2


# ---------------------------------------------------------------------------
# analyze_accuracy_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeAccuracyDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            forecast_horizon=ForecastHorizon.MONTHLY,
            accuracy_pct=90.0,
        )
        eng.record_forecast(
            forecast_id="FC-002",
            forecast_horizon=ForecastHorizon.MONTHLY,
            accuracy_pct=80.0,
        )
        result = eng.analyze_accuracy_distribution()
        assert "monthly" in result
        assert result["monthly"]["count"] == 2
        assert result["monthly"]["avg_accuracy_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_accuracy_distribution() == {}


# ---------------------------------------------------------------------------
# identify_inaccurate_forecasts
# ---------------------------------------------------------------------------


class TestIdentifyInaccurateForecasts:
    def test_detects_inaccurate(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            accuracy_grade=AccuracyGrade.POOR,
        )
        eng.record_forecast(
            forecast_id="FC-002",
            accuracy_grade=AccuracyGrade.EXCELLENT,
        )
        results = eng.identify_inaccurate_forecasts()
        assert len(results) == 1
        assert results[0]["forecast_id"] == "FC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_inaccurate_forecasts() == []


# ---------------------------------------------------------------------------
# rank_by_accuracy
# ---------------------------------------------------------------------------


class TestRankByAccuracy:
    def test_ranked(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            service="api-gateway",
            accuracy_pct=95.0,
        )
        eng.record_forecast(
            forecast_id="FC-002",
            service="api-gateway",
            accuracy_pct=85.0,
        )
        eng.record_forecast(
            forecast_id="FC-003",
            service="auth-svc",
            accuracy_pct=70.0,
        )
        results = eng.rank_by_accuracy()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"
        assert results[0]["avg_accuracy_pct"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_accuracy() == []


# ---------------------------------------------------------------------------
# detect_accuracy_trends
# ---------------------------------------------------------------------------


class TestDetectAccuracyTrends:
    def test_stable(self):
        eng = _engine()
        for val in [50.0, 50.0, 50.0, 50.0]:
            eng.add_evaluation(forecast_id="FC-1", eval_score=val)
        result = eng.detect_accuracy_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [10.0, 10.0, 50.0, 50.0]:
            eng.add_evaluation(forecast_id="FC-1", eval_score=val)
        result = eng.detect_accuracy_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_accuracy_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            forecast_horizon=ForecastHorizon.QUARTERLY,
            accuracy_grade=AccuracyGrade.POOR,
            deviation_cause=DeviationCause.DEMAND_SPIKE,
            accuracy_pct=45.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, CostForecastAccuracyReport)
        assert report.total_records == 1
        assert report.inaccurate_count == 1
        assert len(report.top_inaccurate) >= 1
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
        eng.add_evaluation(forecast_id="FC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._evaluations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_evaluations"] == 0
        assert stats["horizon_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_forecast(
            forecast_id="FC-001",
            forecast_horizon=ForecastHorizon.QUARTERLY,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "quarterly" in stats["horizon_distribution"]
