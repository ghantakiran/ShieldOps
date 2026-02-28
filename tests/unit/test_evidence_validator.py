"""Tests for shieldops.compliance.evidence_validator — ComplianceEvidenceValidator."""

from __future__ import annotations

from shieldops.compliance.evidence_validator import (
    ComplianceEvidenceValidator,
    EvidenceFramework,
    EvidenceType,
    EvidenceValidatorReport,
    ValidationFinding,
    ValidationRecord,
    ValidationStatus,
)


def _engine(**kw) -> ComplianceEvidenceValidator:
    return ComplianceEvidenceValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # EvidenceType (5)
    def test_type_automated_scan(self):
        assert EvidenceType.AUTOMATED_SCAN == "automated_scan"

    def test_type_manual_review(self):
        assert EvidenceType.MANUAL_REVIEW == "manual_review"

    def test_type_system_log(self):
        assert EvidenceType.SYSTEM_LOG == "system_log"

    def test_type_configuration_snapshot(self):
        assert EvidenceType.CONFIGURATION_SNAPSHOT == "configuration_snapshot"

    def test_type_attestation(self):
        assert EvidenceType.ATTESTATION == "attestation"

    # ValidationStatus (5)
    def test_status_valid(self):
        assert ValidationStatus.VALID == "valid"

    def test_status_invalid(self):
        assert ValidationStatus.INVALID == "invalid"

    def test_status_expired(self):
        assert ValidationStatus.EXPIRED == "expired"

    def test_status_incomplete(self):
        assert ValidationStatus.INCOMPLETE == "incomplete"

    def test_status_pending_review(self):
        assert ValidationStatus.PENDING_REVIEW == "pending_review"

    # EvidenceFramework (5)
    def test_framework_soc2(self):
        assert EvidenceFramework.SOC2 == "soc2"

    def test_framework_hipaa(self):
        assert EvidenceFramework.HIPAA == "hipaa"

    def test_framework_pci_dss(self):
        assert EvidenceFramework.PCI_DSS == "pci_dss"

    def test_framework_gdpr(self):
        assert EvidenceFramework.GDPR == "gdpr"

    def test_framework_iso27001(self):
        assert EvidenceFramework.ISO27001 == "iso27001"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_validation_record_defaults(self):
        r = ValidationRecord()
        assert r.id
        assert r.evidence_id == ""
        assert r.control_id == ""
        assert r.evidence_type == EvidenceType.AUTOMATED_SCAN
        assert r.status == ValidationStatus.PENDING_REVIEW
        assert r.framework == EvidenceFramework.SOC2
        assert r.validity_score == 0.0
        assert r.reviewer == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_validation_finding_defaults(self):
        f = ValidationFinding()
        assert f.id
        assert f.evidence_id == ""
        assert f.control_id == ""
        assert f.framework == EvidenceFramework.SOC2
        assert f.finding_type == ""
        assert f.severity == "low"
        assert f.description == ""
        assert f.created_at > 0

    def test_evidence_validator_report_defaults(self):
        r = EvidenceValidatorReport()
        assert r.total_records == 0
        assert r.total_findings == 0
        assert r.avg_validity_score == 0.0
        assert r.by_framework == {}
        assert r.by_status == {}
        assert r.invalid_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_validation
# ---------------------------------------------------------------------------


class TestRecordValidation:
    def test_basic(self):
        eng = _engine(min_validity_pct=90.0)
        r = eng.record_validation(
            evidence_id="ev-1",
            control_id="CC6.1",
            evidence_type=EvidenceType.AUTOMATED_SCAN,
            framework=EvidenceFramework.SOC2,
            validity_score=95.0,
        )
        assert r.evidence_id == "ev-1"
        assert r.control_id == "CC6.1"
        assert r.status == ValidationStatus.VALID
        assert r.validity_score == 95.0

    def test_auto_status_invalid_low_score(self):
        eng = _engine(min_validity_pct=90.0)
        r = eng.record_validation("ev-2", "CC6.2", validity_score=20.0)
        assert r.status == ValidationStatus.INVALID

    def test_auto_status_incomplete_mid_score(self):
        eng = _engine(min_validity_pct=90.0)
        r = eng.record_validation("ev-3", "CC6.3", validity_score=60.0)
        assert r.status == ValidationStatus.INCOMPLETE

    def test_explicit_status_overrides(self):
        eng = _engine()
        r = eng.record_validation(
            "ev-4",
            "CC6.4",
            validity_score=95.0,
            status=ValidationStatus.EXPIRED,
        )
        assert r.status == ValidationStatus.EXPIRED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(f"ev-{i}", f"ctrl-{i}")
        assert len(eng._records) == 3

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_validation("ev-1", "ctrl-1")
        r2 = eng.record_validation("ev-2", "ctrl-2")
        assert r1.id != r2.id


# ---------------------------------------------------------------------------
# get_validation
# ---------------------------------------------------------------------------


class TestGetValidation:
    def test_found(self):
        eng = _engine()
        r = eng.record_validation("ev-1", "ctrl-1")
        assert eng.get_validation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_validation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_validations
# ---------------------------------------------------------------------------


