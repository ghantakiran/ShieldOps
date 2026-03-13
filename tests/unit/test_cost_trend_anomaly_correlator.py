"""Tests for CostTrendAnomalyCorrelator."""

from __future__ import annotations

from shieldops.analytics.cost_trend_anomaly_correlator import (
    CorrelationType,
    CostTrendAnomalyCorrelator,
    ForecastConfidence,
    TrendDirection,
)


def _engine(**kw) -> CostTrendAnomalyCorrelator:
    return CostTrendAnomalyCorrelator(**kw)


class TestEnums:
    def test_trend_direction_values(self):
        for v in TrendDirection:
            assert isinstance(v.value, str)

    def test_correlation_type_values(self):
        for v in CorrelationType:
            assert isinstance(v.value, str)

    def test_forecast_confidence_values(self):
        for v in ForecastConfidence:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(service_name="svc1")
        assert r.service_name == "svc1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(service_name=f"s-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            service_name="svc1",
            current_cost=1500,
            previous_cost=1000,
        )
        a = eng.process(r.id)
        assert a.change_pct == 50.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_zero_previous(self):
        eng = _engine()
        r = eng.add_record(previous_cost=0)
        a = eng.process(r.id)
        assert a.change_pct == 0.0


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(service_name="svc1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_increasing_recommendation(self):
        eng = _engine()
        eng.add_record(
            trend_direction=TrendDirection.INCREASING,
        )
        rpt = eng.generate_report()
        assert any("increasing" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(service_name="svc1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestCorrelateCostWithDeployments:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            service_name="svc1",
            correlation_type=CorrelationType.DEPLOYMENT,
            current_cost=1500,
            previous_cost=1000,
        )
        result = eng.correlate_cost_with_deployments()
        assert len(result) == 1
        assert result[0]["total_cost_impact"] == 500.0

    def test_empty(self):
        assert _engine().correlate_cost_with_deployments() == []

    def test_non_deploy_excluded(self):
        eng = _engine()
        eng.add_record(
            correlation_type=CorrelationType.TRAFFIC,
        )
        assert eng.correlate_cost_with_deployments() == []


class TestAttributeTrendToBusinessEvents:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            event_id="evt1",
            current_cost=200,
            previous_cost=100,
        )
        result = eng.attribute_trend_to_business_events()
        assert len(result) == 1
        assert result[0]["event_id"] == "evt1"

    def test_no_events(self):
        eng = _engine()
        eng.add_record(event_id="")
        assert eng.attribute_trend_to_business_events() == []


class TestForecastTrendContinuation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            service_name="svc1",
            current_cost=150,
            previous_cost=100,
        )
        result = eng.forecast_trend_continuation()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().forecast_trend_continuation() == []
