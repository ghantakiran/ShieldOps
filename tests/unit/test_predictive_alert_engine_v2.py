"""Tests for shieldops.observability.predictive_alert_engine_v2 — PredictiveAlertEngineV2."""

from __future__ import annotations

from shieldops.observability.predictive_alert_engine_v2 import (
    AlertSeverity,
    ModelInfo,
    ModelStatus,
    PredictionConfidence,
    PredictionRecord,
    PredictiveAlertEngineV2,
    PredictiveAlertReport,
)


def _engine(**kw) -> PredictiveAlertEngineV2:
    return PredictiveAlertEngineV2(**kw)


class TestEnums:
    def test_confidence_high(self):
        assert PredictionConfidence.HIGH == "high"

    def test_confidence_medium(self):
        assert PredictionConfidence.MEDIUM == "medium"

    def test_confidence_low(self):
        assert PredictionConfidence.LOW == "low"

    def test_confidence_uncertain(self):
        assert PredictionConfidence.UNCERTAIN == "uncertain"

    def test_severity_critical(self):
        assert AlertSeverity.CRITICAL == "critical"

    def test_severity_warning(self):
        assert AlertSeverity.WARNING == "warning"

    def test_severity_info(self):
        assert AlertSeverity.INFO == "info"

    def test_model_status_trained(self):
        assert ModelStatus.TRAINED == "trained"

    def test_model_status_untrained(self):
        assert ModelStatus.UNTRAINED == "untrained"

    def test_model_status_stale(self):
        assert ModelStatus.STALE == "stale"

    def test_model_status_failed(self):
        assert ModelStatus.FAILED == "failed"


class TestModels:
    def test_prediction_defaults(self):
        p = PredictionRecord()
        assert p.id
        assert p.metric_name == ""
        assert p.predicted_value == 0.0
        assert p.actual_value is None
        assert p.severity == AlertSeverity.INFO
        assert p.confidence == PredictionConfidence.UNCERTAIN
        assert p.horizon_minutes == 30

    def test_model_info_defaults(self):
        m = ModelInfo()
        assert m.id
        assert m.status == ModelStatus.UNTRAINED
        assert m.accuracy == 0.0
        assert m.samples_trained == 0

    def test_report_defaults(self):
        r = PredictiveAlertReport()
        assert r.total_predictions == 0
        assert r.total_models == 0


class TestPredictAlerts:
    def test_critical_prediction(self):
        eng = _engine()
        p = eng.predict_alerts("cpu_usage", 85.0)
        assert p.severity == AlertSeverity.CRITICAL
        assert p.confidence == PredictionConfidence.HIGH

    def test_warning_prediction(self):
        eng = _engine()
        p = eng.predict_alerts("memory", 65.0)
        assert p.severity == AlertSeverity.WARNING

    def test_info_prediction(self):
        eng = _engine()
        p = eng.predict_alerts("disk", 30.0)
        assert p.severity == AlertSeverity.INFO

    def test_custom_horizon(self):
        eng = _engine()
        p = eng.predict_alerts("cpu", 50.0, horizon_minutes=60)
        assert p.horizon_minutes == 60

    def test_eviction(self):
        eng = _engine(max_predictions=3)
        for i in range(5):
            eng.predict_alerts(f"m-{i}", 50.0)
        assert len(eng._predictions) == 3


class TestTrainModel:
    def test_trained(self):
        eng = _engine()
        m = eng.train_model("cpu_model", samples=100)
        assert m.status == ModelStatus.TRAINED
        assert m.accuracy > 0.5

    def test_untrained_low_samples(self):
        eng = _engine()
        m = eng.train_model("low_model", samples=5)
        assert m.status == ModelStatus.UNTRAINED

    def test_zero_samples(self):
        eng = _engine()
        m = eng.train_model("empty_model", samples=0)
        assert m.accuracy == 0.0


class TestEvaluatePredictions:
    def test_no_actuals(self):
        eng = _engine()
        eng.predict_alerts("cpu", 50.0)
        result = eng.evaluate_predictions()
        assert result["evaluated"] == 0

    def test_with_actuals(self):
        eng = _engine()
        p = eng.predict_alerts("cpu", 50.0)
        p.actual_value = 55.0
        result = eng.evaluate_predictions()
        assert result["evaluated"] == 1
        assert result["accuracy"] > 0

    def test_empty(self):
        eng = _engine()
        result = eng.evaluate_predictions()
        assert result["evaluated"] == 0


class TestGetAlertForecast:
    def test_empty(self):
        eng = _engine()
        assert eng.get_alert_forecast() == []

    def test_with_predictions(self):
        eng = _engine()
        eng.predict_alerts("cpu", 85.0)
        eng.predict_alerts("mem", 30.0)
        forecast = eng.get_alert_forecast()
        assert len(forecast) > 0

    def test_custom_hours(self):
        eng = _engine()
        eng.predict_alerts("cpu", 85.0)
        forecast = eng.get_alert_forecast(hours_ahead=48)
        assert forecast[0]["projected_count"] > 0


class TestTuneSensitivity:
    def test_adjust_up(self):
        eng = _engine()
        eng.predict_alerts("cpu", 50.0)
        result = eng.tune_sensitivity("cpu", adjustment=0.1)
        assert result["affected_count"] == 1

    def test_adjust_no_match(self):
        eng = _engine()
        result = eng.tune_sensitivity("nonexistent", adjustment=0.1)
        assert result["affected_count"] == 0

    def test_clamped_to_bounds(self):
        eng = _engine()
        p = eng.predict_alerts("cpu", 50.0)
        eng.tune_sensitivity("cpu", adjustment=5.0)
        assert p.score <= 1.0


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_predictions == 0

    def test_populated(self):
        eng = _engine()
        eng.predict_alerts("cpu", 85.0)
        eng.train_model("m1", samples=100)
        report = eng.generate_report()
        assert report.total_predictions == 1
        assert report.total_models == 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.predict_alerts("cpu", 50.0)
        eng.train_model("m1", samples=10)
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._predictions) == 0
        assert len(eng._models) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_predictions"] == 0

    def test_populated(self):
        eng = _engine()
        eng.predict_alerts("cpu", 50.0)
        stats = eng.get_stats()
        assert stats["unique_metrics"] == 1
