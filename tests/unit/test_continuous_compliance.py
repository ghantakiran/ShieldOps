"""Tests for Continuous Compliance Validator (Phase 17 — F9)."""

from __future__ import annotations

import time

import pytest

from shieldops.compliance.continuous_validator import (
    ComplianceControl,
    ComplianceFramework,
    ComplianceSnapshot,
    ContinuousComplianceValidator,
    ValidationRecord,
    ValidationResult,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _validator(**kw) -> ContinuousComplianceValidator:
    return ContinuousComplianceValidator(**kw)


def _register(
    v: ContinuousComplianceValidator,
    framework: ComplianceFramework = ComplianceFramework.CIS,
    control_id: str = "CIS-1.1",
    title: str = "Ensure MFA",
    **kw,
) -> ComplianceControl:
    return v.register_control(
        framework=framework,
        control_id=control_id,
        title=title,
        **kw,
    )


# -------------------------------------------------------------------
# Enum values
# -------------------------------------------------------------------


class TestEnums:
    def test_framework_cis(self):
        assert ComplianceFramework.CIS == "cis"

    def test_framework_nist_csf(self):
        assert ComplianceFramework.NIST_CSF == "nist_csf"

    def test_framework_soc2(self):
        assert ComplianceFramework.SOC2 == "soc2"

    def test_framework_pci_dss(self):
        assert ComplianceFramework.PCI_DSS == "pci_dss"

    def test_framework_hipaa(self):
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_framework_iso_27001(self):
        assert ComplianceFramework.ISO_27001 == "iso_27001"

    def test_result_pass(self):
        assert ValidationResult.PASS == "pass"  # noqa: S105

    def test_result_fail(self):
        assert ValidationResult.FAIL == "fail"

    def test_result_warning(self):
        assert ValidationResult.WARNING == "warning"

    def test_result_not_applicable(self):
        assert ValidationResult.NOT_APPLICABLE == "not_applicable"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_compliance_control_defaults(self):
        c = ComplianceControl(
            framework=ComplianceFramework.CIS,
            control_id="CIS-1.1",
            title="MFA",
        )
        assert c.id
        assert c.framework == ComplianceFramework.CIS
        assert c.control_id == "CIS-1.1"
        assert c.title == "MFA"
        assert c.description == ""
        assert c.severity == "medium"
        assert c.auto_remediate is False
        assert c.created_at > 0

    def test_compliance_control_full(self):
        c = ComplianceControl(
            framework=ComplianceFramework.HIPAA,
            control_id="HIPAA-164.312",
            title="Encryption",
            description="Encrypt PHI at rest",
            severity="critical",
            auto_remediate=True,
        )
        assert c.severity == "critical"
        assert c.auto_remediate is True
        assert c.description == "Encrypt PHI at rest"

    def test_validation_record_defaults(self):
        r = ValidationRecord(
            control_id="ctrl-1",
            resource_id="res-1",
            result=ValidationResult.PASS,
        )
        assert r.id
        assert r.evidence == ""
        assert r.remediation_action == ""
        assert r.validated_at > 0

    def test_validation_record_full(self):
        r = ValidationRecord(
            control_id="ctrl-1",
            resource_id="res-1",
            result=ValidationResult.FAIL,
            evidence="Port 22 open",
            remediation_action="Close port 22",
        )
        assert r.evidence == "Port 22 open"
        assert r.remediation_action == "Close port 22"

    def test_snapshot_defaults(self):
        s = ComplianceSnapshot(framework=ComplianceFramework.SOC2)
        assert s.id
        assert s.total_controls == 0
        assert s.passed == 0
        assert s.failed == 0
        assert s.warnings == 0
        assert s.compliance_pct == 0.0
        assert s.snapshot_at > 0


# -------------------------------------------------------------------
# register_control
# -------------------------------------------------------------------


class TestRegisterControl:
    def test_basic_registration(self):
        v = _validator()
        ctrl = _register(v)
        assert ctrl.framework == ComplianceFramework.CIS
        assert ctrl.control_id == "CIS-1.1"
        assert ctrl.title == "Ensure MFA"

    def test_registration_with_all_fields(self):
        v = _validator()
        ctrl = v.register_control(
            framework=ComplianceFramework.PCI_DSS,
            control_id="PCI-3.4",
            title="Encrypt cardholder data",
            description="Use AES-256",
            severity="critical",
            auto_remediate=True,
        )
        assert ctrl.severity == "critical"
        assert ctrl.auto_remediate is True

    def test_registration_assigns_unique_ids(self):
        v = _validator()
        c1 = _register(v, control_id="CIS-1.1")
        c2 = _register(v, control_id="CIS-1.2")
        assert c1.id != c2.id

    def test_max_controls_limit(self):
        v = _validator(max_controls=2)
        _register(v, control_id="CIS-1.1")
        _register(v, control_id="CIS-1.2")
        with pytest.raises(ValueError, match="Maximum controls limit"):
            _register(v, control_id="CIS-1.3")


# -------------------------------------------------------------------
# validate_control
# -------------------------------------------------------------------


class TestValidateControl:
    def test_validate_pass(self):
        v = _validator()
        ctrl = _register(v)
        rec = v.validate_control(ctrl.id, "server-01", ValidationResult.PASS)
        assert rec.control_id == ctrl.id
        assert rec.resource_id == "server-01"
        assert rec.result == ValidationResult.PASS

    def test_validate_fail_with_evidence(self):
        v = _validator()
        ctrl = _register(v)
        rec = v.validate_control(
            ctrl.id,
            "server-02",
            ValidationResult.FAIL,
            evidence="SSH root login enabled",
            remediation_action="Disable root SSH",
        )
        assert rec.result == ValidationResult.FAIL
        assert rec.evidence == "SSH root login enabled"

    def test_validate_unknown_control_raises(self):
        v = _validator()
        with pytest.raises(ValueError, match="Control not found"):
            v.validate_control("no-such-id", "res-1", ValidationResult.PASS)

    def test_max_records_limit(self):
        v = _validator(max_records=2)
        ctrl = _register(v)
        v.validate_control(ctrl.id, "r1", ValidationResult.PASS)
        v.validate_control(ctrl.id, "r2", ValidationResult.FAIL)
        with pytest.raises(ValueError, match="Maximum records limit"):
            v.validate_control(ctrl.id, "r3", ValidationResult.PASS)

    def test_multiple_records_same_control(self):
        v = _validator()
        ctrl = _register(v)
        v.validate_control(ctrl.id, "r1", ValidationResult.FAIL)
        v.validate_control(ctrl.id, "r1", ValidationResult.PASS)
        recs = v.list_records(control_id=ctrl.id)
        assert len(recs) == 2


# -------------------------------------------------------------------
# get_snapshot
# -------------------------------------------------------------------


class TestGetSnapshot:
    def test_snapshot_no_controls(self):
        v = _validator()
        snap = v.get_snapshot(ComplianceFramework.CIS)
        assert snap.total_controls == 0
        assert snap.compliance_pct == 0.0

    def test_snapshot_all_pass(self):
        v = _validator()
        c1 = _register(v, control_id="CIS-1")
        c2 = _register(v, control_id="CIS-2")
        v.validate_control(c1.id, "r1", ValidationResult.PASS)
        v.validate_control(c2.id, "r1", ValidationResult.PASS)
        snap = v.get_snapshot(ComplianceFramework.CIS)
        assert snap.total_controls == 2
        assert snap.passed == 2
        assert snap.failed == 0
        assert snap.compliance_pct == 100.0

    def test_snapshot_mixed_results(self):
        v = _validator()
        c1 = _register(v, control_id="CIS-1")
        c2 = _register(v, control_id="CIS-2")
        v.validate_control(c1.id, "r1", ValidationResult.PASS)
        v.validate_control(c2.id, "r1", ValidationResult.FAIL)
        snap = v.get_snapshot(ComplianceFramework.CIS)
        assert snap.passed == 1
        assert snap.failed == 1
        assert snap.compliance_pct == 50.0

    def test_snapshot_latest_record_wins(self):
        v = _validator()
        ctrl = _register(v)
        v.validate_control(ctrl.id, "r1", ValidationResult.FAIL)
        time.sleep(0.01)
        v.validate_control(ctrl.id, "r1", ValidationResult.PASS)
        snap = v.get_snapshot(ComplianceFramework.CIS)
        assert snap.passed == 1
        assert snap.failed == 0

    def test_snapshot_filters_by_framework(self):
        v = _validator()
        cis = _register(v, framework=ComplianceFramework.CIS)
        soc = _register(
            v,
            framework=ComplianceFramework.SOC2,
            control_id="SOC2-CC6",
            title="Logical access",
        )
        v.validate_control(cis.id, "r1", ValidationResult.PASS)
        v.validate_control(soc.id, "r1", ValidationResult.FAIL)
        snap = v.get_snapshot(ComplianceFramework.CIS)
        assert snap.total_controls == 1
        assert snap.passed == 1
        assert snap.failed == 0

    def test_snapshot_warnings_counted(self):
        v = _validator()
        ctrl = _register(v)
        v.validate_control(ctrl.id, "r1", ValidationResult.WARNING)
        snap = v.get_snapshot(ComplianceFramework.CIS)
        assert snap.warnings == 1

    def test_snapshot_stored_internally(self):
        v = _validator()
        _register(v)
        v.get_snapshot(ComplianceFramework.CIS)
        v.get_snapshot(ComplianceFramework.CIS)
        stats = v.get_stats()
        assert stats["total_snapshots"] == 2


# -------------------------------------------------------------------
# list_controls / delete_control
# -------------------------------------------------------------------


class TestListAndDeleteControls:
    def test_list_all(self):
        v = _validator()
        _register(v, control_id="CIS-1")
        _register(v, control_id="CIS-2")
        assert len(v.list_controls()) == 2

    def test_list_filter_by_framework(self):
        v = _validator()
        _register(v, framework=ComplianceFramework.CIS)
        _register(
            v,
            framework=ComplianceFramework.HIPAA,
            control_id="HIPAA-1",
            title="PHI",
        )
        cis_only = v.list_controls(framework=ComplianceFramework.CIS)
        assert len(cis_only) == 1

    def test_list_empty(self):
        v = _validator()
        assert v.list_controls() == []

    def test_delete_existing(self):
        v = _validator()
        ctrl = _register(v)
        assert v.delete_control(ctrl.id) is True
        assert len(v.list_controls()) == 0

    def test_delete_nonexistent(self):
        v = _validator()
        assert v.delete_control("nope") is False


# -------------------------------------------------------------------
# list_records
# -------------------------------------------------------------------


class TestListRecords:
    def test_list_all_records(self):
        v = _validator()
        ctrl = _register(v)
        v.validate_control(ctrl.id, "r1", ValidationResult.PASS)
        v.validate_control(ctrl.id, "r2", ValidationResult.FAIL)
        assert len(v.list_records()) == 2

    def test_filter_by_control_id(self):
        v = _validator()
        c1 = _register(v, control_id="CIS-1")
        c2 = _register(v, control_id="CIS-2")
        v.validate_control(c1.id, "r1", ValidationResult.PASS)
        v.validate_control(c2.id, "r1", ValidationResult.FAIL)
        recs = v.list_records(control_id=c1.id)
        assert len(recs) == 1
        assert recs[0].result == ValidationResult.PASS

    def test_filter_by_result(self):
        v = _validator()
        ctrl = _register(v)
        v.validate_control(ctrl.id, "r1", ValidationResult.PASS)
        v.validate_control(ctrl.id, "r2", ValidationResult.FAIL)
        fails = v.list_records(result=ValidationResult.FAIL)
        assert len(fails) == 1

    def test_limit_applied(self):
        v = _validator()
        ctrl = _register(v)
        for i in range(5):
            v.validate_control(ctrl.id, f"r{i}", ValidationResult.PASS)
        assert len(v.list_records(limit=3)) == 3

    def test_limit_returns_tail(self):
        v = _validator()
        ctrl = _register(v)
        for i in range(5):
            v.validate_control(ctrl.id, f"r{i}", ValidationResult.PASS)
        recs = v.list_records(limit=2)
        assert recs[0].resource_id == "r3"
        assert recs[1].resource_id == "r4"


# -------------------------------------------------------------------
# get_failing_controls
# -------------------------------------------------------------------


class TestGetFailingControls:
    def test_no_failures(self):
        v = _validator()
        ctrl = _register(v)
        v.validate_control(ctrl.id, "r1", ValidationResult.PASS)
        assert v.get_failing_controls() == []

    def test_returns_failing(self):
        v = _validator()
        ctrl = _register(v)
        v.validate_control(ctrl.id, "r1", ValidationResult.FAIL)
        fails = v.get_failing_controls()
        assert len(fails) == 1
        assert fails[0].result == ValidationResult.FAIL

    def test_filter_by_framework(self):
        v = _validator()
        cis = _register(v, framework=ComplianceFramework.CIS)
        soc = _register(
            v,
            framework=ComplianceFramework.SOC2,
            control_id="SOC2-1",
            title="SOC",
        )
        v.validate_control(cis.id, "r1", ValidationResult.FAIL)
        v.validate_control(soc.id, "r1", ValidationResult.FAIL)
        cis_fails = v.get_failing_controls(framework=ComplianceFramework.CIS)
        assert len(cis_fails) == 1

    def test_latest_record_used(self):
        v = _validator()
        ctrl = _register(v)
        v.validate_control(ctrl.id, "r1", ValidationResult.FAIL)
        time.sleep(0.01)
        v.validate_control(ctrl.id, "r1", ValidationResult.PASS)
        assert v.get_failing_controls() == []


# -------------------------------------------------------------------
# get_remediation_candidates
# -------------------------------------------------------------------


class TestGetRemediationCandidates:
    def test_no_auto_remediate_controls(self):
        v = _validator()
        ctrl = _register(v, auto_remediate=False)
        v.validate_control(ctrl.id, "r1", ValidationResult.FAIL)
        assert v.get_remediation_candidates() == []

    def test_auto_remediate_with_fail(self):
        v = _validator()
        ctrl = _register(v, auto_remediate=True)
        v.validate_control(ctrl.id, "r1", ValidationResult.FAIL)
        cands = v.get_remediation_candidates()
        assert len(cands) == 1
        assert cands[0].id == ctrl.id

    def test_auto_remediate_with_pass_excluded(self):
        v = _validator()
        ctrl = _register(v, auto_remediate=True)
        v.validate_control(ctrl.id, "r1", ValidationResult.PASS)
        assert v.get_remediation_candidates() == []

    def test_latest_record_determines_candidacy(self):
        v = _validator()
        ctrl = _register(v, auto_remediate=True)
        v.validate_control(ctrl.id, "r1", ValidationResult.FAIL)
        time.sleep(0.01)
        v.validate_control(ctrl.id, "r1", ValidationResult.PASS)
        assert v.get_remediation_candidates() == []


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        v = _validator()
        s = v.get_stats()
        assert s["total_controls"] == 0
        assert s["total_records"] == 0
        assert s["total_snapshots"] == 0
        assert s["total_pass"] == 0
        assert s["total_fail"] == 0
        assert s["frameworks"] == []

    def test_populated_stats(self):
        v = _validator()
        ctrl = _register(v)
        v.validate_control(ctrl.id, "r1", ValidationResult.PASS)
        v.validate_control(ctrl.id, "r2", ValidationResult.FAIL)
        v.get_snapshot(ComplianceFramework.CIS)
        s = v.get_stats()
        assert s["total_controls"] == 1
        assert s["total_records"] == 2
        assert s["total_snapshots"] == 1
        assert s["total_pass"] == 1
        assert s["total_fail"] == 1
        assert ComplianceFramework.CIS in s["frameworks"]

    def test_multiple_frameworks_in_stats(self):
        v = _validator()
        _register(v, framework=ComplianceFramework.CIS)
        _register(
            v,
            framework=ComplianceFramework.HIPAA,
            control_id="H-1",
            title="PHI",
        )
        s = v.get_stats()
        assert len(s["frameworks"]) == 2
