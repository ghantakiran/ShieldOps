"""Tests for shieldops.compliance.audit_evidence_mapper — AuditEvidenceMapper."""

from __future__ import annotations

from shieldops.compliance.audit_evidence_mapper import (
    AuditEvidenceMapper,
    AuditEvidenceMapperReport,
    ControlFramework,
    EvidenceMappingRecord,
    EvidenceType,
    MappingGap,
    MappingStatus,
)


def _engine(**kw) -> AuditEvidenceMapper:
    return AuditEvidenceMapper(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_framework_soc2(self):
        assert ControlFramework.SOC2 == "soc2"

    def test_framework_hipaa(self):
        assert ControlFramework.HIPAA == "hipaa"

    def test_framework_pci_dss(self):
        assert ControlFramework.PCI_DSS == "pci_dss"

    def test_framework_iso27001(self):
        assert ControlFramework.ISO27001 == "iso27001"

    def test_framework_nist(self):
        assert ControlFramework.NIST == "nist"

    def test_status_fully_mapped(self):
        assert MappingStatus.FULLY_MAPPED == "fully_mapped"

    def test_status_partially_mapped(self):
        assert MappingStatus.PARTIALLY_MAPPED == "partially_mapped"

    def test_status_unmapped(self):
        assert MappingStatus.UNMAPPED == "unmapped"

    def test_status_stale(self):
        assert MappingStatus.STALE == "stale"

    def test_status_under_review(self):
        assert MappingStatus.UNDER_REVIEW == "under_review"

    def test_evidence_automated(self):
        assert EvidenceType.AUTOMATED == "automated"

    def test_evidence_manual(self):
        assert EvidenceType.MANUAL == "manual"

    def test_evidence_hybrid(self):
        assert EvidenceType.HYBRID == "hybrid"

    def test_evidence_attestation(self):
        assert EvidenceType.ATTESTATION == "attestation"

    def test_evidence_observation(self):
        assert EvidenceType.OBSERVATION == "observation"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_evidence_mapping_record_defaults(self):
        r = EvidenceMappingRecord()
        assert r.id
        assert r.control_id == ""
        assert r.control_framework == ControlFramework.SOC2
        assert r.mapping_status == MappingStatus.UNMAPPED
        assert r.evidence_type == EvidenceType.MANUAL
        assert r.mapping_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_mapping_gap_defaults(self):
        g = MappingGap()
        assert g.id
        assert g.control_id == ""
        assert g.control_framework == ControlFramework.SOC2
        assert g.gap_score == 0.0
        assert g.threshold == 0.0
        assert g.breached is False
        assert g.description == ""
        assert g.created_at > 0

    def test_report_defaults(self):
        r = AuditEvidenceMapperReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_gaps == 0
        assert r.unmapped_controls == 0
        assert r.avg_mapping_score == 0.0
        assert r.by_framework == {}
        assert r.by_status == {}
        assert r.by_evidence_type == {}
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
            control_id="CTL-001",
            control_framework=ControlFramework.SOC2,
            mapping_status=MappingStatus.FULLY_MAPPED,
            evidence_type=EvidenceType.AUTOMATED,
            mapping_score=95.0,
            service="api-gateway",
            team="compliance",
        )
        assert r.control_id == "CTL-001"
        assert r.control_framework == ControlFramework.SOC2
        assert r.mapping_status == MappingStatus.FULLY_MAPPED
        assert r.evidence_type == EvidenceType.AUTOMATED
        assert r.mapping_score == 95.0
        assert r.service == "api-gateway"
        assert r.team == "compliance"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mapping(control_id=f"CTL-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_mapping
# ---------------------------------------------------------------------------


class TestGetMapping:
    def test_found(self):
        eng = _engine()
        r = eng.record_mapping(
            control_id="CTL-001",
            mapping_score=95.0,
        )
        result = eng.get_mapping(r.id)
        assert result is not None
        assert result.mapping_score == 95.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_mapping("nonexistent") is None


# ---------------------------------------------------------------------------
# list_mappings
# ---------------------------------------------------------------------------


class TestListMappings:
    def test_list_all(self):
        eng = _engine()
        eng.record_mapping(control_id="CTL-001")
        eng.record_mapping(control_id="CTL-002")
        assert len(eng.list_mappings()) == 2

    def test_filter_by_framework(self):
        eng = _engine()
        eng.record_mapping(
            control_id="CTL-001",
            control_framework=ControlFramework.SOC2,
        )
        eng.record_mapping(
            control_id="CTL-002",
            control_framework=ControlFramework.HIPAA,
        )
        results = eng.list_mappings(framework=ControlFramework.SOC2)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_mapping(
            control_id="CTL-001",
            mapping_status=MappingStatus.FULLY_MAPPED,
        )
        eng.record_mapping(
            control_id="CTL-002",
            mapping_status=MappingStatus.UNMAPPED,
        )
        results = eng.list_mappings(status=MappingStatus.FULLY_MAPPED)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_mapping(control_id="CTL-001", service="api-gateway")
        eng.record_mapping(control_id="CTL-002", service="auth-svc")
        results = eng.list_mappings(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_mapping(control_id="CTL-001", team="compliance")
        eng.record_mapping(control_id="CTL-002", team="security")
        results = eng.list_mappings(team="compliance")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mapping(control_id=f"CTL-{i}")
        assert len(eng.list_mappings(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_gap
# ---------------------------------------------------------------------------


class TestAddGap:
    def test_basic(self):
        eng = _engine()
        g = eng.add_gap(
            control_id="CTL-001",
            control_framework=ControlFramework.HIPAA,
            gap_score=75.0,
            threshold=90.0,
            breached=True,
            description="Missing evidence for encryption",
        )
        assert g.control_id == "CTL-001"
        assert g.control_framework == ControlFramework.HIPAA
        assert g.gap_score == 75.0
        assert g.threshold == 90.0
        assert g.breached is True
        assert g.description == "Missing evidence for encryption"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_gap(control_id=f"CTL-{i}")
        assert len(eng._gaps) == 2


# ---------------------------------------------------------------------------
# analyze_mapping_coverage
# ---------------------------------------------------------------------------


class TestAnalyzeMappingCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.record_mapping(
            control_id="CTL-001",
            control_framework=ControlFramework.SOC2,
            mapping_score=80.0,
        )
        eng.record_mapping(
            control_id="CTL-002",
            control_framework=ControlFramework.SOC2,
            mapping_score=60.0,
        )
        result = eng.analyze_mapping_coverage()
        assert "soc2" in result
        assert result["soc2"]["count"] == 2
        assert result["soc2"]["avg_mapping_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_mapping_coverage() == {}


# ---------------------------------------------------------------------------
# identify_unmapped_controls
# ---------------------------------------------------------------------------


class TestIdentifyUnmappedControls:
    def test_detects_unmapped(self):
        eng = _engine()
        eng.record_mapping(
            control_id="CTL-001",
            mapping_status=MappingStatus.UNMAPPED,
        )
        eng.record_mapping(
            control_id="CTL-002",
            mapping_status=MappingStatus.FULLY_MAPPED,
        )
        results = eng.identify_unmapped_controls()
        assert len(results) == 1
        assert results[0]["control_id"] == "CTL-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unmapped_controls() == []


# ---------------------------------------------------------------------------
# rank_by_mapping_score
# ---------------------------------------------------------------------------


class TestRankByMappingScore:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_mapping(
            control_id="CTL-001",
            service="api-gateway",
            mapping_score=90.0,
        )
        eng.record_mapping(
            control_id="CTL-002",
            service="auth-svc",
            mapping_score=60.0,
        )
        results = eng.rank_by_mapping_score()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"
        assert results[0]["avg_mapping_score"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_mapping_score() == []


# ---------------------------------------------------------------------------
# detect_mapping_trends
# ---------------------------------------------------------------------------


class TestDetectMappingTrends:
    def test_stable(self):
        eng = _engine()
        for score in [50.0, 50.0, 50.0, 50.0]:
            eng.add_gap(control_id="CTL-001", gap_score=score)
        result = eng.detect_mapping_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for score in [30.0, 30.0, 80.0, 80.0]:
            eng.add_gap(control_id="CTL-001", gap_score=score)
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
            control_id="CTL-001",
            control_framework=ControlFramework.SOC2,
            mapping_status=MappingStatus.UNMAPPED,
            mapping_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AuditEvidenceMapperReport)
        assert report.total_records == 1
        assert report.unmapped_controls == 1
        assert len(report.top_unmapped) == 1
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
        eng.record_mapping(control_id="CTL-001")
        eng.add_gap(control_id="CTL-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._gaps) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_gaps"] == 0
        assert stats["framework_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_mapping(
            control_id="CTL-001",
            control_framework=ControlFramework.SOC2,
            service="api-gateway",
            team="compliance",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "soc2" in stats["framework_distribution"]
