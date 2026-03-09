"""Tests for shieldops.operations.security_sla_tracker — SecuritySlaTracker."""

from __future__ import annotations

from shieldops.operations.security_sla_tracker import (
    EscalationLevel,
    SecuritySlaTracker,
    SlaCategory,
    SlaStatus,
)


def _engine(**kw) -> SecuritySlaTracker:
    return SecuritySlaTracker(**kw)


class TestEnums:
    def test_sla_category(self):
        assert SlaCategory.INCIDENT_RESPONSE == "incident_response"

    def test_sla_status(self):
        assert SlaStatus.WITHIN_SLA == "within_sla"

    def test_escalation(self):
        assert EscalationLevel.L1_TEAM_LEAD == "l1_team_lead"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(sla_name="P1 Response", sla_category=SlaCategory.INCIDENT_RESPONSE)
        assert rec.sla_name == "P1 Response"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(sla_name=f"sla-{i}")
        assert len(eng._records) == 3


class TestMttdMttr:
    def test_basic(self):
        eng = _engine()
        eng.add_record(sla_name="P1", target_hours=1.0, actual_hours=0.5)
        result = eng.compute_mttd_mttr()
        assert isinstance(result, dict)


class TestBreaches:
    def test_basic(self):
        eng = _engine()
        eng.add_record(sla_name="P1", sla_status=SlaStatus.BREACHED)
        result = eng.identify_breaches()
        assert isinstance(result, list)


class TestComplianceRate:
    def test_basic(self):
        eng = _engine()
        eng.add_record(sla_name="P1", sla_status=SlaStatus.WITHIN_SLA)
        eng.add_record(sla_name="P2", sla_status=SlaStatus.BREACHED)
        result = eng.compute_compliance_rate()
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(sla_name="P1", service="soc")
        result = eng.process("soc")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(sla_name="P1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(sla_name="P1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(sla_name="P1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
