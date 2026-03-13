"""Tests for AlertSuppressionIntelligence."""

from __future__ import annotations

from shieldops.observability.alert_suppression_intelligence import (
    AlertSuppressionIntelligence,
    SafetyLevel,
    SuppressionReason,
    WindowType,
)


def _engine(**kw) -> AlertSuppressionIntelligence:
    return AlertSuppressionIntelligence(**kw)


class TestEnums:
    def test_suppression_reason_values(self):
        for v in SuppressionReason:
            assert isinstance(v.value, str)

    def test_safety_level_values(self):
        for v in SafetyLevel:
            assert isinstance(v.value, str)

    def test_window_type_values(self):
        for v in WindowType:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(alert_name="cpu_high")
        assert r.alert_name == "cpu_high"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(alert_name=f"a-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.add_record(
            alert_name="cpu_high",
            duration_min=30.0,
            alerts_suppressed=50,
        )
        assert r.alerts_suppressed == 50


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            alert_name="cpu_high",
            alerts_suppressed=10,
        )
        a = eng.process(r.id)
        assert hasattr(a, "alert_name")
        assert a.alert_name == "cpu_high"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_name="cpu_high")
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
        eng.add_record(alert_name="cpu_high")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(alert_name="cpu_high")
        eng.clear_data()
        assert len(eng._records) == 0


class TestLearnSuppressionWindows:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_name="cpu_high",
            duration_min=30.0,
        )
        result = eng.learn_suppression_windows()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().learn_suppression_windows()
        assert r == []


class TestEvaluateSuppressionSafety:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_name="cpu_high",
            alerts_suppressed=100,
            missed_incidents=1,
        )
        result = eng.evaluate_suppression_safety()
        assert len(result) == 1
        assert "safety_assessment" in result[0]

    def test_empty(self):
        r = _engine().evaluate_suppression_safety()
        assert r == []


class TestAutoTuneSuppressionRules:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_name="cpu_high",
            duration_min=30.0,
            alerts_suppressed=100,
            missed_incidents=10,
        )
        result = eng.auto_tune_suppression_rules()
        assert len(result) == 1
        assert "action" in result[0]

    def test_empty(self):
        r = _engine().auto_tune_suppression_rules()
        assert r == []
