"""Tests for shieldops.compliance.evidence_collector — ComplianceEvidenceCollector."""

from __future__ import annotations

import pytest

from shieldops.compliance.evidence_collector import (
    AuditPackage,
    ComplianceEvidenceCollector,
    EvidenceItem,
    EvidenceType,
    FrameworkType,
)


def _collector(**kw) -> ComplianceEvidenceCollector:
    return ComplianceEvidenceCollector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # EvidenceType (6 values)

    def test_type_screenshot(self):
        assert EvidenceType.SCREENSHOT == "screenshot"

    def test_type_log_export(self):
        assert EvidenceType.LOG_EXPORT == "log_export"

    def test_type_configuration(self):
        assert EvidenceType.CONFIGURATION == "configuration"

    def test_type_policy_document(self):
        assert EvidenceType.POLICY_DOCUMENT == "policy_document"

    def test_type_test_result(self):
        assert EvidenceType.TEST_RESULT == "test_result"

    def test_type_approval_record(self):
        assert EvidenceType.APPROVAL_RECORD == "approval_record"

    # FrameworkType (6 values)

    def test_framework_soc2(self):
        assert FrameworkType.SOC2 == "soc2"

    def test_framework_iso27001(self):
        assert FrameworkType.ISO27001 == "iso27001"

    def test_framework_hipaa(self):
        assert FrameworkType.HIPAA == "hipaa"

    def test_framework_pci_dss(self):
        assert FrameworkType.PCI_DSS == "pci_dss"

    def test_framework_gdpr(self):
        assert FrameworkType.GDPR == "gdpr"

    def test_framework_nist(self):
        assert FrameworkType.NIST == "nist"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_evidence_item_defaults(self):
        item = EvidenceItem(
            title="TLS config",
            evidence_type=EvidenceType.CONFIGURATION,
            framework=FrameworkType.SOC2,
        )
        assert item.id
        assert item.control_id == ""
        assert item.description == ""
        assert item.source_system == ""
        assert item.file_path == ""
        assert item.hash_value == ""
        assert item.collected_by == ""
        assert item.valid_from is None
        assert item.valid_until is None
        assert item.metadata == {}
        assert item.collected_at > 0

    def test_audit_package_defaults(self):
        pkg = AuditPackage(name="Q1 Audit", framework=FrameworkType.SOC2)
        assert pkg.id
        assert pkg.evidence_ids == []
        assert pkg.status == "draft"
        assert pkg.reviewer == ""
        assert pkg.review_notes == ""
        assert pkg.created_at > 0
        assert pkg.finalized_at is None


# ---------------------------------------------------------------------------
# collect_evidence
# ---------------------------------------------------------------------------


class TestCollectEvidence:
    def test_basic(self):
        c = _collector()
        item = c.collect_evidence(
            title="Access logs",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
        )
        assert item.title == "Access logs"
        assert item.evidence_type == EvidenceType.LOG_EXPORT
        assert item.framework == FrameworkType.SOC2

    def test_all_fields(self):
        c = _collector()
        item = c.collect_evidence(
            title="Encryption config",
            evidence_type=EvidenceType.CONFIGURATION,
            framework=FrameworkType.ISO27001,
            control_id="A.10.1",
            description="At-rest encryption settings",
            source_system="aws",
            file_path="/evidence/enc.json",
            hash_value="abc123",
            collected_by="admin",
        )
        assert item.control_id == "A.10.1"
        assert item.description == "At-rest encryption settings"
        assert item.source_system == "aws"
        assert item.file_path == "/evidence/enc.json"
        assert item.hash_value == "abc123"
        assert item.collected_by == "admin"

    def test_max_limit(self):
        c = _collector(max_evidence=2)
        c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
        )
        c.collect_evidence(
            title="e2",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
        )
        with pytest.raises(ValueError, match="Maximum evidence items"):
            c.collect_evidence(
                title="e3",
                evidence_type=EvidenceType.LOG_EXPORT,
                framework=FrameworkType.SOC2,
            )


# ---------------------------------------------------------------------------
# get_evidence
# ---------------------------------------------------------------------------


