"""Tests for ApiSlaComplianceTracker."""

from __future__ import annotations

from shieldops.sla.api_sla_compliance_tracker import (
    ApiSlaComplianceTracker,
    ComplianceStatus,
    ConsumerTier,
    SlaMetric,
)


def _engine(**kw) -> ApiSlaComplianceTracker:
    return ApiSlaComplianceTracker(**kw)


class TestEnums:
    def test_compliance_status_values(self):
        for v in ComplianceStatus:
            assert isinstance(v.value, str)

    def test_sla_metric_values(self):
        for v in SlaMetric:
            assert isinstance(v.value, str)

    def test_consumer_tier_values(self):
        for v in ConsumerTier:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(api_name="users-api")
        assert r.api_name == "users-api"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(api_name=f"api-{i}")
        assert len(eng._records) == 5

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            api_name="users-api",
            consumer_id="c-1",
            compliance_status=(ComplianceStatus.BREACHED),
            target_value=99.9,
            actual_value=98.5,
        )
        assert r.actual_value == 98.5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(api_name="users-api")
        a = eng.process(r.id)
        assert a.api_name == "users-api"

    def test_breached(self):
        eng = _engine()
        r = eng.add_record(
            compliance_status=(ComplianceStatus.BREACHED),
        )
        a = eng.process(r.id)
        assert a.breach_risk is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(api_name="users-api")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_breached_apis(self):
        eng = _engine()
        eng.add_record(
            api_name="users-api",
            compliance_status=(ComplianceStatus.BREACHED),
        )
        rpt = eng.generate_report()
        assert len(rpt.breached_apis) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(api_name="users-api")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(api_name="users-api")
        eng.clear_data()
        assert len(eng._records) == 0


class TestMeasureApiSlaAdherence:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            api_name="users-api",
            target_value=99.9,
            actual_value=99.5,
        )
        result = eng.measure_api_sla_adherence()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().measure_api_sla_adherence() == []


class TestDetectSlaBreachRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            api_name="users-api",
            compliance_status=(ComplianceStatus.AT_RISK),
        )
        result = eng.detect_sla_breach_risk()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_sla_breach_risk() == []


class TestGenerateSlaComplianceReport:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            consumer_tier=ConsumerTier.PLATINUM,
            compliance_status=(ComplianceStatus.COMPLIANT),
        )
        result = eng.generate_sla_compliance_report()
        assert len(result) == 1
        assert result[0]["compliance_rate"] == 100.0

    def test_empty(self):
        assert _engine().generate_sla_compliance_report() == []
