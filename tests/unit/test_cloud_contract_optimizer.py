"""Tests for CloudContractOptimizer."""

from __future__ import annotations

from shieldops.billing.cloud_contract_optimizer import (
    CloudContractOptimizer,
    ContractType,
    LeverageType,
    ScenarioOutcome,
)


def _engine(**kw) -> CloudContractOptimizer:
    return CloudContractOptimizer(**kw)


class TestEnums:
    def test_contract_type_values(self):
        for v in ContractType:
            assert isinstance(v.value, str)

    def test_leverage_type_values(self):
        for v in LeverageType:
            assert isinstance(v.value, str)

    def test_scenario_outcome_values(self):
        for v in ScenarioOutcome:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(contract_id="c1")
        assert r.contract_id == "c1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(contract_id=f"c-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            contract_id="c1",
            annual_value=10000,
            discount_pct=20,
        )
        a = eng.process(r.id)
        assert a.effective_rate == 8000.0
        assert a.savings_potential == 2000.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(annual_value=5000)
        rpt = eng.generate_report()
        assert rpt.total_annual_value == 5000.0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_risky_recommendation(self):
        eng = _engine()
        eng.add_record(scenario_outcome=ScenarioOutcome.RISKY)
        rpt = eng.generate_report()
        assert any("risky" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(contract_id="c1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAnalyzeContractTerms:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            contract_id="c1",
            annual_value=10000,
            discount_pct=15,
        )
        result = eng.analyze_contract_terms()
        assert result[0]["contract_id"] == "c1"

    def test_empty(self):
        assert _engine().analyze_contract_terms() == []


class TestIdentifyNegotiationLeverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            leverage_type=LeverageType.VOLUME,
            annual_value=5000,
        )
        result = eng.identify_negotiation_leverage()
        assert len(result) == 1
        assert result[0]["leverage_type"] == "volume"

    def test_empty(self):
        assert _engine().identify_negotiation_leverage() == []


class TestModelContractScenarios:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            contract_id="c1",
            annual_value=10000,
            discount_pct=10,
        )
        result = eng.model_contract_scenarios()
        assert len(result) == 1
        assert result[0]["base_cost"] == 10000.0

    def test_empty(self):
        assert _engine().model_contract_scenarios() == []
