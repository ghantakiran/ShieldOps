"""Tests for shieldops.audit.audit_compliance_mapper — AuditComplianceMapper."""

from __future__ import annotations

from shieldops.audit.audit_compliance_mapper import (
    AuditComplianceMapper,
    AuditComplianceReport,
    ComplianceFramework,
    ComplianceMappingRecord,
    MappingAssessment,
    MappingConfidence,
    MappingStatus,
)


def _engine(**kw) -> AuditComplianceMapper:
    return AuditComplianceMapper(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_framework_soc2(self):
        assert ComplianceFramework.SOC2 == "soc2"

    def test_framework_iso27001(self):
        assert ComplianceFramework.ISO27001 == "iso27001"

    def test_framework_hipaa(self):
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_framework_pci_dss(self):
        assert ComplianceFramework.PCI_DSS == "pci_dss"

    def test_framework_gdpr(self):
        assert ComplianceFramework.GDPR == "gdpr"

    def test_status_mapped(self):
        assert MappingStatus.MAPPED == "mapped"

    def test_status_partially_mapped(self):
        assert MappingStatus.PARTIALLY_MAPPED == "partially_mapped"

    def test_status_unmapped(self):
        assert MappingStatus.UNMAPPED == "unmapped"

    def test_status_review_needed(self):
        assert MappingStatus.REVIEW_NEEDED == "review_needed"

    def test_status_exempt(self):
        assert MappingStatus.EXEMPT == "exempt"

    def test_confidence_high(self):
        assert MappingConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert MappingConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert MappingConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert MappingConfidence.SPECULATIVE == "speculative"

    def test_confidence_none(self):
        assert MappingConfidence.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_mapping_record_defaults(self):
        r = ComplianceMappingRecord()
        assert r.id
        assert r.mapping_id == ""
        assert r.compliance_framework == ComplianceFramework.SOC2
        assert r.mapping_status == MappingStatus.UNMAPPED
        assert r.mapping_confidence == MappingConfidence.NONE
        assert r.coverage_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_mapping_assessment_defaults(self):
        a = MappingAssessment()
        assert a.id
        assert a.mapping_id == ""
        assert a.compliance_framework == ComplianceFramework.SOC2
        assert a.assessment_score == 0.0
        assert a.threshold == 85.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_compliance_report_defaults(self):
        r = AuditComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.unmapped_count == 0
        assert r.avg_coverage_score == 0.0
        assert r.by_framework == {}
        assert r.by_status == {}
        assert r.by_confidence == {}
        assert r.top_unmapped == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_mapping
# ---------------------------------------------------------------------------


class TestRecordMapping:
    def test_basic(self):
        eng = _engine()
        r = eng.record_mapping(
            mapping_id="MAP-001",
            compliance_framework=ComplianceFramework.SOC2,
            mapping_status=MappingStatus.MAPPED,
            mapping_confidence=MappingConfidence.HIGH,
            coverage_score=95.0,
            service="auth-svc",
            team="compliance",
        )
        assert r.mapping_id == "MAP-001"
        assert r.compliance_framework == ComplianceFramework.SOC2
        assert r.mapping_status == MappingStatus.MAPPED
        assert r.mapping_confidence == MappingConfidence.HIGH
        assert r.coverage_score == 95.0
        assert r.team == "compliance"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mapping(mapping_id=f"MAP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_mapping
# ---------------------------------------------------------------------------


class TestGetMapping:
    def test_found(self):
        eng = _engine()
        r = eng.record_mapping(
            mapping_id="MAP-001",
            mapping_status=MappingStatus.MAPPED,
        )
        result = eng.get_mapping(r.id)
        assert result is not None
        assert result.mapping_status == MappingStatus.MAPPED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_mapping("nonexistent") is None


# ---------------------------------------------------------------------------
# list_mappings
# ---------------------------------------------------------------------------


class TestListMappings:
    def test_list_all(self):
        eng = _engine()
        eng.record_mapping(mapping_id="MAP-001")
        eng.record_mapping(mapping_id="MAP-002")
        assert len(eng.list_mappings()) == 2

    def test_filter_by_framework(self):
        eng = _engine()
        eng.record_mapping(
            mapping_id="MAP-001",
            compliance_framework=ComplianceFramework.SOC2,
        )
        eng.record_mapping(
            mapping_id="MAP-002",
            compliance_framework=ComplianceFramework.HIPAA,
        )
        results = eng.list_mappings(
            compliance_framework=ComplianceFramework.SOC2,
        )
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_mapping(
            mapping_id="MAP-001",
            mapping_status=MappingStatus.MAPPED,
        )
        eng.record_mapping(
            mapping_id="MAP-002",
            mapping_status=MappingStatus.UNMAPPED,
        )
        results = eng.list_mappings(mapping_status=MappingStatus.MAPPED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_mapping(mapping_id="MAP-001", team="compliance")
        eng.record_mapping(mapping_id="MAP-002", team="security")
        results = eng.list_mappings(team="compliance")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mapping(mapping_id=f"MAP-{i}")
        assert len(eng.list_mappings(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            mapping_id="MAP-001",
            compliance_framework=ComplianceFramework.SOC2,
            assessment_score=60.0,
            threshold=85.0,
            description="Below threshold",
        )
        assert a.mapping_id == "MAP-001"
        assert a.compliance_framework == ComplianceFramework.SOC2
        assert a.assessment_score == 60.0
        assert a.breached is True

    def test_not_breached(self):
        eng = _engine()
        a = eng.add_assessment(
            mapping_id="MAP-002",
            assessment_score=90.0,
            threshold=85.0,
        )
        assert a.breached is False

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(mapping_id=f"MAP-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_mapping_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeMappingDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_mapping(
            mapping_id="MAP-001",
            compliance_framework=ComplianceFramework.SOC2,
            coverage_score=80.0,
        )
        eng.record_mapping(
            mapping_id="MAP-002",
            compliance_framework=ComplianceFramework.SOC2,
            coverage_score=90.0,
        )
        result = eng.analyze_mapping_distribution()
        assert "soc2" in result
        assert result["soc2"]["count"] == 2
        assert result["soc2"]["avg_coverage_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_mapping_distribution() == {}


# ---------------------------------------------------------------------------
# identify_unmapped_controls
# ---------------------------------------------------------------------------


class TestIdentifyUnmappedControls:
    def test_detects_unmapped_and_review(self):
        eng = _engine()
        eng.record_mapping(
            mapping_id="MAP-001",
            mapping_status=MappingStatus.UNMAPPED,
        )
        eng.record_mapping(
            mapping_id="MAP-002",
            mapping_status=MappingStatus.REVIEW_NEEDED,
        )
        eng.record_mapping(
            mapping_id="MAP-003",
            mapping_status=MappingStatus.MAPPED,
        )
        results = eng.identify_unmapped_controls()
        assert len(results) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unmapped_controls() == []


# ---------------------------------------------------------------------------
# rank_by_coverage
# ---------------------------------------------------------------------------


class TestRankByCoverage:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_mapping(mapping_id="MAP-001", service="api", coverage_score=90.0)
        eng.record_mapping(mapping_id="MAP-002", service="db", coverage_score=30.0)
        results = eng.rank_by_coverage()
        assert len(results) == 2
        assert results[0]["service"] == "db"
        assert results[0]["avg_coverage_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage() == []


# ---------------------------------------------------------------------------
# detect_mapping_trends
# ---------------------------------------------------------------------------


class TestDetectMappingTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(mapping_id="MAP-001", assessment_score=50.0)
        result = eng.detect_mapping_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(mapping_id="MAP-001", assessment_score=30.0)
        eng.add_assessment(mapping_id="MAP-002", assessment_score=30.0)
        eng.add_assessment(mapping_id="MAP-003", assessment_score=80.0)
        eng.add_assessment(mapping_id="MAP-004", assessment_score=80.0)
        result = eng.detect_mapping_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_mapping_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_mapping(
            mapping_id="MAP-001",
            compliance_framework=ComplianceFramework.SOC2,
            mapping_status=MappingStatus.UNMAPPED,
            coverage_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AuditComplianceReport)
        assert report.total_records == 1
        assert report.unmapped_count == 1
        assert len(report.top_unmapped) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_mapping(mapping_id="MAP-001")
        eng.add_assessment(mapping_id="MAP-001")
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
        assert stats["framework_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_mapping(
            mapping_id="MAP-001",
            compliance_framework=ComplianceFramework.SOC2,
            team="compliance",
            service="api",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "soc2" in stats["framework_distribution"]
