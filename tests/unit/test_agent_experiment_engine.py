"""Tests for AgentExperimentEngine."""

from __future__ import annotations

from shieldops.analytics.agent_experiment_engine import (
    AgentExperimentEngine,
    ExperimentOutcome,
    ExperimentType,
    ResourceBudget,
)


def _engine(**kw) -> AgentExperimentEngine:
    return AgentExperimentEngine(**kw)


class TestEnums:
    def test_experiment_type_values(self):
        assert isinstance(ExperimentType.HYPERPARAMETER, str)
        assert isinstance(ExperimentType.ARCHITECTURE, str)
        assert isinstance(ExperimentType.PROMPT, str)
        assert isinstance(ExperimentType.STRATEGY, str)

    def test_experiment_outcome_values(self):
        assert isinstance(ExperimentOutcome.IMPROVED, str)
        assert isinstance(ExperimentOutcome.DEGRADED, str)
        assert isinstance(ExperimentOutcome.NEUTRAL, str)
        assert isinstance(ExperimentOutcome.INCONCLUSIVE, str)

    def test_resource_budget_values(self):
        assert isinstance(ResourceBudget.MINIMAL, str)
        assert isinstance(ResourceBudget.STANDARD, str)
        assert isinstance(ResourceBudget.EXTENDED, str)
        assert isinstance(ResourceBudget.UNLIMITED, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(
            experiment_name="exp-001",
            experiment_type=ExperimentType.PROMPT,
            metric_value=0.9,
            baseline_value=0.8,
        )
        assert r.experiment_name == "exp-001"
        assert r.metric_value == 0.9

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(experiment_name=f"exp-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            experiment_name="exp-001",
            metric_value=0.9,
            baseline_value=0.8,
        )
        result = eng.process(r.id)
        assert "analysis_id" in result

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(experiment_name="exp-001")
        report = eng.generate_report()
        assert report.total_records > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated_count(self):
        eng = _engine()
        eng.add_record(experiment_name="exp-001")
        eng.add_record(experiment_name="exp-002")
        stats = eng.get_stats()
        assert stats["total_records"] == 2


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(experiment_name="exp-001")
        eng.clear_data()
        assert len(eng._records) == 0


class TestRunExperimentCycle:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            agent_id="a1",
            experiment_name="exp-001",
            metric_value=0.9,
            baseline_value=0.8,
        )
        result = eng.run_experiment_cycle("a1")
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.run_experiment_cycle("a1") == []


class TestEvaluateMetricDelta:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            experiment_name="exp-001",
            metric_value=0.9,
            baseline_value=0.8,
        )
        result = eng.evaluate_metric_delta("exp-001")
        assert result["avg_delta"] == 0.1

    def test_empty(self):
        eng = _engine()
        result = eng.evaluate_metric_delta("exp-001")
        assert result["status"] == "no_data"


class TestSelectNextHypothesis:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            agent_id="a1",
            experiment_type=ExperimentType.PROMPT,
            metric_value=0.9,
            baseline_value=0.8,
        )
        result = eng.select_next_hypothesis("a1")
        assert "recommended_type" in result

    def test_empty(self):
        eng = _engine()
        result = eng.select_next_hypothesis("a1")
        assert result["status"] == "no_history"
