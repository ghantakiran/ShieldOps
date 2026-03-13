"""Tests for AuditFindingRemediationEngine."""

from __future__ import annotations

from shieldops.audit.audit_finding_remediation_engine import (
    AuditFindingRemediationEngine,
    FindingCategory,
    FindingSeverity,
    RemediationStatus,
)


def _engine(**kw) -> AuditFindingRemediationEngine:
    return AuditFindingRemediationEngine(**kw)


class TestEnums:
    def test_finding_severity_values(self):
        for v in FindingSeverity:
            assert isinstance(v.value, str)

    def test_remediation_status_values(self):
        for v in RemediationStatus:
            assert isinstance(v.value, str)

    def test_finding_category_values(self):
        for v in FindingCategory:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(finding_id="f1")
        assert r.finding_id == "f1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(finding_id=f"f-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(finding_id="f1", risk_score=80.0, days_open=45.0)
        a = eng.process(r.id)
        assert hasattr(a, "finding_id")
        assert a.finding_id == "f1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(finding_id="f1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(finding_id="f1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(finding_id="f1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeRemediationVelocity:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(finding_id="f1", risk_score=50.0, days_open=10.0)
        result = eng.compute_remediation_velocity()
        assert len(result) == 1
        assert result[0]["finding_id"] == "f1"

    def test_empty(self):
        assert _engine().compute_remediation_velocity() == []


class TestDetectOverdueFindings:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            finding_id="f1",
            days_open=45.0,
            due_date_days=30.0,
        )
        result = eng.detect_overdue_findings()
        assert len(result) == 1
        assert result[0]["overdue_by"] == 15.0

    def test_empty(self):
        assert _engine().detect_overdue_findings() == []


class TestRankFindingsByRiskExposure:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(finding_id="f1", risk_score=50.0, days_open=45.0, due_date_days=30.0)
        eng.add_record(finding_id="f2", risk_score=80.0, days_open=60.0, due_date_days=30.0)
        result = eng.rank_findings_by_risk_exposure()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_findings_by_risk_exposure() == []
