"""Tests for EventContractTestingEngine."""

from __future__ import annotations

from shieldops.changes.event_contract_testing_engine import (
    ContractStatus,
    DriftSeverity,
    EventContractTestingEngine,
    TestResult,
)


def _engine(**kw) -> EventContractTestingEngine:
    return EventContractTestingEngine(**kw)


class TestEnums:
    def test_contract_status_values(self):
        for v in ContractStatus:
            assert isinstance(v.value, str)

    def test_test_result_values(self):
        for v in TestResult:
            assert isinstance(v.value, str)

    def test_drift_severity_values(self):
        for v in DriftSeverity:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(contract_id="c1")
        assert r.contract_id == "c1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(contract_id=f"c-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().record_item()
        assert r.contract_status == (ContractStatus.COMPLIANT)


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(contract_id="c1", coverage_pct=85.0)
        a = eng.process(r.id)
        assert hasattr(a, "contract_id")
        assert a.contract_id == "c1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(contract_id="c1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_broken_contracts(self):
        eng = _engine()
        eng.record_item(
            contract_id="c1",
            contract_status=ContractStatus.BROKEN,
        )
        rpt = eng.generate_report()
        assert len(rpt.broken_contracts) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(contract_id="c1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(contract_id="c1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestValidateContractCompliance:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            contract_id="c1",
            test_result=TestResult.PASSED,
            coverage_pct=90.0,
        )
        result = eng.validate_contract_compliance()
        assert len(result) == 1
        assert result[0]["pass_rate"] == 100.0

    def test_empty(self):
        r = _engine().validate_contract_compliance()
        assert r == []


class TestDetectContractDrift:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            contract_id="c1",
            contract_status=ContractStatus.DRIFTED,
            violation_count=3,
        )
        result = eng.detect_contract_drift()
        assert len(result) == 1

    def test_no_drift(self):
        eng = _engine()
        eng.record_item(
            contract_id="c1",
            contract_status=(ContractStatus.COMPLIANT),
        )
        assert eng.detect_contract_drift() == []


class TestRankContractsByViolationRisk:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            contract_id="c1",
            drift_severity=DriftSeverity.BREAKING,
            violation_count=10,
        )
        eng.record_item(
            contract_id="c2",
            drift_severity=DriftSeverity.COSMETIC,
            violation_count=1,
        )
        result = eng.rank_contracts_by_violation_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_contracts_by_violation_risk()
        assert r == []
