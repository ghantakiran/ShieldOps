"""Tests for MetricConvergenceTracker."""

from __future__ import annotations

from shieldops.analytics.metric_convergence_tracker import (
    ConvergencePattern,
    MetricConvergenceTracker,
    MetricType,
    StabilityLevel,
)


def _engine(**kw) -> MetricConvergenceTracker:
    return MetricConvergenceTracker(**kw)


class TestEnums:
    def test_convergence_pattern_values(self):
        assert isinstance(ConvergencePattern.MONOTONIC, str)
        assert isinstance(ConvergencePattern.OSCILLATING, str)
        assert isinstance(ConvergencePattern.STEP_WISE, str)
        assert isinstance(ConvergencePattern.ASYMPTOTIC, str)

    def test_stability_level_values(self):
        assert isinstance(StabilityLevel.STABLE, str)
        assert isinstance(StabilityLevel.UNSTABLE, str)
        assert isinstance(StabilityLevel.TRANSITIONING, str)
        assert isinstance(StabilityLevel.CHAOTIC, str)

    def test_metric_type_values(self):
        assert isinstance(MetricType.LOSS, str)
        assert isinstance(MetricType.ACCURACY, str)
        assert isinstance(MetricType.LATENCY, str)
        assert isinstance(MetricType.THROUGHPUT, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(
            experiment_id="exp-001",
            metric_value=0.5,
            iteration=1,
        )
        assert r.experiment_id == "exp-001"
        assert r.metric_value == 0.5

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


class TestDetectConvergencePoint:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            experiment_id="exp-001",
            iteration=1,
            metric_value=0.5,
        )
        eng.add_record(
            experiment_id="exp-001",
            iteration=2,
            metric_value=0.5,
        )
        result = eng.detect_convergence_point("exp-001")
        assert result["converged_at"] == 2

    def test_empty(self):
        eng = _engine()
        result = eng.detect_convergence_point("exp-001")
        assert result["status"] == "no_data"


class TestComputeConvergenceRate:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            experiment_id="exp-001",
            iteration=1,
            metric_value=0.5,
        )
        eng.add_record(
            experiment_id="exp-001",
            iteration=2,
            metric_value=0.3,
        )
        result = eng.compute_convergence_rate("exp-001")
        assert result["avg_rate"] == 0.2

    def test_empty(self):
        eng = _engine()
        result = eng.compute_convergence_rate("exp-001")
        assert result["status"] == "no_data"


class TestPredictFinalMetric:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            experiment_id="exp-001",
            iteration=1,
            metric_value=0.5,
        )
        result = eng.predict_final_metric("exp-001")
        assert result["predicted_value"] == 0.5

    def test_empty(self):
        eng = _engine()
        result = eng.predict_final_metric("exp-001")
        assert result["status"] == "no_data"
