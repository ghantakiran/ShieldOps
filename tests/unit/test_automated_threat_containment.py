"""Tests for AutomatedThreatContainment."""

from __future__ import annotations

from shieldops.security.automated_threat_containment import (
    AutomatedThreatContainment,
    ContainmentAction,
    ContainmentResult,
    ContainmentStrategy,
    ThreatContainmentReport,
    ThreatRecord,
    ThreatSeverity,
)


def _engine(**kw) -> AutomatedThreatContainment:
    return AutomatedThreatContainment(**kw)


# --- Enum tests ---


class TestEnums:
    def test_severity_low(self):
        assert ThreatSeverity.LOW == "low"

    def test_severity_critical(self):
        assert ThreatSeverity.CRITICAL == "critical"

    def test_strategy_isolate(self):
        assert ContainmentStrategy.ISOLATE_HOST == "isolate_host"

    def test_strategy_block(self):
        assert ContainmentStrategy.BLOCK_IP == "block_ip"

    def test_strategy_disable(self):
        assert ContainmentStrategy.DISABLE_ACCOUNT == "disable_account"

    def test_strategy_quarantine(self):
        assert ContainmentStrategy.QUARANTINE_FILE == "quarantine_file"

    def test_strategy_rate(self):
        assert ContainmentStrategy.RATE_LIMIT == "rate_limit"

    def test_strategy_kill(self):
        assert ContainmentStrategy.KILL_PROCESS == "kill_process"

    def test_result_success(self):
        assert ContainmentResult.SUCCESS == "success"

    def test_result_partial(self):
        assert ContainmentResult.PARTIAL == "partial"

    def test_result_verified(self):
        assert ContainmentResult.VERIFIED == "verified"


# --- Model tests ---


class TestModels:
    def test_threat_defaults(self):
        t = ThreatRecord()
        assert t.id
        assert t.severity == ThreatSeverity.LOW
        assert t.result == ContainmentResult.PENDING

    def test_action_defaults(self):
        a = ContainmentAction()
        assert a.id
        assert a.verified is False

    def test_report_defaults(self):
        r = ThreatContainmentReport()
        assert r.total_threats == 0
        assert r.success_rate == 0.0


# --- assess_threat ---


class TestAssessThreat:
    def test_critical_auto_strategy(self):
        eng = _engine()
        t = eng.assess_threat(name="apt", severity=ThreatSeverity.CRITICAL, risk_score=95.0)
        assert t.strategy == ContainmentStrategy.ISOLATE_HOST

    def test_high_auto_strategy(self):
        eng = _engine()
        t = eng.assess_threat(name="scan", severity=ThreatSeverity.HIGH)
        assert t.strategy == ContainmentStrategy.BLOCK_IP

    def test_medium_auto_strategy(self):
        eng = _engine()
        t = eng.assess_threat(name="probe", severity=ThreatSeverity.MEDIUM)
        assert t.strategy == ContainmentStrategy.RATE_LIMIT

    def test_low_auto_strategy(self):
        eng = _engine()
        t = eng.assess_threat(name="file", severity=ThreatSeverity.LOW)
        assert t.strategy == ContainmentStrategy.QUARANTINE_FILE

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.assess_threat(name=f"t-{i}")
        assert len(eng._threats) == 3


# --- select_containment_strategy ---


class TestSelectStrategy:
    def test_override(self):
        eng = _engine()
        t = eng.assess_threat(name="test")
        result = eng.select_containment_strategy(t.id, ContainmentStrategy.KILL_PROCESS)
        assert result["strategy"] == "kill_process"
        assert t.strategy == ContainmentStrategy.KILL_PROCESS

    def test_not_found(self):
        eng = _engine()
        result = eng.select_containment_strategy("unknown", ContainmentStrategy.BLOCK_IP)
        assert result["error"] == "not_found"


# --- execute_containment ---


class TestExecuteContainment:
    def test_success(self):
        eng = _engine()
        t = eng.assess_threat(name="test")
        a = eng.execute_containment(t.id, success=True, duration_ms=50.0)
        assert a.result == ContainmentResult.SUCCESS
        assert t.result == ContainmentResult.SUCCESS

    def test_failure(self):
        eng = _engine()
        t = eng.assess_threat(name="test")
        a = eng.execute_containment(t.id, success=False)
        assert a.result == ContainmentResult.FAILED


# --- verify_containment ---


class TestVerifyContainment:
    def test_verified(self):
        eng = _engine()
        t = eng.assess_threat(name="test")
        eng.execute_containment(t.id, success=True)
        result = eng.verify_containment(t.id)
        assert result["verified"] is True
        assert t.result == ContainmentResult.VERIFIED

    def test_not_verified(self):
        eng = _engine()
        t = eng.assess_threat(name="test")
        eng.execute_containment(t.id, success=False)
        result = eng.verify_containment(t.id)
        assert result["verified"] is False

    def test_no_actions(self):
        eng = _engine()
        result = eng.verify_containment("unknown")
        assert result["verified"] is False


# --- document_actions ---


class TestDocumentActions:
    def test_basic(self):
        eng = _engine()
        t = eng.assess_threat(name="test")
        eng.execute_containment(t.id, success=True, notes="contained")
        docs = eng.document_actions(t.id)
        assert len(docs) == 1
        assert docs[0]["notes"] == "contained"

    def test_empty(self):
        eng = _engine()
        assert eng.document_actions("unknown") == []


# --- generate_report ---


class TestReport:
    def test_populated(self):
        eng = _engine(risk_threshold=50.0)
        t = eng.assess_threat(name="test", risk_score=80.0)
        eng.execute_containment(t.id, success=True)
        report = eng.generate_report()
        assert isinstance(report, ThreatContainmentReport)
        assert report.total_threats == 1
        assert report.success_rate == 100.0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "healthy range" in report.recommendations[0]


# --- stats / clear ---


class TestStatsAndClear:
    def test_stats(self):
        eng = _engine()
        eng.assess_threat(name="a", service="s", team="t")
        stats = eng.get_stats()
        assert stats["total_threats"] == 1

    def test_clear(self):
        eng = _engine()
        eng.assess_threat(name="test")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._threats) == 0
