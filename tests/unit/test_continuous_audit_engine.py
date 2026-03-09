"""Tests for shieldops.compliance.continuous_audit_engine — ContinuousAuditEngine."""

from __future__ import annotations

from shieldops.compliance.continuous_audit_engine import (
    AuditControlStatus,
    ContinuousAuditEngine,
    FindingSeverity,
    RemediationState,
)


def _engine(**kw) -> ContinuousAuditEngine:
    return ContinuousAuditEngine(**kw)


class TestEnums:
    def test_control_status(self):
        assert AuditControlStatus.PASSING == "passing"

    def test_finding_severity(self):
        assert FindingSeverity.CRITICAL == "critical"

    def test_remediation_state(self):
        assert RemediationState.OPEN == "open"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(control_id="AC-2", control_status=AuditControlStatus.PASSING)
        assert rec.control_id == "AC-2"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(control_id=f"ctrl-{i}")
        assert len(eng._records) == 3


class TestPassRate:
    def test_basic(self):
        eng = _engine()
        eng.add_record(control_id="AC-2", control_status=AuditControlStatus.PASSING)
        eng.add_record(control_id="AC-3", control_status=AuditControlStatus.FAILING)
        result = eng.compute_pass_rate()
        assert isinstance(result, dict)


class TestStaleControls:
    def test_basic(self):
        eng = _engine()
        eng.add_record(control_id="AC-2", days_since_last_test=120)
        result = eng.identify_stale_controls()
        assert isinstance(result, list)


class TestRemediationProgress:
    def test_basic(self):
        eng = _engine()
        eng.add_record(control_id="AC-2", remediation_state=RemediationState.IN_PROGRESS)
        result = eng.track_remediation_progress()
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(control_id="AC-2", service="iam")
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
