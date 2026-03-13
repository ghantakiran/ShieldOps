"""Tests for LightweightTrainingEngine."""

from __future__ import annotations

from shieldops.analytics.lightweight_training_engine import (
    LightweightTrainingEngine,
    ResourceConstraint,
    TrainingMode,
    TrainingPhase,
)


def _engine(**kw) -> LightweightTrainingEngine:
    return LightweightTrainingEngine(**kw)


class TestEnums:
    def test_training_mode_values(self):
        assert isinstance(TrainingMode.FULL, str)
        assert isinstance(TrainingMode.LORA, str)
        assert isinstance(TrainingMode.QLORA, str)
        assert isinstance(TrainingMode.DISTILLATION, str)

    def test_resource_constraint_values(self):
        assert isinstance(ResourceConstraint.MEMORY, str)
        assert isinstance(ResourceConstraint.COMPUTE, str)
        assert isinstance(ResourceConstraint.TIME, str)
        assert isinstance(ResourceConstraint.COST, str)

    def test_training_phase_values(self):
        assert isinstance(TrainingPhase.WARMUP, str)
        assert isinstance(TrainingPhase.TRAINING, str)
        assert isinstance(TrainingPhase.COOLDOWN, str)
        assert isinstance(TrainingPhase.EVALUATION, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(
            job_name="job-001",
            training_mode=TrainingMode.LORA,
            loss_value=0.5,
        )
        assert r.job_name == "job-001"
        assert r.loss_value == 0.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(job_name=f"job-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(job_name="job-001")
        result = eng.process(r.id)
        assert "analysis_id" in result

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(job_name="job-001")
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
        eng.add_record(job_name="j1")
        eng.add_record(job_name="j2")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(job_name="j1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestEstimateResourceUsage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(job_name="j1", resource_usage_pct=75.0)
        result = eng.estimate_resource_usage("j1")
        assert result["avg_usage"] == 75.0

    def test_empty(self):
        eng = _engine()
        result = eng.estimate_resource_usage("j1")
        assert result["status"] == "no_data"


class TestOptimizeBatchSchedule:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(job_name="j1", epoch=1, loss_value=0.5)
        eng.add_record(job_name="j1", epoch=2, loss_value=0.3)
        result = eng.optimize_batch_schedule("j1")
        assert result["total_epochs"] == 2

    def test_empty(self):
        eng = _engine()
        result = eng.optimize_batch_schedule("j1")
        assert result["status"] == "no_data"


class TestComputeTrainingEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            job_name="j1",
            loss_value=0.2,
            resource_usage_pct=50.0,
        )
        result = eng.compute_training_efficiency("j1")
        assert "efficiency" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_training_efficiency("j1")
        assert result["status"] == "no_data"
