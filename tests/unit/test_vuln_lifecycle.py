"""Tests for shieldops.security.vuln_lifecycle — VulnerabilityLifecycleManager."""

from __future__ import annotations

from shieldops.security.vuln_lifecycle import (
    ExploitPrediction,
    ExploitStatus,
    PatchAttempt,
    PatchOutcome,
    VulnerabilityLifecycleManager,
    VulnerabilityRecord,
    VulnPhase,
)


def _engine(**kw) -> VulnerabilityLifecycleManager:
    return VulnerabilityLifecycleManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_phase_disclosed(self):
        assert VulnPhase.DISCLOSED == "disclosed"

    def test_phase_assessed(self):
        assert VulnPhase.ASSESSED == "assessed"

    def test_phase_patch_available(self):
        assert VulnPhase.PATCH_AVAILABLE == "patch_available"

    def test_phase_patch_testing(self):
        assert VulnPhase.PATCH_TESTING == "patch_testing"

    def test_phase_patch_deployed(self):
        assert VulnPhase.PATCH_DEPLOYED == "patch_deployed"

    def test_phase_mitigated(self):
        assert VulnPhase.MITIGATED == "mitigated"

    def test_phase_accepted_risk(self):
        assert VulnPhase.ACCEPTED_RISK == "accepted_risk"

    def test_exploit_none(self):
        assert ExploitStatus.NO_KNOWN_EXPLOIT == "no_known_exploit"

    def test_exploit_poc(self):
        assert ExploitStatus.POC_AVAILABLE == "poc_available"

    def test_exploit_active(self):
        assert ExploitStatus.ACTIVE_EXPLOITATION == "active_exploitation"

    def test_exploit_weaponized(self):
        assert ExploitStatus.WEAPONIZED == "weaponized"

    def test_patch_success(self):
        assert PatchOutcome.SUCCESS == "success"

    def test_patch_regression(self):
        assert PatchOutcome.REGRESSION == "regression"

    def test_patch_rollback(self):
        assert PatchOutcome.ROLLBACK == "rollback"

    def test_patch_pending(self):
        assert PatchOutcome.PENDING == "pending"

    def test_patch_skipped(self):
        assert PatchOutcome.SKIPPED == "skipped"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_vuln_record_defaults(self):
        v = VulnerabilityRecord()
        assert v.id
        assert v.phase == VulnPhase.DISCLOSED
        assert v.exploit_status == ExploitStatus.NO_KNOWN_EXPLOIT

    def test_patch_attempt_defaults(self):
        p = PatchAttempt()
        assert p.outcome == PatchOutcome.PENDING

    def test_exploit_prediction_defaults(self):
        e = ExploitPrediction()
        assert e.predicted_risk == 0.0


# ---------------------------------------------------------------------------
# register_vulnerability
# ---------------------------------------------------------------------------


class TestRegisterVulnerability:
    def test_basic_register(self):
        eng = _engine()
        v = eng.register_vulnerability(cve_id="CVE-2024-1234", title="Test")
        assert v.cve_id == "CVE-2024-1234"
        assert v.phase == VulnPhase.DISCLOSED

    def test_unique_ids(self):
        eng = _engine()
        v1 = eng.register_vulnerability(cve_id="CVE-1")
        v2 = eng.register_vulnerability(cve_id="CVE-2")
        assert v1.id != v2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.register_vulnerability(cve_id=f"CVE-{i}")
        assert len(eng._vulns) == 3

    def test_with_services(self):
        eng = _engine()
        v = eng.register_vulnerability(affected_services=["svc-a", "svc-b"])
        assert len(v.affected_services) == 2


# ---------------------------------------------------------------------------
# get / list vulnerabilities
# ---------------------------------------------------------------------------


