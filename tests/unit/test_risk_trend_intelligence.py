"""Tests for RiskTrendIntelligence."""

from __future__ import annotations

from shieldops.analytics.risk_trend_intelligence import (
    RiskDomain,
    RiskTrendIntelligence,
    TrendDirection,
    TrendWindow,
)


def _engine(**kw) -> RiskTrendIntelligence:
    return RiskTrendIntelligence(**kw)


class TestEnums:
    def test_trend_window_values(self):
        for v in TrendWindow:
            assert isinstance(v.value, str)

    def test_trend_direction_values(self):
        for v in TrendDirection:
            assert isinstance(v.value, str)

    def test_risk_domain_values(self):
        for v in RiskDomain:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(trend_id="t1")
        assert r.trend_id == "t1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(trend_id=f"t-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            trend_id="t1",
            risk_score=70.0,
            previous_score=50.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "trend_id")
        assert a.trend_id == "t1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(trend_id="t1")
        assert eng.generate_report().total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(trend_id="t1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(trend_id="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeRiskTrajectory:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            trend_id="t1",
            domain=RiskDomain.NETWORK,
            risk_score=80.0,
            previous_score=60.0,
        )
        result = eng.compute_risk_trajectory()
        assert len(result) == 1
        assert result[0]["domain"] == "network"

    def test_empty(self):
        assert _engine().compute_risk_trajectory() == []


class TestDetectRiskAnomalies:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            trend_id="t1",
            risk_score=90.0,
            previous_score=40.0,
        )
        result = eng.detect_risk_anomalies()
        assert len(result) == 1
        assert result[0]["delta"] == 50.0

    def test_empty(self):
        assert _engine().detect_risk_anomalies() == []


class TestForecastRiskLevels:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            trend_id="t1",
            domain=RiskDomain.IDENTITY,
            risk_score=70.0,
            previous_score=60.0,
        )
        result = eng.forecast_risk_levels()
        assert len(result) == 1
        assert "forecast_score" in result[0]

    def test_empty(self):
        assert _engine().forecast_risk_levels() == []
