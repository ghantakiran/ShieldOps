"""Tests for shieldops.agents.compliance_auditor — AgentComplianceAuditor."""

from __future__ import annotations

from shieldops.agents.compliance_auditor import (
    AgentComplianceAuditor,
    AuditEvidence,
    AuditRecord,
    AuditResult,
    ComplianceAuditorReport,
    ComplianceFramework,
    EvidenceType,
)


def _engine(**kw) -> AgentComplianceAuditor:
    return AgentComplianceAuditor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ComplianceFramework (5)
    def test_framework_soc2(self):
        assert ComplianceFramework.SOC2 == "soc2"

    def test_framework_pci_dss(self):
        assert ComplianceFramework.PCI_DSS == "pci_dss"

    def test_framework_hipaa(self):
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_framework_gdpr(self):
        assert ComplianceFramework.GDPR == "gdpr"

    def test_framework_iso_27001(self):
        assert ComplianceFramework.ISO_27001 == "iso_27001"

    # AuditResult (5)
    def test_result_pass(self):
        assert AuditResult.PASS == "pass_result"  # noqa: S105

    def test_result_fail(self):
        assert AuditResult.FAIL == "fail"

    def test_result_warning(self):
        assert AuditResult.WARNING == "warning"

    def test_result_not_applicable(self):
        assert AuditResult.NOT_APPLICABLE == "not_applicable"

    def test_result_needs_review(self):
        assert AuditResult.NEEDS_REVIEW == "needs_review"

    # EvidenceType (5)
    def test_evidence_log_entry(self):
        assert EvidenceType.LOG_ENTRY == "log_entry"

    def test_evidence_configuration(self):
        assert EvidenceType.CONFIGURATION == "configuration"

    def test_evidence_access_record(self):
        assert EvidenceType.ACCESS_RECORD == "access_record"

    def test_evidence_policy_check(self):
        assert EvidenceType.POLICY_CHECK == "policy_check"

    def test_evidence_approval_record(self):
        assert EvidenceType.APPROVAL_RECORD == "approval_record"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_audit_record_defaults(self):
        r = AuditRecord()
        assert r.id
        assert r.agent_name == ""
        assert r.compliance_framework == ComplianceFramework.SOC2
        assert r.audit_result == AuditResult.PASS
        assert r.evidence_type == EvidenceType.LOG_ENTRY
        assert r.finding_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_audit_evidence_defaults(self):
        r = AuditEvidence()
        assert r.id
        assert r.evidence_label == ""
        assert r.compliance_framework == ComplianceFramework.PCI_DSS
        assert r.audit_result == AuditResult.WARNING
        assert r.confidence_score == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = ComplianceAuditorReport()
        assert r.total_audits == 0
        assert r.total_evidence == 0
        assert r.pass_rate_pct == 0.0
        assert r.by_framework == {}
        assert r.by_result == {}
        assert r.failure_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_audit
# -------------------------------------------------------------------


