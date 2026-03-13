"""Tests for ExperimentReplayEngine."""

from __future__ import annotations

from shieldops.analytics.experiment_replay_engine import (
    ComparisonMetric,
    ExperimentReplayEngine,
    ReplayMode,
    ReplayOutcome,
)


def _engine(**kw) -> ExperimentReplayEngine:
    return ExperimentReplayEngine(**kw)


class TestEnums:
    def test_replay_mode_values(self):
        assert isinstance(ReplayMode.EXACT, str)
        assert isinstance(ReplayMode.PERTURBED, str)
        assert isinstance(ReplayMode.ACCELERATED, str)
        assert isinstance(ReplayMode.SUMMARIZED, str)

    def test_replay_outcome_values(self):
        assert isinstance(ReplayOutcome.CONFIRMED, str)
        assert isinstance(ReplayOutcome.CONTRADICTED, str)
        assert isinstance(ReplayOutcome.AMBIGUOUS, str)
        assert isinstance(ReplayOutcome.ERROR, str)

    def test_comparison_metric_values(self):
        assert isinstance(ComparisonMetric.ACCURACY, str)
        assert isinstance(ComparisonMetric.LATENCY, str)
        assert isinstance(ComparisonMetric.COST, str)
        assert isinstance(ComparisonMetric.RELIABILITY, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(
            experiment_id="exp-001",
            replay_mode=ReplayMode.EXACT,
            original_value=0.9,
            replay_value=0.89,
        )
        assert r.experiment_id == "exp-001"
        assert r.original_value == 0.9

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(experiment_id=f"exp-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(experiment_id="exp-001")
        result = eng.process(r.id)
        assert "analysis_id" in result

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(experiment_id="exp-001")
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
        eng.add_record(experiment_id="e1")
        eng.add_record(experiment_id="e2")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(experiment_id="e1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestReplayExperiment:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            experiment_id="exp-001",
            replay_mode=ReplayMode.EXACT,
            original_value=0.9,
            replay_value=0.89,
        )
        result = eng.replay_experiment("exp-001")
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.replay_experiment("exp-001") == []


class TestCompareOutcomes:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            experiment_id="exp-001",
            original_value=0.9,
            replay_value=0.85,
        )
        result = eng.compare_outcomes("exp-001")
        assert result["avg_delta"] == 0.05

    def test_empty(self):
        eng = _engine()
        result = eng.compare_outcomes("exp-001")
        assert result["status"] == "no_data"


class TestDetectNondeterminism:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            experiment_id="exp-001",
            outcome=ReplayOutcome.CONTRADICTED,
        )
        eng.add_record(
            experiment_id="exp-001",
            outcome=ReplayOutcome.CONFIRMED,
        )
        result = eng.detect_nondeterminism("exp-001")
        assert result["nondeterminism_rate"] == 0.5

    def test_empty(self):
        eng = _engine()
        result = eng.detect_nondeterminism("exp-001")
        assert result["status"] == "no_data"
