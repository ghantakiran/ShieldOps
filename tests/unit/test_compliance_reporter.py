"""Tests for shieldops.audit.compliance_reporter — AuditComplianceReporter."""

from __future__ import annotations

from shieldops.audit.compliance_reporter import (
    AuditComplianceReport,
    AuditComplianceReporter,
    AuditScope,
    ComplianceLevel,
    ComplianceRecord,
    ComplianceRule,
    ReportType,
)


def _engine(**kw) -> AuditComplianceReporter:
    return AuditComplianceReporter(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_report_type_soc2(self):
        assert ReportType.SOC2 == "soc2"

    def test_report_type_hipaa(self):
        assert ReportType.HIPAA == "hipaa"

    def test_report_type_pci_dss(self):
        assert ReportType.PCI_DSS == "pci_dss"

    def test_report_type_iso_27001(self):
        assert ReportType.ISO_27001 == "iso_27001"

    def test_report_type_gdpr(self):
        assert ReportType.GDPR == "gdpr"

    def test_compliance_level_compliant(self):
        assert ComplianceLevel.COMPLIANT == "compliant"

    def test_compliance_level_partially_compliant(self):
        assert ComplianceLevel.PARTIALLY_COMPLIANT == "partially_compliant"

    def test_compliance_level_non_compliant(self):
        assert ComplianceLevel.NON_COMPLIANT == "non_compliant"

    def test_compliance_level_exempt(self):
        assert ComplianceLevel.EXEMPT == "exempt"

    def test_compliance_level_under_review(self):
        assert ComplianceLevel.UNDER_REVIEW == "under_review"

    def test_audit_scope_full(self):
        assert AuditScope.FULL == "full"

    def test_audit_scope_partial(self):
        assert AuditScope.PARTIAL == "partial"

    def test_audit_scope_targeted(self):
        assert AuditScope.TARGETED == "targeted"

    def test_audit_scope_follow_up(self):
        assert AuditScope.FOLLOW_UP == "follow_up"

    def test_audit_scope_continuous(self):
        assert AuditScope.CONTINUOUS == "continuous"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_compliance_record_defaults(self):
        r = ComplianceRecord()
        assert r.id
        assert r.framework == ""
        assert r.report_type == ReportType.SOC2
        assert r.compliance_level == ComplianceLevel.UNDER_REVIEW
        assert r.audit_scope == AuditScope.FULL
        assert r.compliance_score == 0.0
        assert r.findings_count == 0
        assert r.team == ""
        assert r.created_at > 0

    def test_compliance_rule_defaults(self):
        p = ComplianceRule()
        assert p.id
        assert p.control_id == ""
        assert p.report_type == ReportType.SOC2
        assert p.audit_scope == AuditScope.FULL
        assert p.required_evidence_count == 0
        assert p.description == ""
        assert p.created_at > 0

    def test_audit_compliance_report_defaults(self):
        r = AuditComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.compliant_count == 0
        assert r.avg_compliance_score == 0.0
        assert r.by_type == {}
        assert r.by_level == {}
        assert r.by_scope == {}
        assert r.non_compliant == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_compliance
# ---------------------------------------------------------------------------


class TestRecordCompliance:
    def test_basic(self):
        eng = _engine()
        r = eng.record_compliance(
            framework="SOC2-CC1",
            report_type=ReportType.SOC2,
            compliance_level=ComplianceLevel.COMPLIANT,
            audit_scope=AuditScope.FULL,
            compliance_score=92.5,
            findings_count=3,
            team="security",
        )
        assert r.framework == "SOC2-CC1"
        assert r.report_type == ReportType.SOC2
        assert r.compliance_level == ComplianceLevel.COMPLIANT
        assert r.audit_scope == AuditScope.FULL
        assert r.compliance_score == 92.5
        assert r.findings_count == 3
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_compliance(framework=f"FW-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_compliance
# ---------------------------------------------------------------------------


class TestGetCompliance:
    def test_found(self):
        eng = _engine()
        r = eng.record_compliance(
            framework="SOC2-CC1",
            compliance_level=ComplianceLevel.COMPLIANT,
        )
        result = eng.get_compliance(r.id)
        assert result is not None
        assert result.compliance_level == ComplianceLevel.COMPLIANT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_compliance("nonexistent") is None


# ---------------------------------------------------------------------------
# list_compliance_records
# ---------------------------------------------------------------------------


class TestListComplianceRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_compliance(framework="FW-001")
        eng.record_compliance(framework="FW-002")
        assert len(eng.list_compliance_records()) == 2

    def test_filter_by_report_type(self):
        eng = _engine()
        eng.record_compliance(
            framework="FW-001",
            report_type=ReportType.HIPAA,
        )
        eng.record_compliance(
            framework="FW-002",
            report_type=ReportType.GDPR,
        )
        results = eng.list_compliance_records(report_type=ReportType.HIPAA)
        assert len(results) == 1

    def test_filter_by_compliance_level(self):
        eng = _engine()
        eng.record_compliance(
            framework="FW-001",
            compliance_level=ComplianceLevel.COMPLIANT,
        )
        eng.record_compliance(
            framework="FW-002",
            compliance_level=ComplianceLevel.NON_COMPLIANT,
        )
        results = eng.list_compliance_records(compliance_level=ComplianceLevel.COMPLIANT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_compliance(framework="FW-001", team="security")
        eng.record_compliance(framework="FW-002", team="platform")
        results = eng.list_compliance_records(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_compliance(framework=f"FW-{i}")
        assert len(eng.list_compliance_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        p = eng.add_rule(
            control_id="CC1.1",
            report_type=ReportType.SOC2,
            audit_scope=AuditScope.TARGETED,
            required_evidence_count=5,
            description="Access control policy",
        )
        assert p.control_id == "CC1.1"
        assert p.report_type == ReportType.SOC2
        assert p.audit_scope == AuditScope.TARGETED
        assert p.required_evidence_count == 5
        assert p.description == "Access control policy"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(control_id=f"CC-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_compliance_gaps
# ---------------------------------------------------------------------------


class TestAnalyzeComplianceGaps:
    def test_with_data(self):
        eng = _engine()
        eng.record_compliance(
            framework="FW-001",
            report_type=ReportType.SOC2,
            compliance_score=90.0,
        )
        eng.record_compliance(
            framework="FW-002",
            report_type=ReportType.SOC2,
            compliance_score=80.0,
        )
        result = eng.analyze_compliance_gaps()
        assert "soc2" in result
        assert result["soc2"]["count"] == 2
        assert result["soc2"]["avg_compliance_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_compliance_gaps() == {}


# ---------------------------------------------------------------------------
# identify_non_compliant
# ---------------------------------------------------------------------------


class TestIdentifyNonCompliant:
    def test_detects_non_compliant(self):
        eng = _engine()
        eng.record_compliance(
            framework="FW-001",
            compliance_level=ComplianceLevel.NON_COMPLIANT,
        )
        eng.record_compliance(
            framework="FW-002",
            compliance_level=ComplianceLevel.COMPLIANT,
        )
        results = eng.identify_non_compliant()
        assert len(results) == 1
        assert results[0]["framework"] == "FW-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_non_compliant() == []


# ---------------------------------------------------------------------------
# rank_by_compliance_score
# ---------------------------------------------------------------------------


class TestRankByComplianceScore:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_compliance(framework="FW-001", team="security", compliance_score=95.0)
        eng.record_compliance(framework="FW-002", team="security", compliance_score=85.0)
        eng.record_compliance(framework="FW-003", team="platform", compliance_score=70.0)
        results = eng.rank_by_compliance_score()
        assert len(results) == 2
        assert results[0]["team"] == "platform"
        assert results[0]["avg_compliance_score"] == 70.0
        assert results[1]["team"] == "security"
        assert results[1]["avg_compliance_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance_score() == []


# ---------------------------------------------------------------------------
# detect_compliance_trends
# ---------------------------------------------------------------------------


class TestDetectComplianceTrends:
    def test_stable(self):
        eng = _engine()
        for score in [85.0, 85.0, 85.0, 85.0]:
            eng.record_compliance(framework="FW", compliance_score=score)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for score in [60.0, 60.0, 90.0, 90.0]:
            eng.record_compliance(framework="FW", compliance_score=score)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_degrading(self):
        eng = _engine()
        for score in [90.0, 90.0, 60.0, 60.0]:
            eng.record_compliance(framework="FW", compliance_score=score)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "degrading"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_compliance_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_compliance(
            framework="SOC2-CC1",
            report_type=ReportType.SOC2,
            compliance_level=ComplianceLevel.COMPLIANT,
            compliance_score=95.0,
            team="security",
        )
        report = eng.generate_report()
        assert isinstance(report, AuditComplianceReport)
        assert report.total_records == 1
        assert report.compliant_count == 1
        assert report.avg_compliance_score == 95.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]

    def test_below_threshold(self):
        eng = _engine(min_compliance_score=90.0)
        eng.record_compliance(
            framework="FW-001",
            compliance_score=70.0,
            compliance_level=ComplianceLevel.NON_COMPLIANT,
        )
        report = eng.generate_report()
        assert any("below" in r for r in report.recommendations)
        assert any("non-compliant" in r for r in report.recommendations)


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_compliance(framework="FW-001")
        eng.add_rule(control_id="CC1.1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_compliance(
            framework="SOC2-CC1",
            report_type=ReportType.SOC2,
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_frameworks"] == 1
        assert "soc2" in stats["type_distribution"]
