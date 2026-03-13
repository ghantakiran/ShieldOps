"""Tests for CloudSpendForecaster."""

from __future__ import annotations

from shieldops.billing.cloud_spend_forecaster import (
    CloudSpendForecaster,
    ForecastHorizon,
    GrowthModel,
    SeasonalityType,
)


def _engine(**kw) -> CloudSpendForecaster:
    return CloudSpendForecaster(**kw)


class TestEnums:
    def test_forecast_horizon_values(self):
        for v in ForecastHorizon:
            assert isinstance(v.value, str)

    def test_seasonality_type_values(self):
        for v in SeasonalityType:
            assert isinstance(v.value, str)

    def test_growth_model_values(self):
        for v in GrowthModel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(account_id="a1")
        assert r.account_id == "a1"

    def test_with_params(self):
        eng = _engine()
        r = eng.add_record(
            account_id="a1",
            current_spend=1000.0,
            projected_spend=1500.0,
        )
        assert r.current_spend == 1000.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(account_id=f"a-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            account_id="a1",
            current_spend=1000.0,
            projected_spend=1500.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "account_id")
        assert a.growth_rate == 50.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_zero_spend(self):
        eng = _engine()
        r = eng.add_record(current_spend=0.0)
        a = eng.process(r.id)
        assert a.growth_rate == 0.0


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(account_id="a1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_high_growth_recommendation(self):
        eng = _engine()
        eng.add_record(current_spend=100, projected_spend=200)
        rpt = eng.generate_report()
        assert any("growth" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(account_id="a1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(account_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestForecastSpendHorizon:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            account_id="a1",
            current_spend=1000,
            projected_spend=1500,
        )
        result = eng.forecast_spend_horizon()
        assert len(result) == 1
        assert result[0]["delta"] == 500.0

    def test_empty(self):
        assert _engine().forecast_spend_horizon() == []


class TestDetectSpendSeasonality:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(current_spend=100)
        result = eng.detect_spend_seasonality()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_spend_seasonality() == []


class TestSimulateGrowthScenario:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(projected_spend=500)
        result = eng.simulate_growth_scenario()
        assert len(result) == 1
        assert result[0]["avg_projected"] == 500.0

    def test_empty(self):
        assert _engine().simulate_growth_scenario() == []
