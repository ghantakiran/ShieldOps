"""Tests for RiskResponseAutomator."""

from __future__ import annotations

from shieldops.security.risk_response_automator import (
    AutomationLevel,
    ResponseAction,
    ResponseOutcome,
    RiskResponseAutomator,
)


def _engine(**kw) -> RiskResponseAutomator:
    return RiskResponseAutomator(**kw)


class TestEnums:
    def test_response_action_values(self):
        for v in ResponseAction:
            assert isinstance(v.value, str)

    def test_automation_level_values(self):
        for v in AutomationLevel:
            assert isinstance(v.value, str)

    def test_response_outcome_values(self):
        for v in ResponseOutcome:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(response_id="r1")
        assert r.response_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(response_id=f"r-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(response_id="r1")
        a = eng.process(r.id)
        assert hasattr(a, "response_id")
        assert a.response_id == "r1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(response_id="r1")
        assert eng.generate_report().total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(response_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(response_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestSelectResponseAction:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            response_id="r1",
            entity_id="e1",
            risk_score=95.0,
        )
        result = eng.select_response_action()
        assert len(result) == 1
        assert result[0]["recommended_action"] == "block"

    def test_empty(self):
        assert _engine().select_response_action() == []


class TestComputeResponseEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            response_id="r1",
            outcome=ResponseOutcome.CONTAINED,
        )
        result = eng.compute_response_effectiveness()
        assert result["overall_effectiveness"] == 1.0

    def test_empty(self):
        result = _engine().compute_response_effectiveness()
        assert result["overall_effectiveness"] == 0.0


class TestDetectResponseDelays:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            response_id="r1",
            entity_id="e1",
            response_time_sec=600.0,
        )
        result = eng.detect_response_delays()
        assert len(result) == 1
        assert result[0]["delay_sec"] == 300.0

    def test_empty(self):
        assert _engine().detect_response_delays() == []
