"""Tests for shieldops.compliance.evidence_chain — ComplianceEvidenceChain."""

from __future__ import annotations

from shieldops.compliance.evidence_chain import (
    ChainStatus,
    ComplianceEvidenceChain,
    ComplianceFramework,
    EvidenceChain,
    EvidenceItem,
    EvidenceReport,
    EvidenceType,
)


def _engine(**kw) -> ComplianceEvidenceChain:
    return ComplianceEvidenceChain(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # EvidenceType (5 values)

    def test_evidence_type_log(self):
        assert EvidenceType.LOG == "log"

    def test_evidence_type_screenshot(self):
        assert EvidenceType.SCREENSHOT == "screenshot"

    def test_evidence_type_config_snapshot(self):
        assert EvidenceType.CONFIG_SNAPSHOT == "config_snapshot"

    def test_evidence_type_approval_record(self):
        assert EvidenceType.APPROVAL_RECORD == "approval_record"

    def test_evidence_type_scan_result(self):
        assert EvidenceType.SCAN_RESULT == "scan_result"

    # ChainStatus (5 values)

    def test_chain_status_valid(self):
        assert ChainStatus.VALID == "valid"

    def test_chain_status_broken(self):
        assert ChainStatus.BROKEN == "broken"

    def test_chain_status_pending_verification(self):
        assert ChainStatus.PENDING_VERIFICATION == "pending_verification"

    def test_chain_status_tampered(self):
        assert ChainStatus.TAMPERED == "tampered"

    def test_chain_status_expired(self):
        assert ChainStatus.EXPIRED == "expired"

    # ComplianceFramework (5 values)

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


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_evidence_item_defaults(self):
        item = EvidenceItem()
        assert item.id
        assert item.chain_id == ""
        assert item.evidence_type == EvidenceType.LOG
        assert item.framework == ComplianceFramework.SOC2
        assert item.description == ""
        assert item.content_hash == ""
        assert item.previous_hash == ""
        assert item.sequence_number == 0
        assert item.collector == ""
        assert item.verified is False
        assert item.created_at > 0

    def test_evidence_chain_defaults(self):
        chain = EvidenceChain()
        assert chain.id
        assert chain.framework == ComplianceFramework.SOC2
        assert chain.status == ChainStatus.PENDING_VERIFICATION
        assert chain.item_count == 0
        assert chain.first_item_at == 0.0
        assert chain.last_item_at == 0.0
        assert chain.is_intact is True
        assert chain.created_at > 0

    def test_evidence_report_defaults(self):
        report = EvidenceReport()
        assert report.total_chains == 0
        assert report.total_items == 0
        assert report.intact_chains == 0
        assert report.broken_chains == 0
        assert report.by_framework == {}
        assert report.by_type == {}
        assert report.by_status == {}
        assert report.recommendations == []
        assert report.generated_at > 0


# -------------------------------------------------------------------
# create_chain
# -------------------------------------------------------------------


class TestCreateChain:
    def test_basic_create(self):
        eng = _engine()
        chain = eng.create_chain()
        assert chain.id
        assert chain.framework == ComplianceFramework.SOC2
        assert len(eng.list_chains()) == 1

    def test_create_with_framework(self):
        eng = _engine()
        chain = eng.create_chain(
            framework=ComplianceFramework.HIPAA,
        )
        assert chain.framework == ComplianceFramework.HIPAA

    def test_unique_ids(self):
        eng = _engine()
        c1 = eng.create_chain()
        c2 = eng.create_chain()
        assert c1.id != c2.id

    def test_eviction_at_max_chains(self):
        eng = _engine(max_chains=3)
        ids = []
        for _ in range(4):
            chain = eng.create_chain()
            ids.append(chain.id)
        chains = eng.list_chains(limit=100)
        assert len(chains) == 3
        found = {c.id for c in chains}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_chain
# -------------------------------------------------------------------


class TestGetChain:
    def test_get_existing(self):
        eng = _engine()
        chain = eng.create_chain()
        found = eng.get_chain(chain.id)
        assert found is not None
        assert found.id == chain.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_chain("nonexistent") is None


# -------------------------------------------------------------------
# list_chains
# -------------------------------------------------------------------


class TestListChains:
    def test_list_all(self):
        eng = _engine()
        eng.create_chain()
        eng.create_chain()
        eng.create_chain()
        assert len(eng.list_chains()) == 3

    def test_filter_by_framework(self):
        eng = _engine()
        eng.create_chain(
            framework=ComplianceFramework.SOC2,
        )
        eng.create_chain(
            framework=ComplianceFramework.HIPAA,
        )
        eng.create_chain(
            framework=ComplianceFramework.SOC2,
        )
        results = eng.list_chains(
            framework=ComplianceFramework.SOC2,
        )
        assert len(results) == 2

    def test_filter_by_status(self):
        eng = _engine()
        c1 = eng.create_chain()
        eng.create_chain()
        # Add evidence to mark c1 as VALID
        eng.add_evidence(
            c1.id,
            EvidenceType.LOG,
            "test",
            "hash1",
        )
        results = eng.list_chains(
            status=ChainStatus.VALID,
        )
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _ in range(10):
            eng.create_chain()
        results = eng.list_chains(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# add_evidence
# -------------------------------------------------------------------


class TestAddEvidence:
    def test_basic_add(self):
        eng = _engine()
        chain = eng.create_chain()
        item = eng.add_evidence(
            chain.id,
            EvidenceType.LOG,
            "Server log snapshot",
            "abc123hash",
            collector="agent-1",
        )
        assert item is not None
        assert item.chain_id == chain.id
        assert item.evidence_type == EvidenceType.LOG
        assert item.content_hash == "abc123hash"
        assert item.sequence_number == 0
        assert item.previous_hash == ""
        assert item.verified is True

    def test_chain_linking(self):
        eng = _engine()
        chain = eng.create_chain()
        eng.add_evidence(
            chain.id,
            EvidenceType.LOG,
            "first",
            "hash1",
        )
        i2 = eng.add_evidence(
            chain.id,
            EvidenceType.SCREENSHOT,
            "second",
            "hash2",
        )
        assert i2 is not None
        assert i2.sequence_number == 1
        assert i2.previous_hash != ""

    def test_chain_not_found(self):
        eng = _engine()
        result = eng.add_evidence(
            "nonexistent",
            EvidenceType.LOG,
            "test",
            "hash",
        )
        assert result is None

    def test_chain_metadata_updated(self):
        eng = _engine()
        chain = eng.create_chain()
        eng.add_evidence(
            chain.id,
            EvidenceType.LOG,
            "test",
            "hash1",
        )
        updated = eng.get_chain(chain.id)
        assert updated is not None
        assert updated.item_count == 1
        assert updated.status == ChainStatus.VALID


# -------------------------------------------------------------------
# verify_chain_integrity
# -------------------------------------------------------------------


class TestVerifyChainIntegrity:
    def test_valid_chain(self):
        eng = _engine()
        chain = eng.create_chain()
        eng.add_evidence(
            chain.id,
            EvidenceType.LOG,
            "first",
            "hash1",
        )
        eng.add_evidence(
            chain.id,
            EvidenceType.SCREENSHOT,
            "second",
            "hash2",
        )
        result = eng.verify_chain_integrity(chain.id)
        assert result["valid"] is True
        assert result["item_count"] == 2

    def test_empty_chain(self):
        eng = _engine()
        chain = eng.create_chain()
        result = eng.verify_chain_integrity(chain.id)
        assert result["valid"] is True
        assert result["item_count"] == 0

    def test_chain_not_found(self):
        eng = _engine()
        result = eng.verify_chain_integrity("bad-id")
        assert result["valid"] is False
        assert result["error"] == "chain not found"


# -------------------------------------------------------------------
# detect_broken_chains
# -------------------------------------------------------------------


class TestDetectBrokenChains:
    def test_no_broken(self):
        eng = _engine()
        chain = eng.create_chain()
        eng.add_evidence(
            chain.id,
            EvidenceType.LOG,
            "test",
            "hash1",
        )
        broken = eng.detect_broken_chains()
        assert len(broken) == 0

    def test_empty(self):
        eng = _engine()
        assert eng.detect_broken_chains() == []


# -------------------------------------------------------------------
# calculate_coverage
# -------------------------------------------------------------------


class TestCalculateCoverage:
    def test_basic_coverage(self):
        eng = _engine()
        c1 = eng.create_chain(
            framework=ComplianceFramework.SOC2,
        )
        c2 = eng.create_chain(
            framework=ComplianceFramework.SOC2,
        )
        eng.add_evidence(
            c1.id,
            EvidenceType.LOG,
            "test",
            "hash1",
        )
        eng.add_evidence(
            c2.id,
            EvidenceType.SCREENSHOT,
            "test",
            "hash2",
        )
        coverage = eng.calculate_coverage(
            ComplianceFramework.SOC2,
        )
        assert coverage["framework"] == "soc2"
        assert coverage["total_chains"] == 2
        assert coverage["total_items"] == 2
        assert coverage["coverage_pct"] == 100.0

    def test_no_chains(self):
        eng = _engine()
        coverage = eng.calculate_coverage(
            ComplianceFramework.HIPAA,
        )
        assert coverage["total_chains"] == 0
        assert coverage["coverage_pct"] == 0.0


# -------------------------------------------------------------------
# export_chain
# -------------------------------------------------------------------


class TestExportChain:
    def test_basic_export(self):
        eng = _engine()
        chain = eng.create_chain()
        eng.add_evidence(
            chain.id,
            EvidenceType.LOG,
            "test",
            "hash1",
        )
        result = eng.export_chain(chain.id)
        assert result is not None
        assert "chain" in result
        assert "items" in result
        assert len(result["items"]) == 1
        assert "exported_at" in result

    def test_export_not_found(self):
        eng = _engine()
        assert eng.export_chain("nonexistent") is None


# -------------------------------------------------------------------
# generate_evidence_report
# -------------------------------------------------------------------


class TestGenerateEvidenceReport:
    def test_basic_report(self):
        eng = _engine()
        c1 = eng.create_chain(
            framework=ComplianceFramework.SOC2,
        )
        c2 = eng.create_chain(
            framework=ComplianceFramework.HIPAA,
        )
        eng.add_evidence(
            c1.id,
            EvidenceType.LOG,
            "test1",
            "hash1",
        )
        eng.add_evidence(
            c2.id,
            EvidenceType.SCAN_RESULT,
            "test2",
            "hash2",
        )
        report = eng.generate_evidence_report()
        assert report.total_chains == 2
        assert report.total_items == 2
        assert report.intact_chains == 2
        assert report.broken_chains == 0
        assert "soc2" in report.by_framework
        assert "hipaa" in report.by_framework
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_evidence_report()
        assert report.total_chains == 0
        assert report.total_items == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.create_chain()
        eng.create_chain()
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_chains()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_chains"] == 0
        assert stats["total_items"] == 0
        assert stats["max_chains"] == 50000
        assert stats["max_items_per_chain"] == 10000
        assert stats["framework_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        c1 = eng.create_chain(
            framework=ComplianceFramework.SOC2,
        )
        eng.create_chain(
            framework=ComplianceFramework.HIPAA,
        )
        eng.add_evidence(
            c1.id,
            EvidenceType.LOG,
            "test",
            "hash1",
        )
        stats = eng.get_stats()
        assert stats["total_chains"] == 2
        assert stats["total_items"] == 1
        assert "soc2" in stats["framework_distribution"]
        assert "hipaa" in stats["framework_distribution"]
