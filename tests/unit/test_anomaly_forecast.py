"""Tests for shieldops.observability.anomaly_forecast."""

from __future__ import annotations

from shieldops.observability.anomaly_forecast import (
    AnomalyForecastEngine,
    AnomalyLikelihood,
    ForecastAlert,
    ForecastHorizon,
    ForecastModel,
    ForecastPoint,
    ForecastReport,
)


def _engine(**kw) -> AnomalyForecastEngine:
    return AnomalyForecastEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ForecastHorizon (5 values)

    def test_horizon_minutes_15(self):
        assert ForecastHorizon.MINUTES_15 == "minutes_15"

    def test_horizon_hour_1(self):
        assert ForecastHorizon.HOUR_1 == "hour_1"

    def test_horizon_hours_4(self):
        assert ForecastHorizon.HOURS_4 == "hours_4"

    def test_horizon_hours_12(self):
        assert ForecastHorizon.HOURS_12 == "hours_12"

    def test_horizon_hours_24(self):
        assert ForecastHorizon.HOURS_24 == "hours_24"

    # AnomalyLikelihood (5 values)

    def test_likelihood_very_low(self):
        assert AnomalyLikelihood.VERY_LOW == "very_low"

    def test_likelihood_low(self):
        assert AnomalyLikelihood.LOW == "low"

    def test_likelihood_moderate(self):
        assert AnomalyLikelihood.MODERATE == "moderate"

    def test_likelihood_high(self):
        assert AnomalyLikelihood.HIGH == "high"

    def test_likelihood_very_high(self):
        assert AnomalyLikelihood.VERY_HIGH == "very_high"

    # ForecastModel (5 values)

    def test_model_arima(self):
        assert ForecastModel.ARIMA == "arima"

    def test_model_prophet(self):
        assert ForecastModel.PROPHET == "prophet"

    def test_model_holt_winters(self):
        assert ForecastModel.HOLT_WINTERS == "holt_winters"

    def test_model_exponential_smoothing(self):
        assert ForecastModel.EXPONENTIAL_SMOOTHING == "exponential_smoothing"

    def test_model_ensemble(self):
        assert ForecastModel.ENSEMBLE == "ensemble"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_forecast_point_defaults(self):
        fp = ForecastPoint()
        assert fp.id
        assert fp.service_name == ""
        assert fp.metric_name == ""
        assert fp.current_value == 0.0
        assert fp.predicted_value == 0.0
        assert fp.anomaly_likelihood == AnomalyLikelihood.VERY_LOW
        assert fp.horizon == ForecastHorizon.HOUR_1
        assert fp.confidence == 0.0
        assert fp.model == ForecastModel.ARIMA
        assert fp.created_at > 0

    def test_forecast_alert_defaults(self):
        fa = ForecastAlert()
        assert fa.id
        assert fa.forecast_id == ""
        assert fa.service_name == ""
        assert fa.metric_name == ""
        assert fa.predicted_breach_at == 0.0
        assert fa.severity == "warning"
        assert fa.acknowledged is False
        assert fa.created_at > 0

    def test_forecast_report_defaults(self):
        fr = ForecastReport()
        assert fr.total_forecasts == 0
        assert fr.total_alerts == 0
        assert fr.accuracy_pct == 0.0
        assert fr.by_likelihood == {}
        assert fr.by_horizon == {}
        assert fr.by_model == {}
        assert fr.upcoming_anomalies == []
        assert fr.recommendations == []
        assert fr.generated_at > 0


# -------------------------------------------------------------------
# create_forecast
# -------------------------------------------------------------------


