"""Tests for AutomatedEvidenceCollector."""

from __future__ import annotations

from shieldops.compliance.automated_evidence_collector import (
    AutomatedEvidenceCollector,
    CollectionStatus,
    ControlFramework,
    EvidenceItem,
    EvidenceReport,
    EvidenceRequirement,
    EvidenceType,
)


def _engine(**kw) -> AutomatedEvidenceCollector:
    return AutomatedEvidenceCollector(**kw)


# --- Enum tests ---


class TestEnums:
    def test_type_log(self):
        assert EvidenceType.LOG == "log"

    def test_type_screenshot(self):
        assert EvidenceType.SCREENSHOT == "screenshot"

    def test_type_config(self):
        assert EvidenceType.CONFIG_SNAPSHOT == "config_snapshot"

    def test_type_scan(self):
        assert EvidenceType.SCAN_REPORT == "scan_report"

    def test_type_audit(self):
        assert EvidenceType.AUDIT_TRAIL == "audit_trail"

    def test_type_policy(self):
        assert EvidenceType.POLICY_DOCUMENT == "policy_document"

    def test_status_pending(self):
        assert CollectionStatus.PENDING == "pending"

    def test_status_collected(self):
        assert CollectionStatus.COLLECTED == "collected"

    def test_status_validated(self):
        assert CollectionStatus.VALIDATED == "validated"

    def test_status_expired(self):
        assert CollectionStatus.EXPIRED == "expired"

    def test_framework_soc2(self):
        assert ControlFramework.SOC2 == "soc2"

    def test_framework_hipaa(self):
        assert ControlFramework.HIPAA == "hipaa"

    def test_framework_pci(self):
        assert ControlFramework.PCI_DSS == "pci_dss"

    def test_framework_gdpr(self):
        assert ControlFramework.GDPR == "gdpr"


# --- Model tests ---


class TestModels:
    def test_requirement_defaults(self):
        r = EvidenceRequirement()
        assert r.id
        assert r.control_id == ""
        assert r.required is True

    def test_item_defaults(self):
        i = EvidenceItem()
        assert i.id
        assert i.status == CollectionStatus.PENDING
        assert i.valid is False

    def test_report_defaults(self):
        r = EvidenceReport()
        assert r.total_requirements == 0
        assert r.by_type == {}


# --- identify_evidence_requirements ---


class TestIdentifyRequirements:
    def test_basic(self):
        eng = _engine()
        r = eng.identify_evidence_requirements(
            control_id="CC6.1",
            framework=ControlFramework.SOC2,
            evidence_type=EvidenceType.LOG,
            description="System access logs",
        )
        assert r.control_id == "CC6.1"
        assert r.framework == ControlFramework.SOC2

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.identify_evidence_requirements(control_id=f"C-{i}")
        assert len(eng._requirements) == 3


# --- collect_evidence ---


class TestCollectEvidence:
    def test_basic(self):
        eng = _engine()
        r = eng.identify_evidence_requirements(control_id="C1")
        item = eng.collect_evidence(
            requirement_id=r.id,
            evidence_type=EvidenceType.LOG,
            content_hash="sha256:abc",
            source="cloudtrail",
            team="sec",
        )
        assert item.requirement_id == r.id
        assert item.status == CollectionStatus.COLLECTED

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.collect_evidence(requirement_id=f"r-{i}")
        assert len(eng._items) == 2


# --- validate_evidence ---


class TestValidateEvidence:
    def test_valid(self):
        eng = _engine()
        r = eng.identify_evidence_requirements(control_id="C1")
        item = eng.collect_evidence(r.id, content_hash="abc")
        result = eng.validate_evidence(item.id)
        assert result["valid"] is True
        assert item.status == CollectionStatus.VALIDATED

    def test_invalid_no_hash(self):
        eng = _engine()
        r = eng.identify_evidence_requirements(control_id="C1")
        item = eng.collect_evidence(r.id, content_hash="")
        result = eng.validate_evidence(item.id)
        assert result["valid"] is False

    def test_not_found(self):
        eng = _engine()
        result = eng.validate_evidence("unknown")
        assert result["valid"] is False
        assert result["reason"] == "not_found"


# --- store_evidence ---


class TestStoreEvidence:
    def test_success(self):
        eng = _engine()
        item = eng.collect_evidence(requirement_id="r1")
        result = eng.store_evidence(item.id, "sha256:xyz")
        assert result["stored"] is True
        assert item.content_hash == "sha256:xyz"

    def test_not_found(self):
        eng = _engine()
        result = eng.store_evidence("unknown", "hash")
        assert result["stored"] is False


# --- get_evidence_status ---


class TestEvidenceStatus:
    def test_with_data(self):
        eng = _engine()
        r = eng.identify_evidence_requirements(control_id="C1")
        item = eng.collect_evidence(r.id, content_hash="abc")
        eng.validate_evidence(item.id)
        status = eng.get_evidence_status()
        assert status["total_requirements"] == 1
        assert status["collection_rate"] == 100.0
        assert status["validation_rate"] == 100.0

    def test_empty(self):
        eng = _engine()
        status = eng.get_evidence_status()
        assert status["total_requirements"] == 0

    def test_partial_collection(self):
        eng = _engine()
        eng.identify_evidence_requirements(control_id="C1")
        eng.identify_evidence_requirements(control_id="C2")
        r1 = eng._requirements[0]
        eng.collect_evidence(r1.id, content_hash="abc")
        status = eng.get_evidence_status()
        assert status["collection_rate"] == 50.0


# --- list_requirements ---


class TestListRequirements:
    def test_all(self):
        eng = _engine()
        eng.identify_evidence_requirements(control_id="C1")
        eng.identify_evidence_requirements(control_id="C2")
        assert len(eng.list_requirements()) == 2

    def test_filter_framework(self):
        eng = _engine()
        eng.identify_evidence_requirements(control_id="C1", framework=ControlFramework.SOC2)
        eng.identify_evidence_requirements(control_id="C2", framework=ControlFramework.HIPAA)
        r = eng.list_requirements(framework=ControlFramework.SOC2)
        assert len(r) == 1

    def test_filter_type(self):
        eng = _engine()
        eng.identify_evidence_requirements(control_id="C1", evidence_type=EvidenceType.LOG)
        eng.identify_evidence_requirements(
            control_id="C2",
            evidence_type=EvidenceType.SCREENSHOT,
        )
        r = eng.list_requirements(evidence_type=EvidenceType.LOG)
        assert len(r) == 1


# --- generate_report ---


class TestReport:
    def test_populated(self):
        eng = _engine()
        r = eng.identify_evidence_requirements(control_id="C1")
        eng.collect_evidence(r.id, content_hash="abc")
        report = eng.generate_report()
        assert isinstance(report, EvidenceReport)
        assert report.total_requirements == 1
        assert report.total_items == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert len(report.recommendations) > 0

    def test_gaps(self):
        eng = _engine()
        eng.identify_evidence_requirements(control_id="C1")
        report = eng.generate_report()
        assert len(report.top_gaps) == 1


# --- stats / clear ---


class TestStatsAndClear:
    def test_stats(self):
        eng = _engine()
        eng.identify_evidence_requirements(control_id="C1")
        stats = eng.get_stats()
        assert stats["total_requirements"] == 1

    def test_clear(self):
        eng = _engine()
        eng.identify_evidence_requirements(control_id="C1")
        eng.collect_evidence(requirement_id="r1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._requirements) == 0
        assert len(eng._items) == 0
