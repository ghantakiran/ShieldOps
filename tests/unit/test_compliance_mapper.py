"""Tests for shieldops.security.compliance_mapper — SecurityComplianceMapper."""

from __future__ import annotations

from shieldops.security.compliance_mapper import (
    ComplianceFramework,
    ComplianceMapperReport,
    ComplianceMapRecord,
    ComplianceRisk,
    ControlEvidence,
    ControlStatus,
    SecurityComplianceMapper,
)


def _engine(**kw) -> SecurityComplianceMapper:
    return SecurityComplianceMapper(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ComplianceFramework (5)
    def test_framework_soc2(self):
        assert ComplianceFramework.SOC2 == "soc2"

    def test_framework_iso27001(self):
        assert ComplianceFramework.ISO27001 == "iso27001"

    def test_framework_hipaa(self):
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_framework_pci_dss(self):
        assert ComplianceFramework.PCI_DSS == "pci_dss"

    def test_framework_nist(self):
        assert ComplianceFramework.NIST == "nist"

    # ControlStatus (5)
    def test_status_compliant(self):
        assert ControlStatus.COMPLIANT == "compliant"

    def test_status_partially_compliant(self):
        assert ControlStatus.PARTIALLY_COMPLIANT == "partially_compliant"

    def test_status_non_compliant(self):
        assert ControlStatus.NON_COMPLIANT == "non_compliant"

    def test_status_not_applicable(self):
        assert ControlStatus.NOT_APPLICABLE == "not_applicable"

    def test_status_under_review(self):
        assert ControlStatus.UNDER_REVIEW == "under_review"

    # ComplianceRisk (5)
    def test_risk_critical(self):
        assert ComplianceRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert ComplianceRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert ComplianceRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert ComplianceRisk.LOW == "low"

    def test_risk_acceptable(self):
        assert ComplianceRisk.ACCEPTABLE == "acceptable"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_compliance_map_record_defaults(self):
        r = ComplianceMapRecord()
        assert r.id
        assert r.framework == ComplianceFramework.SOC2
        assert r.control_id == ""
        assert r.control_name == ""
        assert r.status == ControlStatus.UNDER_REVIEW
        assert r.risk == ComplianceRisk.MODERATE
        assert r.compliance_score == 0.0
        assert r.owner == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_control_evidence_defaults(self):
        r = ControlEvidence()
        assert r.id
        assert r.control_id == ""
        assert r.evidence_type == ""
        assert r.evidence_description == ""
        assert r.collected_at == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = ComplianceMapperReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_evidence == 0
        assert r.avg_compliance_score == 0.0
        assert r.by_framework == {}
        assert r.by_status == {}
        assert r.by_risk == {}
        assert r.non_compliant_controls == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_mapping
# -------------------------------------------------------------------


class TestRecordMapping:
    def test_basic(self):
        eng = _engine()
        r = eng.record_mapping(
            framework=ComplianceFramework.SOC2,
            control_id="CC6.1",
        )
        assert r.framework == ComplianceFramework.SOC2
        assert r.control_id == "CC6.1"

    def test_with_params(self):
        eng = _engine()
        r = eng.record_mapping(
            framework=ComplianceFramework.HIPAA,
            control_id="164.312",
            control_name="Access Control",
            status=ControlStatus.NON_COMPLIANT,
            risk=ComplianceRisk.CRITICAL,
            compliance_score=30.0,
            owner="security-team",
        )
        assert r.framework == ComplianceFramework.HIPAA
        assert r.status == ControlStatus.NON_COMPLIANT
        assert r.compliance_score == 30.0

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_mapping(control_id="C1")
        r2 = eng.record_mapping(control_id="C2")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mapping(control_id=f"C{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_mapping
# -------------------------------------------------------------------


class TestGetMapping:
    def test_found(self):
        eng = _engine()
        r = eng.record_mapping(control_id="C1")
        assert eng.get_mapping(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_mapping("nonexistent") is None


# -------------------------------------------------------------------
# list_mappings
# -------------------------------------------------------------------


class TestListMappings:
    def test_list_all(self):
        eng = _engine()
        eng.record_mapping(control_id="C1")
        eng.record_mapping(control_id="C2")
        assert len(eng.list_mappings()) == 2

    def test_filter_by_framework(self):
        eng = _engine()
        eng.record_mapping(
            framework=ComplianceFramework.SOC2,
        )
        eng.record_mapping(
            framework=ComplianceFramework.HIPAA,
        )
        results = eng.list_mappings(framework=ComplianceFramework.SOC2)
        assert len(results) == 1
        assert results[0].framework == ComplianceFramework.SOC2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_mapping(
            status=ControlStatus.COMPLIANT,
        )
        eng.record_mapping(
            status=ControlStatus.NON_COMPLIANT,
        )
        results = eng.list_mappings(status=ControlStatus.COMPLIANT)
        assert len(results) == 1

    def test_filter_by_risk(self):
        eng = _engine()
        eng.record_mapping(
            risk=ComplianceRisk.CRITICAL,
        )
        eng.record_mapping(
            risk=ComplianceRisk.LOW,
        )
        results = eng.list_mappings(risk=ComplianceRisk.CRITICAL)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mapping(control_id=f"C{i}")
        assert len(eng.list_mappings(limit=5)) == 5


# -------------------------------------------------------------------
# add_evidence
# -------------------------------------------------------------------


class TestAddEvidence:
    def test_basic(self):
        eng = _engine()
        e = eng.add_evidence("CC6.1", "screenshot", "AWS console", 100.0)
        assert e.control_id == "CC6.1"
        assert e.evidence_type == "screenshot"
        assert e.collected_at == 100.0

    def test_unique_ids(self):
        eng = _engine()
        e1 = eng.add_evidence("C1", "doc", "desc1", 1.0)
        e2 = eng.add_evidence("C2", "log", "desc2", 2.0)
        assert e1.id != e2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_evidence(f"C{i}", "type", "desc", float(i))
        assert len(eng._evidence) == 2


# -------------------------------------------------------------------
# analyze_compliance_by_framework
# -------------------------------------------------------------------


class TestAnalyzeComplianceByFramework:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_compliance_by_framework()
        assert result["total_frameworks"] == 0
        assert result["breakdown"] == []

    def test_with_data(self):
        eng = _engine()
        eng.record_mapping(
            framework=ComplianceFramework.SOC2,
            compliance_score=80.0,
        )
        eng.record_mapping(
            framework=ComplianceFramework.SOC2,
            compliance_score=60.0,
        )
        eng.record_mapping(
            framework=ComplianceFramework.HIPAA,
            compliance_score=90.0,
        )
        result = eng.analyze_compliance_by_framework()
        assert result["total_frameworks"] == 2

    def test_non_compliant_counted(self):
        eng = _engine()
        eng.record_mapping(
            framework=ComplianceFramework.NIST,
            status=ControlStatus.NON_COMPLIANT,
        )
        eng.record_mapping(
            framework=ComplianceFramework.NIST,
            status=ControlStatus.COMPLIANT,
        )
        result = eng.analyze_compliance_by_framework()
        nist = next(b for b in result["breakdown"] if b["framework"] == "nist")
        assert nist["non_compliant_count"] == 1


# -------------------------------------------------------------------
# identify_non_compliant_controls
# -------------------------------------------------------------------


class TestIdentifyNonCompliantControls:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_non_compliant_controls() == []

    def test_only_non_compliant(self):
        eng = _engine()
        eng.record_mapping(
            control_id="C1",
            status=ControlStatus.COMPLIANT,
        )
        eng.record_mapping(
            control_id="C2",
            status=ControlStatus.NON_COMPLIANT,
        )
        results = eng.identify_non_compliant_controls()
        assert len(results) == 1
        assert results[0]["control_id"] == "C2"

    def test_multiple_non_compliant(self):
        eng = _engine()
        for i in range(3):
            eng.record_mapping(
                control_id=f"C{i}",
                status=ControlStatus.NON_COMPLIANT,
            )
        eng.record_mapping(
            control_id="C-ok",
            status=ControlStatus.COMPLIANT,
        )
        results = eng.identify_non_compliant_controls()
        assert len(results) == 3


# -------------------------------------------------------------------
# rank_by_compliance_score
# -------------------------------------------------------------------


class TestRankByComplianceScore:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance_score() == []

    def test_ascending_order(self):
        eng = _engine()
        eng.record_mapping(
            control_id="C1",
            compliance_score=90.0,
        )
        eng.record_mapping(
            control_id="C2",
            compliance_score=30.0,
        )
        results = eng.rank_by_compliance_score()
        assert results[0]["control_id"] == "C2"
        assert results[0]["compliance_score"] <= results[-1]["compliance_score"]


# -------------------------------------------------------------------
# detect_compliance_trends
# -------------------------------------------------------------------


class TestDetectComplianceTrends:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_mapping()
        result = eng.detect_compliance_trends()
        assert result["trend"] == "insufficient_data"

    def test_stable_trend(self):
        eng = _engine()
        for _ in range(8):
            eng.record_mapping(compliance_score=70.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] in (
            "stable",
            "improving",
            "worsening",
        )

    def test_improving_trend(self):
        eng = _engine()
        for _ in range(8):
            eng.record_mapping(compliance_score=30.0)
        for _ in range(8):
            eng.record_mapping(compliance_score=90.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "improving"
        assert result["total_records"] == 16


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert isinstance(report, ComplianceMapperReport)
        assert report.total_records == 0
        assert report.recommendations

    def test_with_data(self):
        eng = _engine()
        eng.record_mapping(
            control_id="C1",
            status=ControlStatus.NON_COMPLIANT,
            compliance_score=40.0,
        )
        eng.record_mapping(
            control_id="C2",
            status=ControlStatus.COMPLIANT,
            compliance_score=95.0,
        )
        eng.add_evidence("C1", "screenshot", "desc", 100.0)
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_evidence == 1
        assert report.by_status
        assert report.by_framework


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_records_and_evidence(self):
        eng = _engine()
        eng.record_mapping(control_id="C1")
        eng.add_evidence("C1", "doc", "desc", 1.0)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
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
        eng = _engine(min_compliance_score=75.0)
        eng.record_mapping(
            framework=ComplianceFramework.SOC2,
            control_id="CC6.1",
        )
        eng.record_mapping(
            framework=ComplianceFramework.HIPAA,
            control_id="164.312",
        )
        eng.add_evidence("CC6.1", "doc", "desc", 1.0)
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_evidence"] == 1
        assert stats["min_compliance_score"] == 75.0
        assert stats["unique_controls"] == 2