class TestCreateForecast:
    def test_basic_create(self):
        eng = _engine()
        fp = eng.create_forecast("svc-a", "cpu")
        assert fp.service_name == "svc-a"
        assert fp.metric_name == "cpu"
        assert len(eng.list_forecasts()) == 1

    def test_create_assigns_unique_ids(self):
        eng = _engine()
        f1 = eng.create_forecast("svc-a", "cpu")
        f2 = eng.create_forecast("svc-b", "mem")
        assert f1.id != f2.id

    def test_create_with_values(self):
        eng = _engine()
        fp = eng.create_forecast(
            "svc-a",
            "latency",
            current_value=100.0,
            predicted_value=120.0,
            anomaly_likelihood=AnomalyLikelihood.HIGH,
            confidence=0.85,
        )
        assert fp.current_value == 100.0
        assert fp.predicted_value == 120.0
        assert fp.anomaly_likelihood == AnomalyLikelihood.HIGH
        assert fp.confidence == 0.85

    def test_eviction_at_max(self):
        eng = _engine(max_forecasts=3)
        ids = []
        for i in range(4):
            fp = eng.create_forecast(f"svc-{i}", "cpu")
            ids.append(fp.id)
        forecasts = eng.list_forecasts(limit=100)
        assert len(forecasts) == 3
        found = {f.id for f in forecasts}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_forecast
# -------------------------------------------------------------------


class TestGetForecast:
    def test_get_existing(self):
        eng = _engine()
        fp = eng.create_forecast("svc-a", "cpu")
        found = eng.get_forecast(fp.id)
        assert found is not None
        assert found.id == fp.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_forecast("nonexistent") is None


# -------------------------------------------------------------------
# list_forecasts
# -------------------------------------------------------------------


