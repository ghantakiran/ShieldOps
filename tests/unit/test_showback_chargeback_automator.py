"""Tests for ShowbackChargebackAutomator."""

from __future__ import annotations

from shieldops.billing.showback_chargeback_automator import (
    AllocationMethod,
    DriftSeverity,
    InvoiceStatus,
    ShowbackChargebackAutomator,
)


def _engine(**kw) -> ShowbackChargebackAutomator:
    return ShowbackChargebackAutomator(**kw)


class TestEnums:
    def test_allocation_method_values(self):
        for v in AllocationMethod:
            assert isinstance(v.value, str)

    def test_invoice_status_values(self):
        for v in InvoiceStatus:
            assert isinstance(v.value, str)

    def test_drift_severity_values(self):
        for v in DriftSeverity:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(team_id="t1")
        assert r.team_id == "t1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(team_id=f"t-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            team_id="t1",
            allocated_cost=1000,
            actual_cost=1200,
        )
        a = eng.process(r.id)
        assert a.drift_pct == 20.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_zero_allocated(self):
        eng = _engine()
        r = eng.add_record(allocated_cost=0)
        a = eng.process(r.id)
        assert a.drift_pct == 0.0


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(allocated_cost=1000)
        rpt = eng.generate_report()
        assert rpt.total_allocated == 1000.0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_critical_drift_recommendation(self):
        eng = _engine()
        eng.add_record(drift_severity=DriftSeverity.CRITICAL)
        rpt = eng.generate_report()
        assert any("critical" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(team_id="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeAllocationModel:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            team_id="t1",
            allocated_cost=1000,
            actual_cost=1200,
        )
        result = eng.compute_allocation_model()
        assert result[0]["variance"] == 200.0

    def test_empty(self):
        assert _engine().compute_allocation_model() == []


class TestDetectAllocationDrift:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            team_id="t1",
            allocated_cost=1000,
            actual_cost=1300,
        )
        result = eng.detect_allocation_drift()
        assert result[0]["drift_pct"] == 30.0

    def test_empty(self):
        assert _engine().detect_allocation_drift() == []


class TestGenerateChargebackInvoice:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(team_id="t1", actual_cost=5000)
        result = eng.generate_chargeback_invoice()
        assert result[0]["invoice_amount"] == 5000.0

    def test_empty(self):
        assert _engine().generate_chargeback_invoice() == []
