"""Tests for OperationalForecastingEngine."""

from __future__ import annotations

from shieldops.analytics.operational_forecasting_engine import (
    ForecastAccuracy,
    ForecastHorizon,
    ForecastMethod,
    OperationalForecastingEngine,
)


def _engine(**kw) -> OperationalForecastingEngine:
    return OperationalForecastingEngine(**kw)


class TestEnums:
    def test_forecast_horizon(self):
        assert ForecastHorizon.ONE_DAY == "one_day"

    def test_forecast_method(self):
        assert ForecastMethod.ARIMA == "arima"

    def test_forecast_accuracy(self):
        assert ForecastAccuracy.EXCELLENT == "excellent"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(metric_name="cpu_usage", service="api")
        assert rec.metric_name == "cpu_usage"
        assert rec.service == "api"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(metric_name=f"m-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(metric_name="cpu_usage", service="api")
        result = eng.process("cpu_usage")
        assert isinstance(result, dict)
        assert result["metric_name"] == "cpu_usage"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateForecast:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            metric_name="cpu",
            service="api",
            predicted_value=75.0,
        )
        result = eng.generate_forecast("cpu")
        assert isinstance(result, dict)


class TestEvaluateAccuracy:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            metric_name="cpu",
            service="api",
            actual_value=80.0,
            accuracy_score=0.9,
        )
        result = eng.evaluate_accuracy()
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", service="api")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0