class TestRecordAudit:
    def test_basic(self):
        eng = _engine()
        r = eng.record_audit(
            "agent-a",
            compliance_framework=ComplianceFramework.HIPAA,
            audit_result=AuditResult.PASS,
        )
        assert r.agent_name == "agent-a"
        assert r.compliance_framework == ComplianceFramework.HIPAA

    def test_with_finding_count(self):
        eng = _engine()
        r = eng.record_audit("agent-b", finding_count=5)
        assert r.finding_count == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_audit(f"agent-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_audit
# -------------------------------------------------------------------


class TestGetAudit:
    def test_found(self):
        eng = _engine()
        r = eng.record_audit("agent-a")
        assert eng.get_audit(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_audit("nonexistent") is None


# -------------------------------------------------------------------
# list_audits
# -------------------------------------------------------------------


class TestListAudits:
    def test_list_all(self):
        eng = _engine()
        eng.record_audit("agent-a")
        eng.record_audit("agent-b")
        assert len(eng.list_audits()) == 2

    def test_filter_by_agent(self):
        eng = _engine()
        eng.record_audit("agent-a")
        eng.record_audit("agent-b")
        results = eng.list_audits(agent_name="agent-a")
        assert len(results) == 1

    def test_filter_by_framework(self):
        eng = _engine()
        eng.record_audit("agent-a", compliance_framework=ComplianceFramework.GDPR)
        eng.record_audit("agent-b", compliance_framework=ComplianceFramework.SOC2)
        results = eng.list_audits(compliance_framework=ComplianceFramework.GDPR)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_evidence
# -------------------------------------------------------------------


class TestAddEvidence:
    def test_basic(self):
        eng = _engine()
        r = eng.add_evidence(
            "evidence-1",
            compliance_framework=ComplianceFramework.ISO_27001,
            audit_result=AuditResult.PASS,
            confidence_score=92.0,
        )
        assert r.evidence_label == "evidence-1"
        assert r.confidence_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_evidence(f"evidence-{i}")
        assert len(eng._evidence) == 2


# -------------------------------------------------------------------
# analyze_agent_compliance
# -------------------------------------------------------------------


class TestAnalyzeAgentCompliance:
    def test_with_data(self):
        eng = _engine()
        eng.record_audit("agent-a", audit_result=AuditResult.PASS)
        eng.record_audit("agent-a", audit_result=AuditResult.FAIL)
        result = eng.analyze_agent_compliance("agent-a")
        assert result["agent_name"] == "agent-a"
        assert result["total_records"] == 2
        assert result["pass_count"] == 1
        assert result["pass_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_agent_compliance("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_pass_rate_pct=50.0)
        eng.record_audit("agent-a", audit_result=AuditResult.PASS)
        result = eng.analyze_agent_compliance("agent-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_non_compliant_agents
# -------------------------------------------------------------------


class TestIdentifyNonCompliantAgents:
    def test_with_non_compliant(self):
        eng = _engine()
        eng.record_audit("agent-a", audit_result=AuditResult.FAIL)
        eng.record_audit("agent-a", audit_result=AuditResult.FAIL)
        eng.record_audit("agent-b", audit_result=AuditResult.PASS)
        results = eng.identify_non_compliant_agents()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_non_compliant_agents() == []


# -------------------------------------------------------------------
# rank_by_compliance_score
# -------------------------------------------------------------------


class TestRankByComplianceScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_audit("agent-a", finding_count=10)
        eng.record_audit("agent-a", finding_count=6)
        eng.record_audit("agent-b", finding_count=2)
        results = eng.rank_by_compliance_score()
        assert results[0]["agent_name"] == "agent-a"
        assert results[0]["avg_finding_count"] == 8.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance_score() == []


# -------------------------------------------------------------------
# detect_compliance_drift
# -------------------------------------------------------------------


class TestDetectComplianceDrift:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_audit("agent-a", audit_result=AuditResult.FAIL)
        eng.record_audit("agent-b", audit_result=AuditResult.FAIL)
        results = eng.detect_compliance_drift()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"
        assert results[0]["recurring"] is True

    def test_no_recurring(self):
        eng = _engine()
        eng.record_audit("agent-a", audit_result=AuditResult.FAIL)
        assert eng.detect_compliance_drift() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_audit("agent-a", audit_result=AuditResult.FAIL)
        eng.record_audit("agent-b", audit_result=AuditResult.PASS)
        eng.add_evidence("evidence-1")
        report = eng.generate_report()
        assert report.total_audits == 2
        assert report.total_evidence == 1
        assert report.by_framework != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_audits == 0
        assert report.recommendations[0] == "Agent compliance auditing meets targets"

    def test_failure_recommendation(self):
        eng = _engine()
        eng.record_audit("agent-a", audit_result=AuditResult.FAIL)
        report = eng.generate_report()
        assert "failure" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_audit("agent-a")
        eng.add_evidence("evidence-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._evidence) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_evidence"] == 0
        assert stats["framework_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_audit("agent-a", compliance_framework=ComplianceFramework.SOC2)
        eng.record_audit("agent-b", compliance_framework=ComplianceFramework.HIPAA)
        eng.add_evidence("evidence-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_evidence"] == 1
        assert stats["unique_agents"] == 2
