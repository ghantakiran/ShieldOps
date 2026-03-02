"""Tests for shieldops.security.security_compliance_scorer — SecurityComplianceScorer."""

from __future__ import annotations

from shieldops.security.security_compliance_scorer import (
    ComplianceArea,
    ComplianceGapAssessment,
    ComplianceScoreRecord,
    FrameworkType,
    GapSeverity,
    SecurityComplianceReport,
    SecurityComplianceScorer,
)


def _engine(**kw) -> SecurityComplianceScorer:
    return SecurityComplianceScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_area_access_control(self):
        assert ComplianceArea.ACCESS_CONTROL == "access_control"

    def test_area_data_protection(self):
        assert ComplianceArea.DATA_PROTECTION == "data_protection"

    def test_area_network_security(self):
        assert ComplianceArea.NETWORK_SECURITY == "network_security"

    def test_area_incident_management(self):
        assert ComplianceArea.INCIDENT_MANAGEMENT == "incident_management"

    def test_area_vulnerability_management(self):
        assert ComplianceArea.VULNERABILITY_MANAGEMENT == "vulnerability_management"

    def test_severity_critical(self):
        assert GapSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert GapSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert GapSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert GapSeverity.LOW == "low"

    def test_severity_informational(self):
        assert GapSeverity.INFORMATIONAL == "informational"

    def test_framework_soc2(self):
        assert FrameworkType.SOC2 == "soc2"

    def test_framework_hipaa(self):
        assert FrameworkType.HIPAA == "hipaa"

    def test_framework_pci_dss(self):
        assert FrameworkType.PCI_DSS == "pci_dss"

    def test_framework_iso_27001(self):
        assert FrameworkType.ISO_27001 == "iso_27001"

    def test_framework_nist(self):
        assert FrameworkType.NIST == "nist"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_compliance_score_record_defaults(self):
        r = ComplianceScoreRecord()
        assert r.id
        assert r.control_name == ""
        assert r.compliance_area == ComplianceArea.ACCESS_CONTROL
        assert r.gap_severity == GapSeverity.CRITICAL
        assert r.framework_type == FrameworkType.SOC2
        assert r.compliance_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_compliance_gap_assessment_defaults(self):
        a = ComplianceGapAssessment()
        assert a.id
        assert a.control_name == ""
        assert a.compliance_area == ComplianceArea.ACCESS_CONTROL
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_security_compliance_report_defaults(self):
        r = SecurityComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.gap_count == 0
        assert r.avg_compliance_score == 0.0
        assert r.by_area == {}
        assert r.by_severity == {}
        assert r.by_framework == {}
        assert r.top_gaps == []
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
            control_name="AC-001",
            compliance_area=ComplianceArea.DATA_PROTECTION,
            gap_severity=GapSeverity.HIGH,
            framework_type=FrameworkType.HIPAA,
            compliance_score=45.0,
            service="api-gw",
            team="sre",
        )
        assert r.control_name == "AC-001"
        assert r.compliance_area == ComplianceArea.DATA_PROTECTION
        assert r.gap_severity == GapSeverity.HIGH
        assert r.framework_type == FrameworkType.HIPAA
        assert r.compliance_score == 45.0
        assert r.service == "api-gw"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_compliance(control_name=f"CTL-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_compliance
# ---------------------------------------------------------------------------


class TestGetCompliance:
    def test_found(self):
        eng = _engine()
        r = eng.record_compliance(
            control_name="AC-001",
            gap_severity=GapSeverity.CRITICAL,
        )
        result = eng.get_compliance(r.id)
        assert result is not None
        assert result.gap_severity == GapSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_compliance("nonexistent") is None


# ---------------------------------------------------------------------------
# list_compliance_records
# ---------------------------------------------------------------------------


class TestListComplianceRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_compliance(control_name="CTL-1")
        eng.record_compliance(control_name="CTL-2")
        assert len(eng.list_compliance_records()) == 2

    def test_filter_by_area(self):
        eng = _engine()
        eng.record_compliance(
            control_name="CTL-1",
            compliance_area=ComplianceArea.ACCESS_CONTROL,
        )
        eng.record_compliance(
            control_name="CTL-2",
            compliance_area=ComplianceArea.DATA_PROTECTION,
        )
        results = eng.list_compliance_records(compliance_area=ComplianceArea.ACCESS_CONTROL)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_compliance(
            control_name="CTL-1",
            gap_severity=GapSeverity.CRITICAL,
        )
        eng.record_compliance(
            control_name="CTL-2",
            gap_severity=GapSeverity.LOW,
        )
        results = eng.list_compliance_records(gap_severity=GapSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_compliance(control_name="CTL-1", team="sre")
        eng.record_compliance(control_name="CTL-2", team="platform")
        results = eng.list_compliance_records(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_compliance(control_name=f"CTL-{i}")
        assert len(eng.list_compliance_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            control_name="AC-001",
            compliance_area=ComplianceArea.DATA_PROTECTION,
            assessment_score=88.5,
            threshold=80.0,
            breached=True,
            description="compliance threshold exceeded",
        )
        assert a.control_name == "AC-001"
        assert a.compliance_area == ComplianceArea.DATA_PROTECTION
        assert a.assessment_score == 88.5
        assert a.threshold == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(control_name=f"CTL-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_compliance_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeComplianceDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_compliance(
            control_name="CTL-1",
            compliance_area=ComplianceArea.ACCESS_CONTROL,
            compliance_score=40.0,
        )
        eng.record_compliance(
            control_name="CTL-2",
            compliance_area=ComplianceArea.ACCESS_CONTROL,
            compliance_score=60.0,
        )
        result = eng.analyze_compliance_distribution()
        assert "access_control" in result
        assert result["access_control"]["count"] == 2
        assert result["access_control"]["avg_compliance_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_compliance_distribution() == {}


# ---------------------------------------------------------------------------
# identify_compliance_gaps
# ---------------------------------------------------------------------------


class TestIdentifyComplianceGaps:
    def test_detects_below_threshold(self):
        eng = _engine(compliance_gap_threshold=15.0)
        eng.record_compliance(control_name="CTL-1", compliance_score=10.0)
        eng.record_compliance(control_name="CTL-2", compliance_score=50.0)
        results = eng.identify_compliance_gaps()
        assert len(results) == 1
        assert results[0]["control_name"] == "CTL-1"

    def test_sorted_ascending(self):
        eng = _engine(compliance_gap_threshold=50.0)
        eng.record_compliance(control_name="CTL-1", compliance_score=30.0)
        eng.record_compliance(control_name="CTL-2", compliance_score=10.0)
        results = eng.identify_compliance_gaps()
        assert len(results) == 2
        assert results[0]["compliance_score"] == 10.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_compliance_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_compliance
# ---------------------------------------------------------------------------


class TestRankByCompliance:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_compliance(control_name="CTL-1", service="api-gw", compliance_score=90.0)
        eng.record_compliance(control_name="CTL-2", service="auth", compliance_score=30.0)
        results = eng.rank_by_compliance()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_compliance_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance() == []


# ---------------------------------------------------------------------------
# detect_compliance_trends
# ---------------------------------------------------------------------------


class TestDetectComplianceTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(control_name="CTL-1", assessment_score=50.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(control_name="CTL-1", assessment_score=20.0)
        eng.add_assessment(control_name="CTL-2", assessment_score=20.0)
        eng.add_assessment(control_name="CTL-3", assessment_score=80.0)
        eng.add_assessment(control_name="CTL-4", assessment_score=80.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_compliance_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(compliance_gap_threshold=15.0)
        eng.record_compliance(
            control_name="AC-001",
            compliance_area=ComplianceArea.DATA_PROTECTION,
            gap_severity=GapSeverity.HIGH,
            framework_type=FrameworkType.HIPAA,
            compliance_score=10.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SecurityComplianceReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_compliance(control_name="CTL-1")
        eng.add_assessment(control_name="CTL-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["area_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_compliance(
            control_name="AC-001",
            compliance_area=ComplianceArea.ACCESS_CONTROL,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "access_control" in stats["area_distribution"]
