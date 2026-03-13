"""Tests for ModelSelfTuningEngine."""

from __future__ import annotations

from shieldops.analytics.model_self_tuning_engine import (
    ConvergenceStatus,
    ModelSelfTuningEngine,
    TuningDimension,
    TuningStrategy,
)


def _engine(**kw) -> ModelSelfTuningEngine:
    return ModelSelfTuningEngine(**kw)


class TestEnums:
    def test_tuning_dimension_values(self):
        assert isinstance(TuningDimension.LEARNING_RATE, str)
        assert isinstance(TuningDimension.BATCH_SIZE, str)
        assert isinstance(TuningDimension.TEMPERATURE, str)
        assert isinstance(TuningDimension.TOP_P, str)

    def test_tuning_strategy_values(self):
        assert isinstance(TuningStrategy.GRID_SEARCH, str)
        assert isinstance(TuningStrategy.BAYESIAN, str)
        assert isinstance(TuningStrategy.RANDOM, str)
        assert isinstance(TuningStrategy.ADAPTIVE, str)

    def test_convergence_status_values(self):
        assert isinstance(ConvergenceStatus.CONVERGING, str)
        assert isinstance(ConvergenceStatus.OSCILLATING, str)
        assert isinstance(ConvergenceStatus.DIVERGING, str)
        assert isinstance(ConvergenceStatus.CONVERGED, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(
            model_id="m1",
            dimension=TuningDimension.LEARNING_RATE,
            metric_value=0.95,
        )
        assert r.model_id == "m1"
        assert r.metric_value == 0.95

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(model_id=f"m-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(model_id="m1", metric_value=0.9)
        result = eng.process(r.id)
        assert "analysis_id" in result

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(model_id="m1")
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
        eng.add_record(model_id="m1")
        eng.add_record(model_id="m2")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(model_id="m1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeTuningTrajectory:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(model_id="m1", iteration=1, metric_value=0.5)
        eng.add_record(model_id="m1", iteration=2, metric_value=0.7)
        result = eng.compute_tuning_trajectory("m1")
        assert len(result) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.compute_tuning_trajectory("m1") == []


class TestIdentifyOptimalConfig:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(model_id="m1", metric_value=0.5, param_value=0.01)
        eng.add_record(model_id="m1", metric_value=0.9, param_value=0.001)
        result = eng.identify_optimal_config("m1")
        assert result["best_metric"] == 0.9

    def test_empty(self):
        eng = _engine()
        result = eng.identify_optimal_config("m1")
        assert result["status"] == "no_data"


class TestDetectOverfittingRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(model_id="m1", iteration=1, metric_value=0.9)
        eng.add_record(model_id="m1", iteration=2, metric_value=0.8)
        eng.add_record(model_id="m1", iteration=3, metric_value=0.7)
        result = eng.detect_overfitting_risk("m1")
        assert result["risk"] == "high"

    def test_empty(self):
        eng = _engine()
        result = eng.detect_overfitting_risk("m1")
        assert result["status"] == "no_data"
