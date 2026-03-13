"""Tests for CostGovernancePolicyEngine."""

from __future__ import annotations

from shieldops.compliance.cost_governance_policy_engine import (
    ComplianceStatus,
    CostGovernancePolicyEngine,
    EnforcementLevel,
    PolicyType,
)


def _engine(**kw) -> CostGovernancePolicyEngine:
    return CostGovernancePolicyEngine(**kw)


class TestEnums:
    def test_policy_type_values(self):
        for v in PolicyType:
            assert isinstance(v.value, str)

    def test_compliance_status_values(self):
        for v in ComplianceStatus:
            assert isinstance(v.value, str)

    def test_enforcement_level_values(self):
        for v in EnforcementLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(policy_id="p1")
        assert r.policy_id == "p1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(policy_id=f"p-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            policy_id="p1",
            budget_amount=1000,
            actual_amount=800,
        )
        a = eng.process(r.id)
        assert a.budget_utilization == 80.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_zero_budget(self):
        eng = _engine()
        r = eng.add_record(budget_amount=0)
        a = eng.process(r.id)
        assert a.budget_utilization == 0.0


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(policy_id="p1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_violation_recommendation(self):
        eng = _engine()
        eng.add_record(
            compliance_status=ComplianceStatus.VIOLATION,
        )
        rpt = eng.generate_report()
        assert rpt.total_violations == 1
        assert any("violation" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(policy_id="p1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestEnforceBudgetGates:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            team_id="t1",
            budget_amount=1000,
            actual_amount=1200,
        )
        result = eng.enforce_budget_gates()
        assert result[0]["gate_blocked"] is True

    def test_empty(self):
        assert _engine().enforce_budget_gates() == []


class TestEvaluatePolicyCompliance:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            policy_id="p1",
            compliance_status=ComplianceStatus.COMPLIANT,
        )
        result = eng.evaluate_policy_compliance()
        assert result[0]["compliance_rate"] == 100.0

    def test_empty(self):
        assert _engine().evaluate_policy_compliance() == []


class TestDetectPolicyViolations:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            policy_id="p1",
            compliance_status=ComplianceStatus.VIOLATION,
            budget_amount=1000,
            actual_amount=1500,
        )
        result = eng.detect_policy_violations()
        assert result[0]["overage"] == 500.0

    def test_no_violations(self):
        eng = _engine()
        eng.add_record(
            compliance_status=ComplianceStatus.COMPLIANT,
        )
        assert eng.detect_policy_violations() == []