class TestListForecasts:
    def test_list_all(self):
        eng = _engine()
        eng.create_forecast("svc-a", "cpu")
        eng.create_forecast("svc-b", "mem")
        eng.create_forecast("svc-c", "latency")
        assert len(eng.list_forecasts()) == 3

    def test_filter_by_service(self):
        eng = _engine()
        eng.create_forecast("svc-a", "cpu")
        eng.create_forecast("svc-b", "cpu")
        eng.create_forecast("svc-a", "mem")
        results = eng.list_forecasts(service_name="svc-a")
        assert len(results) == 2
        assert all(f.service_name == "svc-a" for f in results)

    def test_filter_by_likelihood(self):
        eng = _engine()
        eng.create_forecast(
            "svc-a",
            "cpu",
            anomaly_likelihood=AnomalyLikelihood.HIGH,
        )
        eng.create_forecast(
            "svc-b",
            "cpu",
            anomaly_likelihood=AnomalyLikelihood.LOW,
        )
        results = eng.list_forecasts(
            anomaly_likelihood=AnomalyLikelihood.HIGH,
        )
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.create_forecast(f"svc-{i}", "cpu")
        results = eng.list_forecasts(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# predict_anomaly
# -------------------------------------------------------------------


class TestPredictAnomaly:
    def test_predict_with_values(self):
        eng = _engine()
        fp = eng.predict_anomaly(
            "svc-a",
            "cpu",
            [10.0, 12.0, 11.0, 50.0],
        )
        assert fp.service_name == "svc-a"
        assert fp.current_value == 50.0
        assert fp.predicted_value != 0.0

    def test_predict_empty_values(self):
        eng = _engine()
        fp = eng.predict_anomaly("svc-a", "cpu", [])
        assert fp.service_name == "svc-a"
        assert fp.current_value == 0.0

    def test_predict_high_deviation(self):
        eng = _engine()
        fp = eng.predict_anomaly(
            "svc-a",
            "cpu",
            [10.0, 10.0, 10.0, 10.0, 100.0],
        )
        assert fp.anomaly_likelihood in (
            AnomalyLikelihood.HIGH,
            AnomalyLikelihood.VERY_HIGH,
        )

    def test_predict_stable_values(self):
        eng = _engine()
        fp = eng.predict_anomaly(
            "svc-a",
            "cpu",
            [10.0, 10.0, 10.0, 10.0],
        )
        assert fp.anomaly_likelihood == AnomalyLikelihood.VERY_LOW


# -------------------------------------------------------------------
# create_alert
# -------------------------------------------------------------------


class TestCreateAlert:
    def test_create_alert_success(self):
        eng = _engine()
        fp = eng.create_forecast("svc-a", "cpu")
        alert = eng.create_alert(fp.id, "critical")
        assert alert is not None
        assert alert.forecast_id == fp.id
        assert alert.severity == "critical"

    def test_create_alert_not_found(self):
        eng = _engine()
        assert eng.create_alert("nope") is None

    def test_alert_inherits_service(self):
        eng = _engine()
        fp = eng.create_forecast("svc-a", "latency")
        alert = eng.create_alert(fp.id)
        assert alert is not None
        assert alert.service_name == "svc-a"
        assert alert.metric_name == "latency"


# -------------------------------------------------------------------
# evaluate_accuracy
# -------------------------------------------------------------------


class TestEvaluateAccuracy:
    def test_empty_accuracy(self):
        eng = _engine()
        assert eng.evaluate_accuracy() == 0.0

    def test_all_low_confidence(self):
        eng = _engine(alert_threshold=0.9)
        eng.create_forecast(
            "svc-a",
            "cpu",
            confidence=0.1,
        )
        assert eng.evaluate_accuracy() == 100.0

    def test_high_confidence_high_likelihood(self):
        eng = _engine(alert_threshold=0.5)
        eng.create_forecast(
            "svc-a",
            "cpu",
            anomaly_likelihood=AnomalyLikelihood.HIGH,
            confidence=0.8,
        )
        assert eng.evaluate_accuracy() == 100.0


# -------------------------------------------------------------------
# identify_trending_metrics
# -------------------------------------------------------------------


class TestIdentifyTrendingMetrics:
    def test_trending_detected(self):
        eng = _engine()
        eng.create_forecast(
            "svc-a",
            "cpu",
            predicted_value=10.0,
        )
        eng.create_forecast(
            "svc-a",
            "cpu",
            predicted_value=20.0,
        )
        trends = eng.identify_trending_metrics()
        assert len(trends) == 1
        assert trends[0]["service_name"] == "svc-a"
        assert trends[0]["trend"] == "increasing"

    def test_no_trending(self):
        eng = _engine()
        eng.create_forecast(
            "svc-a",
            "cpu",
            predicted_value=10.0,
        )
        trends = eng.identify_trending_metrics()
        assert trends == []


# -------------------------------------------------------------------
# rank_by_risk
# -------------------------------------------------------------------


class TestRankByRisk:
    def test_ranking_order(self):
        eng = _engine()
        eng.create_forecast(
            "svc-low",
            "cpu",
            anomaly_likelihood=AnomalyLikelihood.LOW,
            confidence=0.1,
        )
        eng.create_forecast(
            "svc-high",
            "cpu",
            anomaly_likelihood=AnomalyLikelihood.VERY_HIGH,
            confidence=0.9,
        )
        ranked = eng.rank_by_risk()
        assert len(ranked) == 2
        assert ranked[0].service_name == "svc-high"

    def test_empty_ranking(self):
        eng = _engine()
        assert eng.rank_by_risk() == []


# -------------------------------------------------------------------
# generate_forecast_report
# -------------------------------------------------------------------


class TestGenerateForecastReport:
    def test_basic_report(self):
        eng = _engine()
        eng.create_forecast(
            "svc-a",
            "cpu",
            anomaly_likelihood=AnomalyLikelihood.HIGH,
        )
        eng.create_forecast(
            "svc-b",
            "mem",
            anomaly_likelihood=AnomalyLikelihood.LOW,
        )
        fp = eng.create_forecast("svc-c", "latency")
        eng.create_alert(fp.id)
        report = eng.generate_forecast_report()
        assert report.total_forecasts == 3
        assert report.total_alerts == 1
        assert isinstance(report.by_likelihood, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_forecast_report()
        assert report.total_forecasts == 0
        assert report.total_alerts == 0
        assert report.accuracy_pct == 0.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.create_forecast("svc-a", "cpu")
        eng.create_forecast("svc-b", "mem")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_forecasts()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_forecasts"] == 0
        assert stats["total_alerts"] == 0
        assert stats["alert_threshold"] == 0.7
        assert stats["likelihood_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.create_forecast(
            "svc-a",
            "cpu",
            anomaly_likelihood=AnomalyLikelihood.HIGH,
        )
        eng.create_forecast(
            "svc-b",
            "mem",
            anomaly_likelihood=AnomalyLikelihood.LOW,
        )
        stats = eng.get_stats()
        assert stats["total_forecasts"] == 2
        assert len(stats["likelihood_distribution"]) == 2
