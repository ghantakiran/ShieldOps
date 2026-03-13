"""Tests for RiskFactorAggregator."""

from __future__ import annotations

from shieldops.security.risk_factor_aggregator import (
    AggregationMethod,
    FactorSource,
    FactorWeight,
    RiskFactorAggregator,
)


def _engine(**kw) -> RiskFactorAggregator:
    return RiskFactorAggregator(**kw)


class TestEnums:
    def test_factor_source_values(self):
        for v in FactorSource:
            assert isinstance(v.value, str)

    def test_aggregation_method_values(self):
        for v in AggregationMethod:
            assert isinstance(v.value, str)

    def test_factor_weight_values(self):
        for v in FactorWeight:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(factor_id="f1")
        assert r.factor_id == "f1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(factor_id=f"f-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(factor_id="f1", score=10.0)
        a = eng.process(r.id)
        assert hasattr(a, "factor_id")
        assert a.factor_id == "f1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(factor_id="f1")
        assert eng.generate_report().total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(factor_id="f1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(factor_id="f1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAggregateRiskFactors:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            factor_id="f1",
            entity_id="e1",
            score=10.0,
        )
        result = eng.aggregate_risk_factors()
        assert len(result) == 1
        assert result[0]["entity_id"] == "e1"

    def test_empty(self):
        assert _engine().aggregate_risk_factors() == []


class TestDetectFactorCorrelation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            factor_id="f1",
            entity_id="e1",
            source=FactorSource.DETECTION_RULE,
        )
        eng.add_record(
            factor_id="f2",
            entity_id="e1",
            source=FactorSource.THREAT_INTEL,
        )
        result = eng.detect_factor_correlation()
        assert len(result) == 1
        assert result[0]["source_count"] == 2

    def test_empty(self):
        assert _engine().detect_factor_correlation() == []


class TestComputeFactorContribution:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(factor_id="f1", score=30.0)
        eng.add_record(factor_id="f2", score=70.0)
        result = eng.compute_factor_contribution()
        assert len(result) == 1
        assert result[0]["contribution_pct"] == 100.0

    def test_empty(self):
        assert _engine().compute_factor_contribution() == []
