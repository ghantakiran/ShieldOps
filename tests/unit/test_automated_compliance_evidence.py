"""Tests for shieldops.security.automated_compliance_evidence — AutomatedComplianceEvidence."""

from __future__ import annotations

from shieldops.security.automated_compliance_evidence import (
    AutomatedComplianceEvidence,
    ComplianceFramework,
    EvidenceType,
    ValidationStatus,
)


def _engine(**kw) -> AutomatedComplianceEvidence:
    return AutomatedComplianceEvidence(**kw)


class TestEnums:
    def test_evidence_type(self):
        assert EvidenceType.CONFIGURATION == "configuration"

    def test_validation(self):
        assert ValidationStatus.VALID == "valid"

    def test_framework(self):
        assert ComplianceFramework.SOC2 == "soc2"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(control_id="AC-2", framework=ComplianceFramework.SOC2)
        assert rec.control_id == "AC-2"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(control_id=f"ctrl-{i}")
        assert len(eng._records) == 3


class TestAuditReadiness:
    def test_basic(self):
        eng = _engine()
        eng.add_record(control_id="AC-2", validation_status=ValidationStatus.VALID)
        result = eng.compute_audit_readiness()
        assert isinstance(result, dict)


class TestStaleEvidence:
    def test_basic(self):
        eng = _engine()
        eng.add_record(control_id="AC-2", last_validated_at=0.0)
        result = eng.identify_stale_evidence()
        assert isinstance(result, list)


class TestFrameworkCoverage:
    def test_basic(self):
        eng = _engine()
        eng.add_record(control_id="AC-2", framework=ComplianceFramework.SOC2)
        result = eng.framework_coverage()
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(control_id="AC-2", service="api")
        result = eng.process("AC-2")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(control_id="AC-2")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(control_id="AC-2")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(control_id="AC-2")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
