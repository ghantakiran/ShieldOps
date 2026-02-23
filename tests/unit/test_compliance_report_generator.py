"""Tests for compliance report generator."""

from __future__ import annotations

import pytest

from shieldops.compliance.report_generator import (
    _FRAMEWORK_CONTROLS,
    ComplianceControl,
    ComplianceFramework,
    ComplianceReport,
    ComplianceReportGenerator,
    ControlEvidence,
    ControlStatus,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _gen() -> ComplianceReportGenerator:
    return ComplianceReportGenerator()


# ── Enum tests ───────────────────────────────────────────────────────


class TestComplianceFrameworkEnum:
    def test_soc2_value(self) -> None:
        assert ComplianceFramework.SOC2 == "soc2"

    def test_pci_dss_value(self) -> None:
        assert ComplianceFramework.PCI_DSS == "pci_dss"

    def test_hipaa_value(self) -> None:
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_iso27001_value(self) -> None:
        assert ComplianceFramework.ISO27001 == "iso27001"

    def test_nist_value(self) -> None:
        assert ComplianceFramework.NIST == "nist"

    def test_member_count(self) -> None:
        assert len(ComplianceFramework) == 5


class TestControlStatusEnum:
    def test_passing(self) -> None:
        assert ControlStatus.PASSING == "passing"

    def test_failing(self) -> None:
        assert ControlStatus.FAILING == "failing"

    def test_not_assessed(self) -> None:
        assert ControlStatus.NOT_ASSESSED == "not_assessed"

    def test_not_applicable(self) -> None:
        assert ControlStatus.NOT_APPLICABLE == "not_applicable"

    def test_member_count(self) -> None:
        assert len(ControlStatus) == 4


# ── Model tests ──────────────────────────────────────────────────────


class TestControlEvidenceModel:
    def test_defaults(self) -> None:
        ev = ControlEvidence(control_id="CC1.1", description="Audit log present")
        assert len(ev.id) == 12
        assert ev.control_id == "CC1.1"
        assert ev.source == ""
        assert ev.collected_at > 0
        assert ev.metadata == {}


class TestComplianceControlModel:
    def test_defaults(self) -> None:
        ctrl = ComplianceControl(
            id="CC1.1",
            name="Control Environment",
            framework=ComplianceFramework.SOC2,
        )
        assert ctrl.status == ControlStatus.NOT_ASSESSED
        assert ctrl.evidence == []
        assert ctrl.assessed_at is None
        assert ctrl.notes == ""


class TestComplianceReportModel:
    def test_defaults(self) -> None:
        r = ComplianceReport(framework=ComplianceFramework.SOC2)
        assert len(r.id) == 12
        assert r.title == ""
        assert r.controls == []
        assert r.overall_score == 0.0
        assert r.passing_count == 0
        assert r.failing_count == 0
        assert r.not_assessed_count == 0
        assert r.generated_at > 0
        assert r.metadata == {}


# ── Generator creation ───────────────────────────────────────────────


class TestGeneratorCreation:
    def test_default_max_reports(self) -> None:
        g = _gen()
        assert g._max_reports == 500

    def test_custom_max_reports(self) -> None:
        g = ComplianceReportGenerator(max_reports=10)
        assert g._max_reports == 10


# ── Framework control templates ──────────────────────────────────────


class TestFrameworkControlTemplates:
    def test_soc2_has_9_controls(self) -> None:
        assert len(_FRAMEWORK_CONTROLS[ComplianceFramework.SOC2]) == 9

    def test_pci_dss_has_6_controls(self) -> None:
        assert len(_FRAMEWORK_CONTROLS[ComplianceFramework.PCI_DSS]) == 6

    def test_hipaa_has_4_controls(self) -> None:
        assert len(_FRAMEWORK_CONTROLS[ComplianceFramework.HIPAA]) == 4

    def test_iso27001_has_5_controls(self) -> None:
        assert len(_FRAMEWORK_CONTROLS[ComplianceFramework.ISO27001]) == 5

    def test_nist_has_5_controls(self) -> None:
        assert len(_FRAMEWORK_CONTROLS[ComplianceFramework.NIST]) == 5

    def test_soc2_first_control_id(self) -> None:
        assert _FRAMEWORK_CONTROLS[ComplianceFramework.SOC2][0]["id"] == "CC1.1"

    def test_pci_first_control_id(self) -> None:
        assert _FRAMEWORK_CONTROLS[ComplianceFramework.PCI_DSS][0]["id"] == "PCI-1"


# ── generate_report ──────────────────────────────────────────────────


class TestGenerateReport:
    def test_soc2_report_default(self) -> None:
        g = _gen()
        r = g.generate_report(ComplianceFramework.SOC2)
        assert r.framework == ComplianceFramework.SOC2
        assert len(r.controls) == 9
        assert r.not_assessed_count == 9
        assert r.overall_score == 0.0

    def test_pci_dss_report(self) -> None:
        g = _gen()
        r = g.generate_report(ComplianceFramework.PCI_DSS)
        assert len(r.controls) == 6

    def test_hipaa_report(self) -> None:
        g = _gen()
        r = g.generate_report(ComplianceFramework.HIPAA)
        assert len(r.controls) == 4

    def test_iso27001_report(self) -> None:
        g = _gen()
        r = g.generate_report(ComplianceFramework.ISO27001)
        assert len(r.controls) == 5

    def test_nist_report(self) -> None:
        g = _gen()
        r = g.generate_report(ComplianceFramework.NIST)
        assert len(r.controls) == 5

    def test_with_control_statuses_all_passing(self) -> None:
        g = _gen()
        statuses = {f"NIST-{s}": ControlStatus.PASSING for s in ["ID", "PR", "DE", "RS", "RC"]}
        r = g.generate_report(ComplianceFramework.NIST, control_statuses=statuses)
        assert r.passing_count == 5
        assert r.overall_score == pytest.approx(100.0)

    def test_with_mixed_statuses(self) -> None:
        g = _gen()
        statuses = {
            "NIST-ID": ControlStatus.PASSING,
            "NIST-PR": ControlStatus.FAILING,
            "NIST-DE": ControlStatus.NOT_ASSESSED,
        }
        r = g.generate_report(ComplianceFramework.NIST, control_statuses=statuses)
        assert r.passing_count == 1
        assert r.failing_count == 1
        assert r.not_assessed_count == 3  # DE + RS + RC

    def test_not_applicable_excluded_from_score(self) -> None:
        g = _gen()
        statuses = {
            "NIST-ID": ControlStatus.PASSING,
            "NIST-PR": ControlStatus.PASSING,
            "NIST-DE": ControlStatus.NOT_APPLICABLE,
            "NIST-RS": ControlStatus.NOT_APPLICABLE,
            "NIST-RC": ControlStatus.NOT_APPLICABLE,
        }
        r = g.generate_report(ComplianceFramework.NIST, control_statuses=statuses)
        # 2 passing out of 2 applicable => 100%
        assert r.overall_score == pytest.approx(100.0)

    def test_score_computation_partial(self) -> None:
        g = _gen()
        statuses = {
            "NIST-ID": ControlStatus.PASSING,
            "NIST-PR": ControlStatus.FAILING,
        }
        r = g.generate_report(ComplianceFramework.NIST, control_statuses=statuses)
        # 1 passing / 5 applicable = 20%
        assert r.overall_score == pytest.approx(20.0)

    def test_custom_title(self) -> None:
        g = _gen()
        r = g.generate_report(ComplianceFramework.SOC2, title="Q1 Audit")
        assert r.title == "Q1 Audit"

    def test_default_title_generated(self) -> None:
        g = _gen()
        r = g.generate_report(ComplianceFramework.SOC2)
        assert "SOC2" in r.title

    def test_max_reports_limit_raises(self) -> None:
        g = ComplianceReportGenerator(max_reports=2)
        g.generate_report(ComplianceFramework.SOC2)
        g.generate_report(ComplianceFramework.NIST)
        with pytest.raises(ValueError, match="Maximum reports limit reached"):
            g.generate_report(ComplianceFramework.HIPAA)

    def test_generated_by_and_period(self) -> None:
        g = _gen()
        r = g.generate_report(
            ComplianceFramework.SOC2,
            generated_by="auditor",
            period_start="2025-01-01",
            period_end="2025-03-31",
        )
        assert r.generated_by == "auditor"
        assert r.period_start == "2025-01-01"
        assert r.period_end == "2025-03-31"


# ── add_evidence ─────────────────────────────────────────────────────


class TestAddEvidence:
    def test_basic_evidence(self) -> None:
        g = _gen()
        r = g.generate_report(ComplianceFramework.SOC2)
        ev = g.add_evidence(r.id, "CC1.1", "Audit log present", source="splunk")
        assert ev is not None
        assert ev.control_id == "CC1.1"
        assert ev.description == "Audit log present"
        assert ev.source == "splunk"

    def test_evidence_appended_to_control(self) -> None:
        g = _gen()
        r = g.generate_report(ComplianceFramework.SOC2)
        g.add_evidence(r.id, "CC1.1", "Evidence A")
        g.add_evidence(r.id, "CC1.1", "Evidence B")
        ctrl = [c for c in r.controls if c.id == "CC1.1"][0]
        assert len(ctrl.evidence) == 2

    def test_evidence_not_found_report(self) -> None:
        g = _gen()
        result = g.add_evidence("nonexistent", "CC1.1", "desc")
        assert result is None

    def test_evidence_not_found_control(self) -> None:
        g = _gen()
        r = g.generate_report(ComplianceFramework.SOC2)
        result = g.add_evidence(r.id, "FAKE-999", "desc")
        assert result is None


# ── get_report ───────────────────────────────────────────────────────


class TestGetReport:
    def test_found(self) -> None:
        g = _gen()
        r = g.generate_report(ComplianceFramework.SOC2)
        fetched = g.get_report(r.id)
        assert fetched is not None
        assert fetched.id == r.id

    def test_not_found(self) -> None:
        g = _gen()
        assert g.get_report("missing") is None


# ── list_reports ─────────────────────────────────────────────────────


class TestListReports:
    def test_all_reports(self) -> None:
        g = _gen()
        g.generate_report(ComplianceFramework.SOC2)
        g.generate_report(ComplianceFramework.NIST)
        assert len(g.list_reports()) == 2

    def test_filter_by_framework(self) -> None:
        g = _gen()
        g.generate_report(ComplianceFramework.SOC2)
        g.generate_report(ComplianceFramework.NIST)
        result = g.list_reports(framework=ComplianceFramework.SOC2)
        assert len(result) == 1
        assert result[0].framework == ComplianceFramework.SOC2

    def test_limit(self) -> None:
        g = _gen()
        for _ in range(5):
            g.generate_report(ComplianceFramework.SOC2)
        assert len(g.list_reports(limit=3)) == 3

    def test_empty(self) -> None:
        g = _gen()
        assert g.list_reports() == []


# ── get_compliance_score ─────────────────────────────────────────────


class TestGetComplianceScore:
    def test_basic_score(self) -> None:
        g = _gen()
        r = g.generate_report(
            ComplianceFramework.NIST,
            control_statuses={"NIST-ID": ControlStatus.PASSING},
        )
        score = g.get_compliance_score(r.id)
        assert score is not None
        assert score["report_id"] == r.id
        assert score["framework"] == "nist"
        assert score["passing"] == 1
        assert score["total_controls"] == 5

    def test_not_found(self) -> None:
        g = _gen()
        assert g.get_compliance_score("nope") is None


# ── get_stats ────────────────────────────────────────────────────────


class TestGetStats:
    def test_empty(self) -> None:
        g = _gen()
        stats = g.get_stats()
        assert stats["total_reports"] == 0
        assert stats["avg_score"] == 0.0
        assert stats["by_framework"] == {}

    def test_with_reports(self) -> None:
        g = _gen()
        g.generate_report(ComplianceFramework.SOC2)
        g.generate_report(ComplianceFramework.SOC2)
        g.generate_report(ComplianceFramework.NIST)
        stats = g.get_stats()
        assert stats["total_reports"] == 3
        assert stats["by_framework"]["soc2"] == 2
        assert stats["by_framework"]["nist"] == 1

    def test_avg_score_computed(self) -> None:
        g = _gen()
        g.generate_report(
            ComplianceFramework.NIST,
            control_statuses={
                "NIST-ID": ControlStatus.PASSING,
                "NIST-PR": ControlStatus.PASSING,
                "NIST-DE": ControlStatus.PASSING,
                "NIST-RS": ControlStatus.PASSING,
                "NIST-RC": ControlStatus.PASSING,
            },
        )
        stats = g.get_stats()
        assert stats["avg_score"] == pytest.approx(100.0)