class TestGetEvidence:
    def test_found(self):
        c = _collector()
        item = c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
        )
        assert c.get_evidence(item.id) is not None

    def test_not_found(self):
        c = _collector()
        assert c.get_evidence("nonexistent") is None


# ---------------------------------------------------------------------------
# list_evidence
# ---------------------------------------------------------------------------


class TestListEvidence:
    def test_all(self):
        c = _collector()
        c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
        )
        c.collect_evidence(
            title="e2",
            evidence_type=EvidenceType.SCREENSHOT,
            framework=FrameworkType.HIPAA,
        )
        assert len(c.list_evidence()) == 2

    def test_by_framework(self):
        c = _collector()
        c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
        )
        c.collect_evidence(
            title="e2",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.HIPAA,
        )
        result = c.list_evidence(framework=FrameworkType.SOC2)
        assert len(result) == 1
        assert result[0].framework == FrameworkType.SOC2

    def test_by_type(self):
        c = _collector()
        c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
        )
        c.collect_evidence(
            title="e2",
            evidence_type=EvidenceType.SCREENSHOT,
            framework=FrameworkType.SOC2,
        )
        result = c.list_evidence(evidence_type=EvidenceType.SCREENSHOT)
        assert len(result) == 1
        assert result[0].evidence_type == EvidenceType.SCREENSHOT

    def test_by_control_id(self):
        c = _collector()
        c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
            control_id="CC6.1",
        )
        c.collect_evidence(
            title="e2",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
            control_id="CC7.2",
        )
        result = c.list_evidence(control_id="CC6.1")
        assert len(result) == 1
        assert result[0].control_id == "CC6.1"


# ---------------------------------------------------------------------------
# delete_evidence
# ---------------------------------------------------------------------------


class TestDeleteEvidence:
    def test_existing(self):
        c = _collector()
        item = c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
        )
        assert c.delete_evidence(item.id) is True
        assert c.get_evidence(item.id) is None

    def test_nonexistent(self):
        c = _collector()
        assert c.delete_evidence("nonexistent") is False


# ---------------------------------------------------------------------------
# create_package
# ---------------------------------------------------------------------------


class TestCreatePackage:
    def test_basic(self):
        c = _collector()
        pkg = c.create_package(name="Q1 SOC2", framework=FrameworkType.SOC2)
        assert pkg.name == "Q1 SOC2"
        assert pkg.framework == FrameworkType.SOC2
        assert pkg.status == "draft"

    def test_all_fields(self):
        c = _collector()
        item = c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
        )
        pkg = c.create_package(
            name="Q1 SOC2",
            framework=FrameworkType.SOC2,
            evidence_ids=[item.id],
        )
        assert item.id in pkg.evidence_ids

    def test_max_limit(self):
        c = _collector(max_packages=2)
        c.create_package(name="p1", framework=FrameworkType.SOC2)
        c.create_package(name="p2", framework=FrameworkType.SOC2)
        with pytest.raises(ValueError, match="Maximum packages"):
            c.create_package(name="p3", framework=FrameworkType.SOC2)


# ---------------------------------------------------------------------------
# add_to_package
# ---------------------------------------------------------------------------


class TestAddToPackage:
    def test_basic(self):
        c = _collector()
        item = c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
        )
        pkg = c.create_package(name="p1", framework=FrameworkType.SOC2)
        result = c.add_to_package(pkg.id, item.id)
        assert result is not None
        assert item.id in result.evidence_ids

    def test_not_found_package(self):
        c = _collector()
        assert c.add_to_package("nonexistent", "some-evidence") is None

    def test_duplicate_evidence_not_added_twice(self):
        c = _collector()
        item = c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
        )
        pkg = c.create_package(name="p1", framework=FrameworkType.SOC2)
        c.add_to_package(pkg.id, item.id)
        c.add_to_package(pkg.id, item.id)
        result = c.get_package(pkg.id)
        assert result.evidence_ids.count(item.id) == 1


# ---------------------------------------------------------------------------
# finalize_package
# ---------------------------------------------------------------------------


