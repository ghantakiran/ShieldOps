"""Tests for OncallBurdenAnalyzer."""

from __future__ import annotations

from shieldops.incidents.oncall_burden_analyzer import (
    BurdenLevel,
    BurnoutRisk,
    OncallBurdenAnalyzer,
    ShiftPeriod,
)


def _engine(**kw) -> OncallBurdenAnalyzer:
    return OncallBurdenAnalyzer(**kw)


class TestEnums:
    def test_burden_level_values(self):
        for v in BurdenLevel:
            assert isinstance(v.value, str)

    def test_shift_period_values(self):
        for v in ShiftPeriod:
            assert isinstance(v.value, str)

    def test_burnout_risk_values(self):
        for v in BurnoutRisk:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(responder_id="r1")
        assert r.responder_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(responder_id=f"r-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.add_record(
            responder_id="r1",
            pages_received=20,
            hours_on_call=8.0,
        )
        assert r.pages_received == 20


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            responder_id="r1",
            pages_received=10,
        )
        a = eng.process(r.id)
        assert hasattr(a, "responder_id")
        assert a.responder_id == "r1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(responder_id="r1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(responder_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(responder_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestCalculateBurdenIndex:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            responder_id="r1",
            pages_received=20,
            hours_on_call=8.0,
        )
        result = eng.calculate_burden_index()
        assert len(result) == 1
        assert "burden_index" in result[0]

    def test_empty(self):
        assert _engine().calculate_burden_index() == []


class TestDetectBurdenImbalance:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            responder_id="r1",
            team="sre",
            pages_received=50,
        )
        eng.add_record(
            responder_id="r2",
            team="sre",
            pages_received=5,
        )
        result = eng.detect_burden_imbalance()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().detect_burden_imbalance()
        assert r == []


class TestForecastBurnoutRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            responder_id="r1",
            pages_received=30,
            shift_period=ShiftPeriod.OVERNIGHT,
        )
        result = eng.forecast_burnout_risk()
        assert len(result) == 1
        assert "risk_level" in result[0]

    def test_empty(self):
        assert _engine().forecast_burnout_risk() == []
