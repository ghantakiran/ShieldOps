"""Tests for shieldops.security.compliance_bridge — SecurityComplianceBridge."""

from __future__ import annotations

from shieldops.security.compliance_bridge import (
    BridgeRecord,
    BridgeStatus,
    ComplianceBridgeReport,
    FrameworkMapping,
    MappingConfidence,
    SecurityComplianceBridge,
    SecurityFramework,
)


def _engine(**kw) -> SecurityComplianceBridge:
    return SecurityComplianceBridge(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # BridgeStatus (5)
    def test_status_aligned(self):
        assert BridgeStatus.ALIGNED == "aligned"

    def test_status_partial_alignment(self):
        assert BridgeStatus.PARTIAL_ALIGNMENT == "partial_alignment"

    def test_status_misaligned(self):
        assert BridgeStatus.MISALIGNED == "misaligned"

    def test_status_gap_detected(self):
        assert BridgeStatus.GAP_DETECTED == "gap_detected"

    def test_status_not_assessed(self):
        assert BridgeStatus.NOT_ASSESSED == "not_assessed"

    # SecurityFramework (5)
    def test_framework_nist(self):
        assert SecurityFramework.NIST == "nist"

    def test_framework_cis(self):
        assert SecurityFramework.CIS == "cis"

    def test_framework_iso27001(self):
        assert SecurityFramework.ISO27001 == "iso27001"

    def test_framework_soc2(self):
        assert SecurityFramework.SOC2 == "soc2"

    def test_framework_pci_dss(self):
        assert SecurityFramework.PCI_DSS == "pci_dss"

    # MappingConfidence (5)
    def test_confidence_exact(self):
        assert MappingConfidence.EXACT == "exact"

    def test_confidence_high(self):
        assert MappingConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert MappingConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert MappingConfidence.LOW == "low"

    def test_confidence_unmapped(self):
        assert MappingConfidence.UNMAPPED == "unmapped"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_bridge_record_defaults(self):
        r = BridgeRecord()
        assert r.id
        assert r.control_id == ""
        assert r.control_name == ""
        assert r.framework == SecurityFramework.NIST
        assert r.bridge_status == BridgeStatus.NOT_ASSESSED
        assert r.alignment_score_pct == 0.0
        assert r.gap_description == ""
        assert r.created_at > 0

    def test_framework_mapping_defaults(self):
        m = FrameworkMapping()
        assert m.id
        assert m.source_framework == SecurityFramework.NIST
        assert m.target_framework == SecurityFramework.CIS
        assert m.source_control_id == ""
        assert m.target_control_id == ""
        assert m.mapping_confidence == MappingConfidence.MODERATE
        assert m.notes == ""
        assert m.created_at > 0

    def test_compliance_bridge_report_defaults(self):
        r = ComplianceBridgeReport()
        assert r.id
        assert r.total_bridges == 0
        assert r.total_mappings == 0
        assert r.avg_alignment_score_pct == 0.0
        assert r.by_framework == {}
        assert r.by_status == {}
        assert r.gap_count == 0
        assert r.aligned_count == 0
        assert r.recommendations == []
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_bridge
# -------------------------------------------------------------------


class TestRecordBridge:
    def test_basic(self):
        eng = _engine()
        r = eng.record_bridge("NIST-AC-1", framework=SecurityFramework.NIST)
        assert r.control_id == "NIST-AC-1"
        assert r.framework == SecurityFramework.NIST

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_bridge(
            "CIS-1.1",
            control_name="Inventory of Hardware Assets",
            framework=SecurityFramework.CIS,
            bridge_status=BridgeStatus.ALIGNED,
            alignment_score_pct=95.0,
            gap_description="",
        )
        assert r.framework == SecurityFramework.CIS
        assert r.bridge_status == BridgeStatus.ALIGNED
        assert r.alignment_score_pct == 95.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_bridge(f"ctrl-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_bridge
# -------------------------------------------------------------------


class TestGetBridge:
    def test_found(self):
        eng = _engine()
        r = eng.record_bridge("NIST-AC-1")
        assert eng.get_bridge(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_bridge("nonexistent") is None


# -------------------------------------------------------------------
# list_bridges
# -------------------------------------------------------------------


class TestListBridges:
    def test_list_all(self):
        eng = _engine()
        eng.record_bridge("ctrl-a")
        eng.record_bridge("ctrl-b")
        assert len(eng.list_bridges()) == 2

    def test_filter_by_framework(self):
        eng = _engine()
        eng.record_bridge("ctrl-a", framework=SecurityFramework.NIST)
        eng.record_bridge("ctrl-b", framework=SecurityFramework.CIS)
        results = eng.list_bridges(framework=SecurityFramework.CIS)
        assert len(results) == 1
        assert results[0].control_id == "ctrl-b"

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_bridge("ctrl-a", bridge_status=BridgeStatus.ALIGNED)
        eng.record_bridge("ctrl-b", bridge_status=BridgeStatus.MISALIGNED)
        results = eng.list_bridges(bridge_status=BridgeStatus.MISALIGNED)
        assert len(results) == 1
        assert results[0].control_id == "ctrl-b"


# -------------------------------------------------------------------
# add_mapping
# -------------------------------------------------------------------


class TestAddMapping:
    def test_basic(self):
        eng = _engine()
        m = eng.add_mapping(
            source_framework=SecurityFramework.NIST,
            target_framework=SecurityFramework.SOC2,
            source_control_id="AC-1",
            target_control_id="CC6.1",
            mapping_confidence=MappingConfidence.HIGH,
            notes="Direct control mapping",
        )
        assert m.source_framework == SecurityFramework.NIST
        assert m.target_framework == SecurityFramework.SOC2
        assert m.mapping_confidence == MappingConfidence.HIGH

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_mapping(source_control_id=f"ctrl-{i}")
        assert len(eng._mappings) == 2


# -------------------------------------------------------------------
# analyze_alignment_by_framework
# -------------------------------------------------------------------


class TestAnalyzeAlignmentByFramework:
    def test_with_data(self):
        eng = _engine(min_alignment_pct=80.0)
        eng.record_bridge("ctrl-a", framework=SecurityFramework.NIST, alignment_score_pct=90.0)
        eng.record_bridge("ctrl-b", framework=SecurityFramework.NIST, alignment_score_pct=70.0)
        result = eng.analyze_alignment_by_framework(SecurityFramework.NIST)
        assert result["record_count"] == 2
        assert result["avg_alignment_score_pct"] == 80.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_alignment_by_framework(SecurityFramework.PCI_DSS)
        assert result["status"] == "no_data"

    def test_below_threshold(self):
        eng = _engine(min_alignment_pct=80.0)
        eng.record_bridge("ctrl-a", framework=SecurityFramework.CIS, alignment_score_pct=60.0)
        result = eng.analyze_alignment_by_framework(SecurityFramework.CIS)
        assert result["meets_threshold"] is False


# -------------------------------------------------------------------
# identify_security_gaps
# -------------------------------------------------------------------


class TestIdentifySecurityGaps:
    def test_with_gaps(self):
        eng = _engine()
        eng.record_bridge(
            "ctrl-a",
            bridge_status=BridgeStatus.GAP_DETECTED,
            alignment_score_pct=40.0,
            gap_description="Missing encryption control",
        )
        eng.record_bridge("ctrl-b", bridge_status=BridgeStatus.ALIGNED, alignment_score_pct=95.0)
        results = eng.identify_security_gaps()
        assert len(results) == 1
        assert results[0]["control_id"] == "ctrl-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_security_gaps() == []

    def test_misaligned_included(self):
        eng = _engine()
        eng.record_bridge("ctrl-a", bridge_status=BridgeStatus.MISALIGNED)
        results = eng.identify_security_gaps()
        assert len(results) == 1


# -------------------------------------------------------------------
# rank_by_alignment_score
# -------------------------------------------------------------------


class TestRankByAlignmentScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_bridge("ctrl-a", alignment_score_pct=40.0)
        eng.record_bridge("ctrl-b", alignment_score_pct=90.0)
        results = eng.rank_by_alignment_score()
        assert results[0]["control_id"] == "ctrl-b"
        assert results[0]["alignment_score_pct"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_alignment_score() == []


# -------------------------------------------------------------------
# detect_alignment_drift
# -------------------------------------------------------------------


class TestDetectAlignmentDrift:
    def test_with_drift(self):
        eng = _engine(min_alignment_pct=80.0)
        eng.record_bridge("ctrl-a", framework=SecurityFramework.NIST, alignment_score_pct=50.0)
        eng.record_bridge("ctrl-b", framework=SecurityFramework.CIS, alignment_score_pct=90.0)
        results = eng.detect_alignment_drift()
        assert len(results) == 1
        assert results[0]["framework"] == "nist"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_alignment_drift() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_bridge("ctrl-a", bridge_status=BridgeStatus.ALIGNED, alignment_score_pct=90.0)
        eng.record_bridge(
            "ctrl-b", bridge_status=BridgeStatus.GAP_DETECTED, alignment_score_pct=30.0
        )
        eng.add_mapping()
        report = eng.generate_report()
        assert report.total_bridges == 2
        assert report.total_mappings == 1
        assert report.gap_count == 1
        assert report.aligned_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_bridges == 0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_bridge("ctrl-a")
        eng.add_mapping()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._mappings) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_bridges"] == 0
        assert stats["total_mappings"] == 0
        assert stats["framework_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_alignment_pct=85.0)
        eng.record_bridge("ctrl-a", framework=SecurityFramework.NIST)
        eng.record_bridge("ctrl-b", framework=SecurityFramework.CIS)
        eng.add_mapping()
        stats = eng.get_stats()
        assert stats["total_bridges"] == 2
        assert stats["total_mappings"] == 1
        assert stats["unique_controls"] == 2
        assert stats["min_alignment_pct"] == 85.0