class TestFinalizePackage:
    def test_basic(self):
        c = _collector()
        pkg = c.create_package(name="p1", framework=FrameworkType.SOC2)
        result = c.finalize_package(
            pkg.id,
            reviewer="auditor@co.com",
            notes="Looks good",
        )
        assert result is not None
        assert result.status == "finalized"
        assert result.reviewer == "auditor@co.com"
        assert result.review_notes == "Looks good"
        assert result.finalized_at is not None

    def test_not_found(self):
        c = _collector()
        assert c.finalize_package("nonexistent", reviewer="x") is None


# ---------------------------------------------------------------------------
# get_package
# ---------------------------------------------------------------------------


class TestGetPackage:
    def test_found(self):
        c = _collector()
        pkg = c.create_package(name="p1", framework=FrameworkType.SOC2)
        assert c.get_package(pkg.id) is not None

    def test_not_found(self):
        c = _collector()
        assert c.get_package("nonexistent") is None


# ---------------------------------------------------------------------------
# list_packages
# ---------------------------------------------------------------------------


class TestListPackages:
    def test_all(self):
        c = _collector()
        c.create_package(name="p1", framework=FrameworkType.SOC2)
        c.create_package(name="p2", framework=FrameworkType.HIPAA)
        assert len(c.list_packages()) == 2

    def test_by_framework(self):
        c = _collector()
        c.create_package(name="p1", framework=FrameworkType.SOC2)
        c.create_package(name="p2", framework=FrameworkType.HIPAA)
        result = c.list_packages(framework=FrameworkType.SOC2)
        assert len(result) == 1
        assert result[0].framework == FrameworkType.SOC2

    def test_by_status(self):
        c = _collector()
        pkg = c.create_package(name="p1", framework=FrameworkType.SOC2)
        c.create_package(name="p2", framework=FrameworkType.SOC2)
        c.finalize_package(pkg.id, reviewer="x")
        drafts = c.list_packages(status="draft")
        finalized = c.list_packages(status="finalized")
        assert len(drafts) == 1
        assert len(finalized) == 1


# ---------------------------------------------------------------------------
# get_coverage
# ---------------------------------------------------------------------------


class TestGetCoverage:
    def test_returns_coverage_by_control(self):
        c = _collector()
        c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
            control_id="CC6.1",
        )
        c.collect_evidence(
            title="e2",
            evidence_type=EvidenceType.CONFIGURATION,
            framework=FrameworkType.SOC2,
            control_id="CC7.2",
        )
        coverage = c.get_coverage(FrameworkType.SOC2)
        assert coverage["total_controls"] == 2
        assert coverage["covered_controls"] == 2
        assert coverage["coverage_pct"] == 100.0
        assert coverage["uncovered_controls"] == []


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        c = _collector()
        stats = c.get_stats()
        assert stats["total_evidence"] == 0
        assert stats["total_packages"] == 0
        assert stats["finalized_packages"] == 0
        assert stats["framework_distribution"] == {}
        assert stats["evidence_type_distribution"] == {}
        assert stats["coverage_by_framework"] == {}

    def test_populated(self):
        c = _collector()
        c.collect_evidence(
            title="e1",
            evidence_type=EvidenceType.LOG_EXPORT,
            framework=FrameworkType.SOC2,
            control_id="CC6.1",
        )
        c.collect_evidence(
            title="e2",
            evidence_type=EvidenceType.SCREENSHOT,
            framework=FrameworkType.SOC2,
            control_id="CC7.2",
        )
        pkg = c.create_package(name="p1", framework=FrameworkType.SOC2)
        c.finalize_package(pkg.id, reviewer="auditor")
        stats = c.get_stats()
        assert stats["total_evidence"] == 2
        assert stats["total_packages"] == 1
        assert stats["finalized_packages"] == 1
        assert FrameworkType.SOC2 in stats["framework_distribution"]
        assert stats["framework_distribution"][FrameworkType.SOC2] == 2
        assert EvidenceType.LOG_EXPORT in stats["evidence_type_distribution"]
        assert "soc2" in stats["coverage_by_framework"]
