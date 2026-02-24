"""Tests for shieldops.compliance.compliance_drift — ComplianceDriftDetector.

Covers:
- DriftSeverity, DriftCategory, RemediationUrgency enums
- ComplianceDriftRecord, DriftBaseline, DriftReport model defaults
- record_drift (basic, unique IDs, extra fields, eviction at max)
- get_drift (found, not found)
- list_drifts (all, filter by framework, filter by severity, limit)
- create_baseline (basic, with drifts)
- compare_to_baseline (with baseline, no baseline)
- calculate_drift_rate (basic, empty)
- identify_recurring_drifts (recurring, none)
- mark_remediated (success, not found)
- generate_drift_report (populated, empty)
- clear_data (basic)
- get_stats (empty, populated)
"""

from __future__ import annotations

from shieldops.compliance.compliance_drift import (
    ComplianceDriftDetector,
    ComplianceDriftRecord,
    DriftBaseline,
    DriftCategory,
    DriftReport,
    DriftSeverity,
    RemediationUrgency,
)


def _engine(**kw) -> ComplianceDriftDetector:
    return ComplianceDriftDetector(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DriftSeverity (5 values)

    def test_severity_cosmetic(self):
        assert DriftSeverity.COSMETIC == "cosmetic"

    def test_severity_minor(self):
        assert DriftSeverity.MINOR == "minor"

    def test_severity_major(self):
        assert DriftSeverity.MAJOR == "major"

    def test_severity_critical(self):
        assert DriftSeverity.CRITICAL == "critical"

    def test_severity_blocking(self):
        assert DriftSeverity.BLOCKING == "blocking"

    # DriftCategory (5 values)

    def test_category_configuration(self):
        assert DriftCategory.CONFIGURATION == "configuration"

    def test_category_access_control(self):
        assert DriftCategory.ACCESS_CONTROL == "access_control"

    def test_category_encryption(self):
        assert DriftCategory.ENCRYPTION == "encryption"

    def test_category_logging(self):
        assert DriftCategory.LOGGING == "logging"

    def test_category_network(self):
        assert DriftCategory.NETWORK == "network"

    # RemediationUrgency (5 values)

    def test_urgency_immediate(self):
        assert RemediationUrgency.IMMEDIATE == "immediate"

    def test_urgency_within_24h(self):
        assert RemediationUrgency.WITHIN_24H == "within_24h"

    def test_urgency_within_week(self):
        assert RemediationUrgency.WITHIN_WEEK == "within_week"

    def test_urgency_next_audit(self):
        assert RemediationUrgency.NEXT_AUDIT == "next_audit"

    def test_urgency_accepted_risk(self):
        assert RemediationUrgency.ACCEPTED_RISK == "accepted_risk"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_drift_record_defaults(self):
        r = ComplianceDriftRecord(resource_id="res-1")
        assert r.id
        assert r.resource_id == "res-1"
        assert r.framework == ""
        assert r.control_id == ""
        assert r.drift_category == DriftCategory.CONFIGURATION
        assert r.severity == DriftSeverity.MINOR
        assert r.expected_state == ""
        assert r.actual_state == ""
        assert r.remediation_urgency == (RemediationUrgency.WITHIN_WEEK)
        assert r.is_remediated is False
        assert r.detected_at > 0
        assert r.created_at > 0

    def test_drift_baseline_defaults(self):
        b = DriftBaseline(framework="SOC2")
        assert b.id
        assert b.framework == "SOC2"
        assert b.control_count == 0
        assert b.last_audit_at == 0.0
        assert b.drift_count == 0
        assert b.compliance_pct == 100.0
        assert b.created_at > 0

    def test_drift_report_defaults(self):
        r = DriftReport()
        assert r.total_drifts == 0
        assert r.total_baselines == 0
        assert r.avg_compliance_pct == 0.0
        assert r.by_severity == {}
        assert r.by_category == {}
        assert r.by_urgency == {}
        assert r.critical_drifts == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_drift
# -------------------------------------------------------------------


class TestRecordDrift:
    def test_basic(self):
        e = _engine()
        r = e.record_drift(
            resource_id="sg-001",
            framework="SOC2",
            control_id="CC6.1",
            severity=DriftSeverity.MAJOR,
        )
        assert r.resource_id == "sg-001"
        assert r.framework == "SOC2"
        assert r.control_id == "CC6.1"
        assert r.severity == DriftSeverity.MAJOR

    def test_unique_ids(self):
        e = _engine()
        r1 = e.record_drift(resource_id="a")
        r2 = e.record_drift(resource_id="b")
        assert r1.id != r2.id

    def test_extra_fields(self):
        e = _engine()
        r = e.record_drift(
            resource_id="bucket-1",
            drift_category=DriftCategory.ENCRYPTION,
            expected_state="AES-256",
            actual_state="none",
            remediation_urgency=RemediationUrgency.IMMEDIATE,
        )
        assert r.drift_category == DriftCategory.ENCRYPTION
        assert r.expected_state == "AES-256"
        assert r.actual_state == "none"
        assert r.remediation_urgency == (RemediationUrgency.IMMEDIATE)

    def test_evicts_at_max(self):
        e = _engine(max_records=2)
        r1 = e.record_drift(resource_id="a")
        e.record_drift(resource_id="b")
        e.record_drift(resource_id="c")
        drifts = e.list_drifts()
        ids = {d.id for d in drifts}
        assert r1.id not in ids
        assert len(drifts) == 2


# -------------------------------------------------------------------
# get_drift
# -------------------------------------------------------------------


class TestGetDrift:
    def test_found(self):
        e = _engine()
        r = e.record_drift(resource_id="x")
        assert e.get_drift(r.id) is not None
        assert e.get_drift(r.id).resource_id == "x"

    def test_not_found(self):
        e = _engine()
        assert e.get_drift("nonexistent") is None


# -------------------------------------------------------------------
# list_drifts
# -------------------------------------------------------------------


class TestListDrifts:
    def test_list_all(self):
        e = _engine()
        e.record_drift(resource_id="a")
        e.record_drift(resource_id="b")
        e.record_drift(resource_id="c")
        assert len(e.list_drifts()) == 3

    def test_filter_by_framework(self):
        e = _engine()
        e.record_drift(resource_id="a", framework="SOC2")
        e.record_drift(resource_id="b", framework="HIPAA")
        filtered = e.list_drifts(framework="SOC2")
        assert len(filtered) == 1
        assert filtered[0].framework == "SOC2"

    def test_filter_by_severity(self):
        e = _engine()
        e.record_drift(
            resource_id="a",
            severity=DriftSeverity.CRITICAL,
        )
        e.record_drift(
            resource_id="b",
            severity=DriftSeverity.MINOR,
        )
        filtered = e.list_drifts(severity=DriftSeverity.CRITICAL)
        assert len(filtered) == 1

    def test_limit(self):
        e = _engine()
        for i in range(10):
            e.record_drift(resource_id=f"r-{i}")
        assert len(e.list_drifts(limit=3)) == 3


# -------------------------------------------------------------------
# create_baseline
# -------------------------------------------------------------------


class TestCreateBaseline:
    def test_basic(self):
        e = _engine()
        b = e.create_baseline(framework="SOC2", control_count=50)
        assert b.framework == "SOC2"
        assert b.control_count == 50
        assert b.compliance_pct == 100.0

    def test_with_drifts(self):
        e = _engine()
        e.record_drift(resource_id="a", framework="SOC2")
        e.record_drift(resource_id="b", framework="SOC2")
        b = e.create_baseline(framework="SOC2", control_count=10)
        assert b.drift_count == 2
        assert b.compliance_pct == 80.0


# -------------------------------------------------------------------
# compare_to_baseline
# -------------------------------------------------------------------


class TestCompareToBaseline:
    def test_with_baseline(self):
        e = _engine()
        e.record_drift(resource_id="a", framework="SOC2")
        e.create_baseline(framework="SOC2", control_count=10)
        e.record_drift(resource_id="b", framework="SOC2")
        result = e.compare_to_baseline("SOC2")
        assert result["has_baseline"] is True
        assert result["current_drift_count"] == 2
        assert result["delta"] == 1
        assert result["trending"] == "worsening"

    def test_no_baseline(self):
        e = _engine()
        result = e.compare_to_baseline("HIPAA")
        assert result["has_baseline"] is False


# -------------------------------------------------------------------
# calculate_drift_rate
# -------------------------------------------------------------------


class TestCalculateDriftRate:
    def test_basic(self):
        e = _engine()
        e.record_drift(resource_id="a", framework="SOC2")
        e.record_drift(resource_id="b", framework="SOC2")
        r = e.record_drift(resource_id="c", framework="SOC2")
        e.mark_remediated(r.id)
        result = e.calculate_drift_rate("SOC2")
        assert result["total_drifts"] == 3
        assert result["unremediated"] == 2
        assert result["drift_rate_pct"] > 0

    def test_empty(self):
        e = _engine()
        result = e.calculate_drift_rate("SOC2")
        assert result["total_drifts"] == 0
        assert result["drift_rate_pct"] == 0.0


# -------------------------------------------------------------------
# identify_recurring_drifts
# -------------------------------------------------------------------


class TestIdentifyRecurringDrifts:
    def test_recurring(self):
        e = _engine()
        e.record_drift(framework="SOC2", control_id="CC6.1")
        e.record_drift(framework="SOC2", control_id="CC6.1")
        e.record_drift(framework="SOC2", control_id="CC7.2")
        recurring = e.identify_recurring_drifts()
        assert len(recurring) == 1
        assert recurring[0]["occurrences"] == 2

    def test_none_recurring(self):
        e = _engine()
        e.record_drift(framework="SOC2", control_id="CC6.1")
        e.record_drift(framework="SOC2", control_id="CC7.2")
        assert e.identify_recurring_drifts() == []


# -------------------------------------------------------------------
# mark_remediated
# -------------------------------------------------------------------


class TestMarkRemediated:
    def test_success(self):
        e = _engine()
        r = e.record_drift(resource_id="x")
        result = e.mark_remediated(r.id)
        assert result is not None
        assert result.is_remediated is True

    def test_not_found(self):
        e = _engine()
        assert e.mark_remediated("nonexistent") is None


# -------------------------------------------------------------------
# generate_drift_report
# -------------------------------------------------------------------


class TestGenerateDriftReport:
    def test_populated(self):
        e = _engine()
        e.record_drift(
            resource_id="a",
            severity=DriftSeverity.CRITICAL,
            drift_category=DriftCategory.ENCRYPTION,
        )
        e.record_drift(
            resource_id="b",
            severity=DriftSeverity.MINOR,
            drift_category=DriftCategory.LOGGING,
        )
        e.create_baseline(framework="SOC2", control_count=10)
        report = e.generate_drift_report()
        assert report.total_drifts == 2
        assert report.total_baselines == 1
        assert "critical" in report.by_severity
        assert "encryption" in report.by_category
        assert len(report.critical_drifts) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        e = _engine()
        report = e.generate_drift_report()
        assert report.total_drifts == 0
        assert report.total_baselines == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_basic(self):
        e = _engine()
        e.record_drift(resource_id="a")
        e.record_drift(resource_id="b")
        e.create_baseline(framework="SOC2")
        count = e.clear_data()
        assert count == 2
        assert e.list_drifts() == []


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_drifts"] == 0
        assert stats["total_baselines"] == 0
        assert stats["max_records"] == 200000
        assert stats["max_drift_rate_pct"] == 5.0
        assert stats["severity_distribution"] == {}

    def test_populated(self):
        e = _engine()
        e.record_drift(
            resource_id="a",
            severity=DriftSeverity.CRITICAL,
        )
        e.record_drift(
            resource_id="b",
            severity=DriftSeverity.MINOR,
        )
        e.create_baseline(framework="SOC2")
        stats = e.get_stats()
        assert stats["total_drifts"] == 2
        assert stats["total_baselines"] == 1
        assert "critical" in stats["severity_distribution"]
        assert "minor" in stats["severity_distribution"]
