"""Tests for CapacityDemandForecaster."""

from __future__ import annotations

from shieldops.analytics.capacity_demand_forecaster import (
    CapacityDemandForecaster,
    DemandTrend,
    ForecastHorizon,
    ResourceType,
)


def _engine(**kw) -> CapacityDemandForecaster:
    return CapacityDemandForecaster(**kw)


class TestEnums:
    def test_forecast_horizon_values(self):
        for v in ForecastHorizon:
            assert isinstance(v.value, str)

    def test_resource_type_values(self):
        for v in ResourceType:
            assert isinstance(v.value, str)

    def test_demand_trend_values(self):
        for v in DemandTrend:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(resource_id="r1")
        assert r.resource_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(resource_id=f"r-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.add_record(
            resource_id="r1",
            forecast_horizon=ForecastHorizon.LONG_TERM,
            resource_type=ResourceType.MEMORY,
            current_usage=75.0,
            capacity_limit=100.0,
            forecast_value=95.0,
        )
        assert r.current_usage == 75.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(resource_id="r1", current_usage=80.0, capacity_limit=100.0)
        a = eng.process(r.id)
        assert hasattr(a, "resource_id")
        assert a.resource_id == "r1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_exhaustion_risk(self):
        eng = _engine()
        r = eng.add_record(
            resource_id="r1",
            forecast_value=95.0,
            capacity_limit=100.0,
        )
        a = eng.process(r.id)
        assert a.exhaustion_risk is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(resource_id="r1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(resource_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(resource_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeDemandForecast:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(resource_id="r1", forecast_value=80.0)
        result = eng.compute_demand_forecast()
        assert len(result) == 1
        assert result[0]["resource_id"] == "r1"

    def test_empty(self):
        assert _engine().compute_demand_forecast() == []


class TestDetectCapacityExhaustionRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            resource_id="r1",
            forecast_value=95.0,
            capacity_limit=100.0,
        )
        result = eng.detect_capacity_exhaustion_risk()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_capacity_exhaustion_risk() == []


class TestRankResourcesByScalingUrgency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(resource_id="r1", forecast_value=80.0, capacity_limit=100.0)
        eng.add_record(resource_id="r2", forecast_value=95.0, capacity_limit=100.0)
        result = eng.rank_resources_by_scaling_urgency()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_resources_by_scaling_urgency() == []
