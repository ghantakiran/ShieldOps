"""Tests for ComplianceAsCodeEngine."""

from __future__ import annotations

from shieldops.compliance.compliance_as_code_engine import (
    ComplianceAsCodeEngine,
    ComplianceReport,
    ComplianceStatus,
    EvidenceRecord,
    FrameworkType,
    PolicyLanguage,
    PolicyRecord,
    RemediationStatus,
)


def _engine(**kw) -> ComplianceAsCodeEngine:
    return ComplianceAsCodeEngine(**kw)


# --- Enum tests ---


class TestEnums:
    def test_language_rego(self):
        assert PolicyLanguage.REGO == "rego"

    def test_language_yaml(self):
        assert PolicyLanguage.YAML == "yaml"

    def test_language_json(self):
        assert PolicyLanguage.JSON == "json"

    def test_language_python(self):
        assert PolicyLanguage.PYTHON == "python"

    def test_status_compliant(self):
        assert ComplianceStatus.COMPLIANT == "compliant"

    def test_status_non_compliant(self):
        assert ComplianceStatus.NON_COMPLIANT == "non_compliant"

    def test_status_partial(self):
        assert ComplianceStatus.PARTIALLY_COMPLIANT == "partially_compliant"

    def test_remediation_pending(self):
        assert RemediationStatus.PENDING == "pending"

    def test_framework_soc2(self):
        assert FrameworkType.SOC2 == "soc2"

    def test_framework_hipaa(self):
        assert FrameworkType.HIPAA == "hipaa"

    def test_framework_pci(self):
        assert FrameworkType.PCI_DSS == "pci_dss"

    def test_framework_gdpr(self):
        assert FrameworkType.GDPR == "gdpr"


# --- Model tests ---


class TestModels:
    def test_policy_defaults(self):
        p = PolicyRecord()
        assert p.id
        assert p.name == ""
        assert p.framework == FrameworkType.SOC2
        assert p.status == ComplianceStatus.NOT_ASSESSED

    def test_evidence_defaults(self):
        e = EvidenceRecord()
        assert e.id
        assert e.valid is False

    def test_report_defaults(self):
        r = ComplianceReport()
        assert r.total_policies == 0
        assert r.by_framework == {}


# --- parse_policy ---


class TestParsePolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.parse_policy(
            name="encryption",
            framework=FrameworkType.PCI_DSS,
            language=PolicyLanguage.REGO,
            score=75.0,
            control_id="PCI-3.4",
            service="payments",
            team="sec",
        )
        assert p.name == "encryption"
        assert p.framework == FrameworkType.PCI_DSS
        assert p.control_id == "PCI-3.4"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.parse_policy(name=f"p-{i}")
        assert len(eng._policies) == 3


# --- evaluate_compliance ---


class TestEvaluateCompliance:
    def test_compliant(self):
        eng = _engine()
        p = eng.parse_policy(name="test")
        result = eng.evaluate_compliance(p.id, score=95.0)
        assert result["status"] == "compliant"

    def test_partial(self):
        eng = _engine()
        p = eng.parse_policy(name="test")
        result = eng.evaluate_compliance(p.id, score=60.0)
        assert result["status"] == "partially_compliant"

    def test_non_compliant(self):
        eng = _engine()
        p = eng.parse_policy(name="test")
        result = eng.evaluate_compliance(p.id, score=30.0)
        assert result["status"] == "non_compliant"

    def test_not_found(self):
        eng = _engine()
        result = eng.evaluate_compliance("unknown", score=50.0)
        assert result["status"] == "not_found"


# --- generate_evidence ---


class TestGenerateEvidence:
    def test_basic(self):
        eng = _engine()
        p = eng.parse_policy(name="test")
        ev = eng.generate_evidence(p.id, evidence_type="log", content_hash="abc123")
        assert ev.policy_id == p.id
        assert ev.content_hash == "abc123"

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.generate_evidence(f"p-{i}")
        assert len(eng._evidence) == 2


# --- remediate_violations ---


class TestRemediate:
    def test_remediate_non_compliant(self):
        eng = _engine()
        p = eng.parse_policy(name="test")
        eng.evaluate_compliance(p.id, score=20.0)
        result = eng.remediate_violations(p.id)
        assert result["remediation"] == "completed"

    def test_skip_compliant(self):
        eng = _engine()
        p = eng.parse_policy(name="test")
        eng.evaluate_compliance(p.id, score=95.0)
        result = eng.remediate_violations(p.id)
        assert result["remediation"] == "skipped"

    def test_not_found(self):
        eng = _engine()
        result = eng.remediate_violations("unknown")
        assert result["remediation"] == "failed"


# --- get_compliance_dashboard ---


class TestDashboard:
    def test_with_data(self):
        eng = _engine()
        p = eng.parse_policy(name="test")
        eng.evaluate_compliance(p.id, score=95.0)
        result = eng.get_compliance_dashboard()
        assert result["total"] == 1
        assert result["compliance_rate"] == 100.0

    def test_empty(self):
        eng = _engine()
        result = eng.get_compliance_dashboard()
        assert result["total"] == 0


# --- list_policies ---


class TestListPolicies:
    def test_all(self):
        eng = _engine()
        eng.parse_policy(name="a")
        eng.parse_policy(name="b")
        assert len(eng.list_policies()) == 2

    def test_filter_framework(self):
        eng = _engine()
        eng.parse_policy(name="a", framework=FrameworkType.SOC2)
        eng.parse_policy(name="b", framework=FrameworkType.HIPAA)
        assert len(eng.list_policies(framework=FrameworkType.SOC2)) == 1

    def test_filter_team(self):
        eng = _engine()
        eng.parse_policy(name="a", team="sec")
        eng.parse_policy(name="b", team="ops")
        assert len(eng.list_policies(team="sec")) == 1


# --- generate_report ---


class TestReport:
    def test_populated(self):
        eng = _engine(score_threshold=80.0)
        eng.parse_policy(name="test", score=40.0)
        report = eng.generate_report()
        assert isinstance(report, ComplianceReport)
        assert report.total_policies == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert len(report.recommendations) > 0


# --- stats / clear ---


class TestStatsAndClear:
    def test_stats(self):
        eng = _engine()
        eng.parse_policy(name="a", service="s", team="t")
        stats = eng.get_stats()
        assert stats["total_policies"] == 1

    def test_clear(self):
        eng = _engine()
        eng.parse_policy(name="test")
        eng.generate_evidence("p1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._policies) == 0
