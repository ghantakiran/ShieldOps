"""Tests for AutonomousComplianceEngine."""

from __future__ import annotations

from shieldops.compliance.autonomous_compliance_engine import (
    AutomationLevel,
    AutonomousComplianceEngine,
    ComplianceAction,
    FrameworkScope,
)


def _engine(**kw) -> AutonomousComplianceEngine:
    return AutonomousComplianceEngine(**kw)


class TestEnums:
    def test_compliance_action_values(self):
        assert ComplianceAction.ASSESS == "assess"
        assert ComplianceAction.REMEDIATE == "remediate"
        assert ComplianceAction.VERIFY == "verify"
        assert ComplianceAction.REPORT == "report"

    def test_framework_scope_values(self):
        assert FrameworkScope.SOC2 == "soc2"
        assert FrameworkScope.HIPAA == "hipaa"
        assert FrameworkScope.PCI == "pci"
        assert FrameworkScope.ISO27001 == "iso27001"

    def test_automation_level_values(self):
        assert AutomationLevel.MANUAL == "manual"
        assert AutomationLevel.ASSISTED == "assisted"
        assert AutomationLevel.AUTOMATED == "automated"
        assert AutomationLevel.AUTONOMOUS == "autonomous"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            name="comp-001",
            compliance_action=ComplianceAction.ASSESS,
            framework_scope=FrameworkScope.SOC2,
            score=85.0,
            service="auth",
            team="compliance",
        )
        assert r.name == "comp-001"
        assert r.compliance_action == ComplianceAction.ASSESS
        assert r.score == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="test", score=40.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1

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
        eng.add_record(name="t", service="a", team="b")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(name="test")
        eng.add_analysis(name="test")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestAutoAssessControls:
    def test_with_data(self):
        eng = _engine(threshold=50.0)
        eng.add_record(
            name="a",
            framework_scope=FrameworkScope.SOC2,
            score=80.0,
        )
        eng.add_record(
            name="b",
            framework_scope=FrameworkScope.SOC2,
            score=30.0,
        )
        results = eng.auto_assess_controls()
        assert len(results) == 1
        assert results[0]["framework"] == "soc2"
        assert results[0]["passing"] == 1
        assert results[0]["failing"] == 1

    def test_empty(self):
        eng = _engine()
        assert eng.auto_assess_controls() == []


class TestGenerateRemediationPlan:
    def test_with_failing_controls(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="fail", score=30.0)
        eng.add_record(name="pass", score=90.0)
        plan = eng.generate_remediation_plan()
        assert len(plan) == 1
        assert plan[0]["name"] == "fail"
        assert plan[0]["gap"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.generate_remediation_plan() == []


class TestComputeComplianceVelocity:
    def test_improving(self):
        eng = _engine()
        eng.add_record(name="a", score=30.0)
        eng.add_record(name="b", score=30.0)
        eng.add_record(name="c", score=80.0)
        eng.add_record(name="d", score=80.0)
        result = eng.compute_compliance_velocity()
        assert result["velocity"] > 0
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        eng.add_record(name="a", score=50.0)
        result = eng.compute_compliance_velocity()
        assert result["reason"] == "insufficient_data"
