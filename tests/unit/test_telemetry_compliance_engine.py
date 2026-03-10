"""Tests for TelemetryComplianceEngine."""

from __future__ import annotations

from shieldops.observability.telemetry_compliance_engine import (
    ComplianceStandard,
    DataSensitivity,
    RetentionPolicy,
    TelemetryComplianceEngine,
)


def _engine(**kw) -> TelemetryComplianceEngine:
    return TelemetryComplianceEngine(**kw)


class TestEnums:
    def test_compliance_standard(self):
        assert ComplianceStandard.GDPR == "gdpr"
        assert ComplianceStandard.HIPAA == "hipaa"

    def test_data_sensitivity(self):
        assert DataSensitivity.PUBLIC == "public"
        assert DataSensitivity.RESTRICTED == "restricted"

    def test_retention_policy(self):
        assert RetentionPolicy.DAYS_30 == "days_30"
        assert RetentionPolicy.INDEFINITE == "indefinite"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="tel-1", service="api")
        assert rec.name == "tel-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"t-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="tel-1", score=90.0)
        result = eng.process("tel-1")
        assert result["key"] == "tel-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(name="t1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.add_record(name="t1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(name="t1", service="api")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestAuditDataResidency:
    def test_basic(self):
        eng = _engine()
        eng.add_record(name="t1", region="us-east-1", pii_detected=True)
        result = eng.audit_data_residency()
        assert "regions" in result

    def test_empty(self):
        eng = _engine()
        result = eng.audit_data_residency()
        assert result["status"] == "no_data"


class TestDetectPiiInTelemetry:
    def test_basic(self):
        eng = _engine()
        eng.add_record(name="t1", service="api", pii_detected=True)
        result = eng.detect_pii_in_telemetry()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_no_pii(self):
        eng = _engine()
        eng.add_record(name="t1", pii_detected=False)
        result = eng.detect_pii_in_telemetry()
        assert len(result) == 0


class TestEnforceRetentionRules:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="t1",
            standard=ComplianceStandard.HIPAA,
            retention=RetentionPolicy.DAYS_365,
        )
        result = eng.enforce_retention_rules()
        assert "total_checked" in result

    def test_empty(self):
        eng = _engine()
        result = eng.enforce_retention_rules()
        assert result["status"] == "no_data"
