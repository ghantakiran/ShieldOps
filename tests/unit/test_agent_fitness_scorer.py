"""Tests for AgentFitnessScorer."""

from __future__ import annotations

from shieldops.analytics.agent_fitness_scorer import (
    AgentFitnessScorer,
    FitnessDimension,
    FitnessTrend,
    ScoringMethod,
)


def _engine(**kw) -> AgentFitnessScorer:
    return AgentFitnessScorer(**kw)


class TestEnums:
    def test_fitness_dimension_values(self):
        assert isinstance(FitnessDimension.ACCURACY, str)
        assert isinstance(FitnessDimension.SPEED, str)
        assert isinstance(FitnessDimension.COST, str)
        assert isinstance(FitnessDimension.RELIABILITY, str)

    def test_scoring_method_values(self):
        assert isinstance(ScoringMethod.WEIGHTED_SUM, str)
        assert isinstance(ScoringMethod.PARETO, str)
        assert isinstance(ScoringMethod.TOURNAMENT, str)
        assert isinstance(ScoringMethod.ELO, str)

    def test_fitness_trend_values(self):
        assert isinstance(FitnessTrend.IMPROVING, str)
        assert isinstance(FitnessTrend.PLATEAUED, str)
        assert isinstance(FitnessTrend.DECLINING, str)
        assert isinstance(FitnessTrend.VOLATILE, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(
            agent_id="a1",
            dimension=FitnessDimension.ACCURACY,
            score=0.85,
        )
        assert r.agent_id == "a1"
        assert r.score == 0.85

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(agent_id=f"a-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(agent_id="a1", score=0.9)
        result = eng.process(r.id)
        assert "analysis_id" in result

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(agent_id="a1")
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
        eng.add_record(agent_id="a1")
        eng.add_record(agent_id="a2")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(agent_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeCompositeFitness:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            agent_id="a1",
            dimension=FitnessDimension.ACCURACY,
            score=0.9,
        )
        eng.add_record(
            agent_id="a1",
            dimension=FitnessDimension.SPEED,
            score=0.7,
        )
        result = eng.compute_composite_fitness("a1")
        assert "overall_fitness" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_composite_fitness("a1")
        assert result["status"] == "no_data"


class TestDetectFitnessPlateau:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            agent_id="a1",
            trend=FitnessTrend.PLATEAUED,
        )
        result = eng.detect_fitness_plateau("a1")
        assert result["plateau_rate"] == 1.0

    def test_empty(self):
        eng = _engine()
        result = eng.detect_fitness_plateau("a1")
        assert result["status"] == "no_data"


class TestRecommendImprovementFocus:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            agent_id="a1",
            dimension=FitnessDimension.ACCURACY,
            score=0.9,
        )
        eng.add_record(
            agent_id="a1",
            dimension=FitnessDimension.COST,
            score=0.3,
        )
        result = eng.recommend_improvement_focus("a1")
        assert result["weakest_dimension"] == "cost"

    def test_empty(self):
        eng = _engine()
        result = eng.recommend_improvement_focus("a1")
        assert result["status"] == "no_data"
