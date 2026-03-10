"""Tests for ObservabilityAutomationEngine."""

from __future__ import annotations

from shieldops.observability.observability_automation_engine import (
    ActionType,
    AutomationOutcome,
    AutomationTrigger,
    ObservabilityAutomationEngine,
)


def _engine(**kw) -> ObservabilityAutomationEngine:
    return ObservabilityAutomationEngine(**kw)


class TestEnums:
    def test_automation_trigger(self):
        assert AutomationTrigger.THRESHOLD_BREACH == "threshold_breach"
        assert AutomationTrigger.SCHEDULE == "schedule"

    def test_action_type(self):
        assert ActionType.ALERT_CREATE == "alert_create"
        assert ActionType.ESCALATE == "escalate"

    def test_automation_outcome(self):
        assert AutomationOutcome.SUCCESS == "success"
        assert AutomationOutcome.SKIPPED == "skipped"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="auto-1", service="api")
        assert rec.name == "auto-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"a-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="auto-1", score=85.0)
        result = eng.process("auto-1")
        assert result["key"] == "auto-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(name="a1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.add_record(name="a1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(name="a1", service="api")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestEvaluateTriggerConditions:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="a1",
            trigger=AutomationTrigger.ANOMALY_DETECTED,
            outcome=AutomationOutcome.SUCCESS,
            execution_time_ms=150.0,
        )
        result = eng.evaluate_trigger_conditions()
        assert isinstance(result, dict)
        assert "anomaly_detected" in result

    def test_empty(self):
        eng = _engine()
        result = eng.evaluate_trigger_conditions()
        assert result["status"] == "no_data"


class TestExecuteAutomatedResponse:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="a1",
            trigger=AutomationTrigger.THRESHOLD_BREACH,
            action_type=ActionType.ALERT_CREATE,
            outcome=AutomationOutcome.SUCCESS,
        )
        result = eng.execute_automated_response(
            trigger=AutomationTrigger.THRESHOLD_BREACH,
            action=ActionType.ALERT_CREATE,
        )
        assert "historical_success_rate" in result

    def test_no_match(self):
        eng = _engine()
        result = eng.execute_automated_response(
            trigger=AutomationTrigger.SCHEDULE,
            action=ActionType.ESCALATE,
        )
        assert result["status"] == "no_matching_rules"


class TestMeasureAutomationEffectiveness:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="a1",
            action_type=ActionType.RULE_MODIFY,
            effectiveness=0.85,
            execution_time_ms=200.0,
        )
        result = eng.measure_automation_effectiveness()
        assert "overall_effectiveness" in result

    def test_empty(self):
        eng = _engine()
        result = eng.measure_automation_effectiveness()
        assert result["status"] == "no_data"
