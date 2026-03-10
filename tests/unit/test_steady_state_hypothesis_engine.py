"""Tests for SteadyStateHypothesisEngine."""

from __future__ import annotations

from shieldops.sla.steady_state_hypothesis_engine import (
    HypothesisType,
    SteadyStateHypothesisEngine,
    SteadyStateScope,
    ValidationResult,
)


def _engine(**kw) -> SteadyStateHypothesisEngine:
    return SteadyStateHypothesisEngine(**kw)


class TestEnums:
    def test_hypothesis_type_values(self):
        assert HypothesisType.AVAILABILITY == "availability"
        assert HypothesisType.LATENCY == "latency"

    def test_validation_result_values(self):
        assert ValidationResult.CONFIRMED == "confirmed"
        assert ValidationResult.VIOLATED == "violated"

    def test_steady_state_scope_values(self):
        assert SteadyStateScope.SERVICE == "service"
        assert SteadyStateScope.CLUSTER == "cluster"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(name="hyp-1", score=80.0)
        assert r.name == "hyp-1"
        assert r.score == 80.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"h-{i}")
        assert len(eng._records) == 3


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="test", score=40.0)
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
        eng.add_record(name="a", team="t1")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(name="x")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(name="a", score=70.0)
        result = eng.analyze_distribution()
        assert isinstance(result, dict)


class TestIdentifyGaps:
    def test_returns_list(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=30.0)
        result = eng.identify_gaps()
        assert isinstance(result, list)


class TestDetectTrends:
    def test_insufficient(self):
        eng = _engine()
        r = eng.detect_trends()
        assert r["trend"] == "insufficient_data"