class TestGetVulnerability:
    def test_found(self):
        eng = _engine()
        v = eng.register_vulnerability(cve_id="CVE-1")
        assert eng.get_vulnerability(v.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_vulnerability("nonexistent") is None


class TestListVulnerabilities:
    def test_list_all(self):
        eng = _engine()
        eng.register_vulnerability(cve_id="CVE-1")
        eng.register_vulnerability(cve_id="CVE-2")
        assert len(eng.list_vulnerabilities()) == 2

    def test_filter_by_phase(self):
        eng = _engine()
        eng.register_vulnerability(cve_id="CVE-1")
        results = eng.list_vulnerabilities(phase=VulnPhase.DISCLOSED)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.register_vulnerability(severity="critical")
        eng.register_vulnerability(severity="low")
        results = eng.list_vulnerabilities(severity="critical")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# advance_phase / record_patch_attempt
# ---------------------------------------------------------------------------


class TestAdvancePhase:
    def test_advance(self):
        eng = _engine()
        v = eng.register_vulnerability()
        assert eng.advance_phase(v.id, VulnPhase.ASSESSED) is True
        assert v.phase == VulnPhase.ASSESSED

    def test_advance_not_found(self):
        eng = _engine()
        assert eng.advance_phase("bad", VulnPhase.ASSESSED) is False


class TestRecordPatchAttempt:
    def test_record_patch(self):
        eng = _engine()
        v = eng.register_vulnerability()
        attempt = eng.record_patch_attempt(v.id, patch_version="1.2.3")
        assert attempt is not None
        assert attempt.patch_version == "1.2.3"

    def test_success_advances_phase(self):
        eng = _engine()
        v = eng.register_vulnerability()
        eng.record_patch_attempt(v.id, outcome=PatchOutcome.SUCCESS)
        assert v.phase == VulnPhase.PATCH_DEPLOYED

    def test_patch_invalid_vuln(self):
        eng = _engine()
        assert eng.record_patch_attempt("bad_id") is None


# ---------------------------------------------------------------------------
# predict_exploit_risk
# ---------------------------------------------------------------------------


class TestPredictExploitRisk:
    def test_basic_prediction(self):
        eng = _engine()
        v = eng.register_vulnerability(cvss_score=9.0)
        pred = eng.predict_exploit_risk(v.id)
        assert pred is not None
        assert pred.predicted_risk > 0.0

    def test_prediction_not_found(self):
        eng = _engine()
        assert eng.predict_exploit_risk("bad") is None

    def test_high_cvss_higher_risk(self):
        eng = _engine()
        v_high = eng.register_vulnerability(cvss_score=10.0)
        v_low = eng.register_vulnerability(cvss_score=1.0)
        p_high = eng.predict_exploit_risk(v_high.id)
        p_low = eng.predict_exploit_risk(v_low.id)
        assert p_high is not None
        assert p_low is not None
        assert p_high.predicted_risk > p_low.predicted_risk


# ---------------------------------------------------------------------------
# overdue / risk summary / patch success / stats
# ---------------------------------------------------------------------------


class TestOverduePatches:
    def test_no_overdue(self):
        eng = _engine(patch_sla_days=365)
        eng.register_vulnerability()
        assert len(eng.get_overdue_patches()) == 0


class TestRiskSummary:
    def test_summary(self):
        eng = _engine()
        eng.register_vulnerability(severity="critical")
        eng.register_vulnerability(severity="low")
        summary = eng.get_risk_summary()
        assert summary["total_vulnerabilities"] == 2
        assert summary["open_vulnerabilities"] == 2


class TestPatchSuccessRate:
    def test_empty(self):
        eng = _engine()
        rate = eng.get_patch_success_rate()
        assert rate["total_attempts"] == 0

    def test_with_patches(self):
        eng = _engine()
        v = eng.register_vulnerability()
        eng.record_patch_attempt(v.id, outcome=PatchOutcome.SUCCESS)
        eng.record_patch_attempt(v.id, outcome=PatchOutcome.ROLLBACK)
        rate = eng.get_patch_success_rate()
        assert rate["total_attempts"] == 2
        assert rate["success_rate"] == 50.0


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_vulnerabilities"] == 0

    def test_populated_stats(self):
        eng = _engine()
        v = eng.register_vulnerability()
        eng.record_patch_attempt(v.id, outcome=PatchOutcome.SUCCESS)
        stats = eng.get_stats()
        assert stats["total_vulnerabilities"] == 1
        assert stats["total_patch_attempts"] == 1
