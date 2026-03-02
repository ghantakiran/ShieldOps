"""Tests for shieldops.compliance.compliance_control_mapper — ComplianceControlMapper."""

from __future__ import annotations

from shieldops.compliance.compliance_control_mapper import (
    ComplianceControlMapper,
    ComplianceControlReport,
    ComplianceFramework,
    ControlStatus,
    MappingAnalysis,
    MappingConfidence,
    MappingRecord,
)


def _engine(**kw) -> ComplianceControlMapper:
    return ComplianceControlMapper(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_framework_soc2(self):
        assert ComplianceFramework.SOC2 == "soc2"

    def test_framework_pci_dss(self):
        assert ComplianceFramework.PCI_DSS == "pci_dss"

    def test_framework_hipaa(self):
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_framework_iso_27001(self):
        assert ComplianceFramework.ISO_27001 == "iso_27001"

    def test_framework_gdpr(self):
        assert ComplianceFramework.GDPR == "gdpr"

    def test_status_implemented(self):
        assert ControlStatus.IMPLEMENTED == "implemented"

    def test_status_partially_implemented(self):
        assert ControlStatus.PARTIALLY_IMPLEMENTED == "partially_implemented"

    def test_status_planned(self):
        assert ControlStatus.PLANNED == "planned"

    def test_status_not_applicable(self):
        assert ControlStatus.NOT_APPLICABLE == "not_applicable"

    def test_status_gap(self):
        assert ControlStatus.GAP == "gap"

    def test_confidence_exact_match(self):
        assert MappingConfidence.EXACT_MATCH == "exact_match"

    def test_confidence_strong_match(self):
        assert MappingConfidence.STRONG_MATCH == "strong_match"

    def test_confidence_partial_match(self):
        assert MappingConfidence.PARTIAL_MATCH == "partial_match"

    def test_confidence_weak_match(self):
        assert MappingConfidence.WEAK_MATCH == "weak_match"

    def test_confidence_unmapped(self):
        assert MappingConfidence.UNMAPPED == "unmapped"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_mapping_record_defaults(self):
        r = MappingRecord()
        assert r.id
        assert r.control_name == ""
        assert r.compliance_framework == ComplianceFramework.SOC2
        assert r.control_status == ControlStatus.IMPLEMENTED
        assert r.mapping_confidence == MappingConfidence.EXACT_MATCH
        assert r.coverage_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_mapping_analysis_defaults(self):
        a = MappingAnalysis()
        assert a.id
        assert a.control_name == ""
        assert a.compliance_framework == ComplianceFramework.SOC2
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_compliance_control_report_defaults(self):
        r = ComplianceControlReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_coverage_score == 0.0
        assert r.by_framework == {}
        assert r.by_status == {}
        assert r.by_confidence == {}
        assert r.top_gaps == []
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
            control_name="CC6.1",
            compliance_framework=ComplianceFramework.SOC2,
            control_status=ControlStatus.IMPLEMENTED,
            mapping_confidence=MappingConfidence.EXACT_MATCH,
            coverage_score=95.0,
            service="api-gateway",
            team="sre",
        )
        assert r.control_name == "CC6.1"
        assert r.compliance_framework == ComplianceFramework.SOC2
        assert r.control_status == ControlStatus.IMPLEMENTED
        assert r.mapping_confidence == MappingConfidence.EXACT_MATCH
        assert r.coverage_score == 95.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mapping(control_name=f"CTL-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_mapping
# ---------------------------------------------------------------------------


class TestGetMapping:
    def test_found(self):
        eng = _engine()
        r = eng.record_mapping(
            control_name="CC6.1",
            compliance_framework=ComplianceFramework.PCI_DSS,
        )
        result = eng.get_mapping(r.id)
        assert result is not None
        assert result.compliance_framework == ComplianceFramework.PCI_DSS

    def test_not_found(self):
        eng = _engine()
        assert eng.get_mapping("nonexistent") is None


# ---------------------------------------------------------------------------
# list_mappings
# ---------------------------------------------------------------------------


class TestListMappings:
    def test_list_all(self):
        eng = _engine()
        eng.record_mapping(control_name="CTL-001")
        eng.record_mapping(control_name="CTL-002")
        assert len(eng.list_mappings()) == 2

    def test_filter_by_framework(self):
        eng = _engine()
        eng.record_mapping(
            control_name="CTL-001",
            compliance_framework=ComplianceFramework.SOC2,
        )
        eng.record_mapping(
            control_name="CTL-002",
            compliance_framework=ComplianceFramework.HIPAA,
        )
        results = eng.list_mappings(compliance_framework=ComplianceFramework.SOC2)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_mapping(
            control_name="CTL-001",
            control_status=ControlStatus.IMPLEMENTED,
        )
        eng.record_mapping(
            control_name="CTL-002",
            control_status=ControlStatus.GAP,
        )
        results = eng.list_mappings(control_status=ControlStatus.IMPLEMENTED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_mapping(control_name="CTL-001", team="sre")
        eng.record_mapping(control_name="CTL-002", team="platform")
        results = eng.list_mappings(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mapping(control_name=f"CTL-{i}")
        assert len(eng.list_mappings(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            control_name="CC6.1",
            compliance_framework=ComplianceFramework.PCI_DSS,
            analysis_score=72.0,
            threshold=70.0,
            breached=True,
            description="Coverage below target",
        )
        assert a.control_name == "CC6.1"
        assert a.compliance_framework == ComplianceFramework.PCI_DSS
        assert a.analysis_score == 72.0
        assert a.threshold == 70.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(control_name=f"CTL-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_mapping_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeMappingDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_mapping(
            control_name="CTL-001",
            compliance_framework=ComplianceFramework.SOC2,
            coverage_score=80.0,
        )
        eng.record_mapping(
            control_name="CTL-002",
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
# identify_coverage_gaps
# ---------------------------------------------------------------------------


class TestIdentifyCoverageGaps:
    def test_detects_gaps(self):
        eng = _engine(coverage_gap_threshold=15.0)
        eng.record_mapping(
            control_name="CTL-001",
            coverage_score=10.0,
        )
        eng.record_mapping(
            control_name="CTL-002",
            coverage_score=80.0,
        )
        results = eng.identify_coverage_gaps()
        assert len(results) == 1
        assert results[0]["control_name"] == "CTL-001"

    def test_sorted_ascending(self):
        eng = _engine(coverage_gap_threshold=15.0)
        eng.record_mapping(control_name="CTL-001", coverage_score=10.0)
        eng.record_mapping(control_name="CTL-002", coverage_score=5.0)
        results = eng.identify_coverage_gaps()
        assert len(results) == 2
        assert results[0]["coverage_score"] == 5.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_coverage_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_coverage
# ---------------------------------------------------------------------------


class TestRankByCoverage:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_mapping(control_name="CTL-001", coverage_score=90.0, service="svc-a")
        eng.record_mapping(control_name="CTL-002", coverage_score=50.0, service="svc-b")
        results = eng.rank_by_coverage()
        assert len(results) == 2
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_coverage_score"] == 50.0

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
            eng.add_analysis(control_name="CTL-001", analysis_score=70.0)
        result = eng.detect_mapping_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(control_name="CTL-001", analysis_score=50.0)
        eng.add_analysis(control_name="CTL-002", analysis_score=50.0)
        eng.add_analysis(control_name="CTL-003", analysis_score=80.0)
        eng.add_analysis(control_name="CTL-004", analysis_score=80.0)
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
        eng = _engine(coverage_gap_threshold=15.0)
        eng.record_mapping(
            control_name="CC6.1",
            compliance_framework=ComplianceFramework.SOC2,
            control_status=ControlStatus.GAP,
            coverage_score=10.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ComplianceControlReport)
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
        eng.record_mapping(control_name="CTL-001")
        eng.add_analysis(control_name="CTL-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["framework_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_mapping(
            control_name="CTL-001",
            compliance_framework=ComplianceFramework.SOC2,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "soc2" in stats["framework_distribution"]