class TestListValidations:
    def test_list_all(self):
        eng = _engine()
        eng.record_validation("ev-1", "ctrl-1", framework=EvidenceFramework.SOC2)
        eng.record_validation("ev-2", "ctrl-2", framework=EvidenceFramework.HIPAA)
        assert len(eng.list_validations()) == 2

    def test_filter_by_framework(self):
        eng = _engine()
        eng.record_validation("ev-1", "ctrl-1", framework=EvidenceFramework.SOC2)
        eng.record_validation("ev-2", "ctrl-2", framework=EvidenceFramework.GDPR)
        results = eng.list_validations(framework=EvidenceFramework.SOC2)
        assert len(results) == 1
        assert results[0].framework == EvidenceFramework.SOC2

    def test_filter_by_status(self):
        eng = _engine(min_validity_pct=90.0)
        eng.record_validation("ev-1", "ctrl-1", validity_score=95.0)
        eng.record_validation("ev-2", "ctrl-2", validity_score=10.0)
        results = eng.list_validations(status=ValidationStatus.VALID)
        assert len(results) == 1
        assert results[0].status == ValidationStatus.VALID


# ---------------------------------------------------------------------------
# add_finding
# ---------------------------------------------------------------------------


class TestAddFinding:
    def test_basic(self):
        eng = _engine()
        f = eng.add_finding(
            evidence_id="ev-1",
            control_id="CC6.1",
            framework=EvidenceFramework.SOC2,
            finding_type="missing_evidence",
            severity="high",
            description="No audit log found",
        )
        assert f.evidence_id == "ev-1"
        assert f.finding_type == "missing_evidence"
        assert f.severity == "high"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_finding(f"ev-{i}", f"ctrl-{i}")
        assert len(eng._findings) == 2


# ---------------------------------------------------------------------------
# analyze_validation_by_framework
# ---------------------------------------------------------------------------


class TestAnalyzeValidationByFramework:
    def test_with_data(self):
        eng = _engine(min_validity_pct=90.0)
        eng.record_validation(
            "ev-1", "CC6.1", framework=EvidenceFramework.SOC2, validity_score=95.0
        )
        eng.record_validation(
            "ev-2", "CC6.2", framework=EvidenceFramework.SOC2, validity_score=85.0
        )
        result = eng.analyze_validation_by_framework(EvidenceFramework.SOC2)
        assert result["framework"] == "soc2"
        assert result["total_evidence"] == 2
        assert result["avg_validity_score"] == 90.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_validation_by_framework(EvidenceFramework.HIPAA)
        assert result["status"] == "no_data"


# ---------------------------------------------------------------------------
# identify_invalid_evidence
# ---------------------------------------------------------------------------


class TestIdentifyInvalidEvidence:
    def test_with_invalid(self):
        eng = _engine()
        eng.record_validation(
            "ev-1", "ctrl-1", status=ValidationStatus.INVALID, validity_score=10.0
        )
        eng.record_validation("ev-2", "ctrl-2", status=ValidationStatus.VALID, validity_score=95.0)
        results = eng.identify_invalid_evidence()
        assert len(results) == 1
        assert results[0]["status"] == "invalid"

    def test_includes_expired(self):
        eng = _engine()
        eng.record_validation("ev-1", "ctrl-1", status=ValidationStatus.EXPIRED, validity_score=0.0)
        results = eng.identify_invalid_evidence()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_invalid_evidence() == []


# ---------------------------------------------------------------------------
# rank_by_validity_score
# ---------------------------------------------------------------------------


class TestRankByValidityScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_validation("ev-1", "ctrl-1", validity_score=90.0)
        eng.record_validation("ev-2", "ctrl-2", validity_score=30.0)
        results = eng.rank_by_validity_score()
        assert results[0]["validity_score"] == 30.0
        assert results[1]["validity_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_validity_score() == []


# ---------------------------------------------------------------------------
# detect_validation_gaps
# ---------------------------------------------------------------------------


class TestDetectValidationGaps:
    def test_with_invalid_gaps(self):
        eng = _engine()
        eng.record_validation(
            "ev-1",
            "ctrl-1",
            framework=EvidenceFramework.SOC2,
            status=ValidationStatus.INVALID,
            validity_score=10.0,
        )
        gaps = eng.detect_validation_gaps()
        assert len(gaps) >= 1
        soc2_gap = next((g for g in gaps if g["framework"] == "soc2"), None)
        assert soc2_gap is not None
        assert soc2_gap["gap_detected"] is True

    def test_all_valid_no_gaps(self):
        eng = _engine(min_validity_pct=90.0)
        eng.record_validation("ev-1", "ctrl-1", validity_score=95.0)
        gaps = eng.detect_validation_gaps()
        # No invalid/expired so gap_detected should be False for all entries
        assert all(not g["gap_detected"] for g in gaps)


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_validity_pct=90.0)
        eng.record_validation("ev-1", "ctrl-1", validity_score=50.0)
        eng.add_finding("ev-1", "ctrl-1", severity="high")
        report = eng.generate_report()
        assert isinstance(report, EvidenceValidatorReport)
        assert report.total_records == 1
        assert report.total_findings == 1
        assert report.invalid_count >= 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "meets validity requirements" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_validation("ev-1", "ctrl-1")
        eng.add_finding("ev-1", "ctrl-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._findings) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_findings"] == 0
        assert stats["framework_distribution"] == {}
        assert stats["unique_controls"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_validation("ev-1", "CC6.1", framework=EvidenceFramework.SOC2)
        eng.record_validation("ev-2", "HIPAA-1", framework=EvidenceFramework.HIPAA)
        eng.add_finding("ev-1", "CC6.1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_findings"] == 1
        assert stats["unique_controls"] == 2
        assert "soc2" in stats["framework_distribution"]
