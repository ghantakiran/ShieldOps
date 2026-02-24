"""Tests for shieldops.changes.deployment_gate — DeploymentApprovalGate."""

from __future__ import annotations

from shieldops.changes.deployment_gate import (
    ApprovalLevel,
    DeploymentApprovalGate,
    DeploymentGate,
    GateDecision,
    GateReport,
    GateStatus,
    GateType,
)


def _engine(**kw) -> DeploymentApprovalGate:
    return DeploymentApprovalGate(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # GateStatus (5 values)

    def test_gate_status_pending(self):
        assert GateStatus.PENDING == "pending"

    def test_gate_status_approved(self):
        assert GateStatus.APPROVED == "approved"

    def test_gate_status_rejected(self):
        assert GateStatus.REJECTED == "rejected"

    def test_gate_status_auto_approved(self):
        assert GateStatus.AUTO_APPROVED == "auto_approved"

    def test_gate_status_expired(self):
        assert GateStatus.EXPIRED == "expired"

    # GateType (5 values)

    def test_gate_type_manual_review(self):
        assert GateType.MANUAL_REVIEW == "manual_review"

    def test_gate_type_automated_check(self):
        assert GateType.AUTOMATED_CHECK == "automated_check"

    def test_gate_type_security_scan(self):
        assert GateType.SECURITY_SCAN == "security_scan"

    def test_gate_type_load_test(self):
        assert GateType.LOAD_TEST == "load_test"

    def test_gate_type_canary_validation(self):
        assert GateType.CANARY_VALIDATION == "canary_validation"

    # ApprovalLevel (5 values)

    def test_approval_level_team_lead(self):
        assert ApprovalLevel.TEAM_LEAD == "team_lead"

    def test_approval_level_engineering_manager(self):
        assert ApprovalLevel.ENGINEERING_MANAGER == "engineering_manager"

    def test_approval_level_sre_on_call(self):
        assert ApprovalLevel.SRE_ON_CALL == "sre_on_call"

    def test_approval_level_security_team(self):
        assert ApprovalLevel.SECURITY_TEAM == "security_team"

    def test_approval_level_vp_engineering(self):
        assert ApprovalLevel.VP_ENGINEERING == "vp_engineering"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_deployment_gate_defaults(self):
        gate = DeploymentGate()
        assert gate.id
        assert gate.deployment_id == ""
        assert gate.service_name == ""
        assert gate.gate_type == GateType.MANUAL_REVIEW
        assert gate.status == GateStatus.PENDING
        assert gate.approval_level == ApprovalLevel.TEAM_LEAD
        assert gate.approver == ""
        assert gate.reason == ""
        assert gate.pre_checks == []
        assert gate.expires_at == 0.0
        assert gate.created_at > 0

    def test_gate_decision_defaults(self):
        decision = GateDecision()
        assert decision.id
        assert decision.gate_id == ""
        assert decision.decision == ""
        assert decision.decided_by == ""
        assert decision.rationale == ""
        assert decision.decided_at == 0.0
        assert decision.created_at > 0

    def test_gate_report_defaults(self):
        report = GateReport()
        assert report.total_gates == 0
        assert report.total_decisions == 0
        assert report.approval_rate_pct == 0.0
        assert report.avg_wait_hours == 0.0
        assert report.by_status == {}
        assert report.by_type == {}
        assert report.slow_gates == []
        assert report.recommendations == []
        assert report.generated_at > 0


# -------------------------------------------------------------------
# create_gate
# -------------------------------------------------------------------


class TestCreateGate:
    def test_basic_create(self):
        eng = _engine()
        gate = eng.create_gate("deploy-1")
        assert gate.deployment_id == "deploy-1"
        assert gate.status == GateStatus.PENDING
        assert len(eng.list_gates()) == 1

    def test_create_assigns_unique_ids(self):
        eng = _engine()
        g1 = eng.create_gate("deploy-1")
        g2 = eng.create_gate("deploy-2")
        assert g1.id != g2.id

    def test_create_with_params(self):
        eng = _engine()
        gate = eng.create_gate(
            "deploy-1",
            service_name="api-svc",
            gate_type=GateType.SECURITY_SCAN,
            approval_level=ApprovalLevel.SECURITY_TEAM,
            reason="Security review needed",
            pre_checks=["vuln-scan", "dep-check"],
        )
        assert gate.gate_type == GateType.SECURITY_SCAN
        assert gate.approval_level == ApprovalLevel.SECURITY_TEAM
        assert len(gate.pre_checks) == 2

    def test_expires_at_set(self):
        eng = _engine(gate_expiry_hours=48)
        gate = eng.create_gate("deploy-1")
        assert gate.expires_at > gate.created_at

    def test_eviction_at_max_gates(self):
        eng = _engine(max_gates=3)
        ids = []
        for i in range(4):
            gate = eng.create_gate(f"deploy-{i}")
            ids.append(gate.id)
        gates = eng.list_gates(limit=100)
        assert len(gates) == 3
        found = {g.id for g in gates}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_gate
# -------------------------------------------------------------------


class TestGetGate:
    def test_get_existing(self):
        eng = _engine()
        gate = eng.create_gate("deploy-1")
        found = eng.get_gate(gate.id)
        assert found is not None
        assert found.id == gate.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_gate("nonexistent") is None


# -------------------------------------------------------------------
# list_gates
# -------------------------------------------------------------------


class TestListGates:
    def test_list_all(self):
        eng = _engine()
        eng.create_gate("deploy-1")
        eng.create_gate("deploy-2")
        eng.create_gate("deploy-3")
        assert len(eng.list_gates()) == 3

    def test_filter_by_deployment(self):
        eng = _engine()
        eng.create_gate("deploy-a")
        eng.create_gate("deploy-b")
        eng.create_gate("deploy-a")
        results = eng.list_gates(deployment_id="deploy-a")
        assert len(results) == 2

    def test_filter_by_status(self):
        eng = _engine()
        g1 = eng.create_gate("deploy-1")
        eng.create_gate("deploy-2")
        eng.approve_gate(g1.id, "admin")
        pending = eng.list_gates(status=GateStatus.PENDING)
        assert len(pending) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.create_gate(f"deploy-{i}")
        results = eng.list_gates(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# approve_gate
# -------------------------------------------------------------------


class TestApproveGate:
    def test_approve_pending(self):
        eng = _engine()
        gate = eng.create_gate("deploy-1")
        result = eng.approve_gate(gate.id, "admin", "LGTM")
        assert result is not None
        assert result.status == GateStatus.APPROVED
        assert result.approver == "admin"

    def test_approve_nonexistent(self):
        eng = _engine()
        assert eng.approve_gate("nope", "admin") is None

    def test_approve_already_approved(self):
        eng = _engine()
        gate = eng.create_gate("deploy-1")
        eng.approve_gate(gate.id, "admin")
        result = eng.approve_gate(gate.id, "other")
        assert result is not None
        assert result.approver == "admin"


# -------------------------------------------------------------------
# reject_gate
# -------------------------------------------------------------------


class TestRejectGate:
    def test_reject_pending(self):
        eng = _engine()
        gate = eng.create_gate("deploy-1")
        result = eng.reject_gate(
            gate.id,
            "admin",
            "Too risky",
        )
        assert result is not None
        assert result.status == GateStatus.REJECTED

    def test_reject_nonexistent(self):
        eng = _engine()
        assert eng.reject_gate("nope", "admin") is None

    def test_reject_already_rejected(self):
        eng = _engine()
        gate = eng.create_gate("deploy-1")
        eng.reject_gate(gate.id, "admin", "No")
        result = eng.reject_gate(gate.id, "other", "Also no")
        assert result is not None
        assert result.status == GateStatus.REJECTED


# -------------------------------------------------------------------
# evaluate_auto_approval
# -------------------------------------------------------------------


class TestEvaluateAutoApproval:
    def test_auto_approve_automated_check(self):
        eng = _engine()
        gate = eng.create_gate(
            "deploy-1",
            gate_type=GateType.AUTOMATED_CHECK,
            pre_checks=["lint", "test"],
        )
        result = eng.evaluate_auto_approval(gate.id)
        assert result is not None
        assert result.status == GateStatus.AUTO_APPROVED

    def test_no_auto_for_manual_review(self):
        eng = _engine()
        gate = eng.create_gate(
            "deploy-1",
            gate_type=GateType.MANUAL_REVIEW,
        )
        result = eng.evaluate_auto_approval(gate.id)
        assert result is not None
        assert result.status == GateStatus.PENDING

    def test_auto_nonexistent(self):
        eng = _engine()
        assert eng.evaluate_auto_approval("nope") is None


# -------------------------------------------------------------------
# check_gate_expiry
# -------------------------------------------------------------------


class TestCheckGateExpiry:
    def test_expires_old_gate(self):
        eng = _engine(gate_expiry_hours=0)
        import time

        gate = eng.create_gate("deploy-1")
        gate.expires_at = time.time() - 1
        expired = eng.check_gate_expiry()
        assert len(expired) == 1
        assert expired[0].status == GateStatus.EXPIRED

    def test_no_expiry_for_recent(self):
        eng = _engine(gate_expiry_hours=24)
        eng.create_gate("deploy-1")
        expired = eng.check_gate_expiry()
        assert len(expired) == 0


# -------------------------------------------------------------------
# calculate_approval_velocity
# -------------------------------------------------------------------


class TestCalculateApprovalVelocity:
    def test_basic_velocity(self):
        eng = _engine()
        gate = eng.create_gate("deploy-1")
        eng.approve_gate(gate.id, "admin")
        velocity = eng.calculate_approval_velocity()
        assert velocity["total_decisions"] == 1
        assert velocity["avg_wait_hours"] >= 0.0

    def test_empty_velocity(self):
        eng = _engine()
        velocity = eng.calculate_approval_velocity()
        assert velocity["total_decisions"] == 0
        assert velocity["avg_wait_hours"] == 0.0


# -------------------------------------------------------------------
# generate_gate_report
# -------------------------------------------------------------------


class TestGenerateGateReport:
    def test_basic_report(self):
        eng = _engine()
        g1 = eng.create_gate("deploy-1")
        eng.create_gate("deploy-2")
        eng.approve_gate(g1.id, "admin")
        report = eng.generate_gate_report()
        assert report.total_gates == 2
        assert report.total_decisions == 1
        assert report.approval_rate_pct > 0
        assert isinstance(report.by_status, dict)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_gate_report()
        assert report.total_gates == 0
        assert report.approval_rate_pct == 0.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.create_gate("deploy-1")
        eng.create_gate("deploy-2")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_gates()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_gates"] == 0
        assert stats["total_decisions"] == 0
        assert stats["gate_expiry_hours"] == 24
        assert stats["status_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        g1 = eng.create_gate("deploy-1")
        eng.create_gate("deploy-2")
        eng.approve_gate(g1.id, "admin")
        stats = eng.get_stats()
        assert stats["total_gates"] == 2
        assert stats["total_decisions"] == 1
        assert len(stats["status_distribution"]) > 0
