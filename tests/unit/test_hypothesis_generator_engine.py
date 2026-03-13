"""Tests for HypothesisGeneratorEngine."""

from __future__ import annotations

from shieldops.analytics.hypothesis_generator_engine import (
    HypothesisConfidence,
    HypothesisGeneratorEngine,
    HypothesisSource,
    ValidationMethod,
)


def _engine(**kw) -> HypothesisGeneratorEngine:
    return HypothesisGeneratorEngine(**kw)


class TestEnums:
    def test_hypothesis_source_values(self):
        assert isinstance(HypothesisSource.METRIC_ANALYSIS, str)
        assert isinstance(HypothesisSource.FAILURE_PATTERN, str)
        assert isinstance(HypothesisSource.PEER_COMPARISON, str)
        assert isinstance(HypothesisSource.RANDOM_EXPLORATION, str)

    def test_hypothesis_confidence_values(self):
        assert isinstance(HypothesisConfidence.STRONG, str)
        assert isinstance(HypothesisConfidence.MODERATE, str)
        assert isinstance(HypothesisConfidence.WEAK, str)
        assert isinstance(HypothesisConfidence.SPECULATIVE, str)

    def test_validation_method_values(self):
        assert isinstance(ValidationMethod.AB_TEST, str)
        assert isinstance(ValidationMethod.HOLDOUT, str)
        assert isinstance(ValidationMethod.CROSS_VALIDATION, str)
        assert isinstance(ValidationMethod.BOOTSTRAP, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(
            hypothesis_name="h-001",
            expected_impact=0.15,
        )
        assert r.hypothesis_name == "h-001"
        assert r.expected_impact == 0.15

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(hypothesis_name=f"h-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(hypothesis_name="h-001")
        result = eng.process(r.id)
        assert "analysis_id" in result

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(hypothesis_name="h-001")
        report = eng.generate_report()
        assert report.total_records > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        assert "total_records" in eng.get_stats()

    def test_populated_count(self):
        eng = _engine()
        eng.add_record(hypothesis_name="h1")
        eng.add_record(hypothesis_name="h2")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(hypothesis_name="h1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestGenerateHypotheses:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(agent_id="a1", hypothesis_name="h1")
        result = eng.generate_hypotheses("a1")
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.generate_hypotheses("a1") == []


class TestRankByExpectedImpact:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            agent_id="a1",
            hypothesis_name="h1",
            expected_impact=0.1,
        )
        eng.add_record(
            agent_id="a1",
            hypothesis_name="h2",
            expected_impact=0.5,
        )
        result = eng.rank_by_expected_impact("a1")
        assert result[0]["expected_impact"] == 0.5

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_expected_impact("a1") == []


class TestPruneTestedHypotheses:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            agent_id="a1",
            hypothesis_name="h1",
            tested=True,
        )
        eng.add_record(
            agent_id="a1",
            hypothesis_name="h2",
            tested=False,
        )
        result = eng.prune_tested_hypotheses("a1")
        assert result["tested_count"] == 1
        assert result["untested_count"] == 1

    def test_empty(self):
        eng = _engine()
        result = eng.prune_tested_hypotheses("a1")
        assert result["status"] == "no_data"
