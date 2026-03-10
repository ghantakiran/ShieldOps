"""Tests for AnomalySelfLearningEngine."""

from __future__ import annotations

from shieldops.observability.anomaly_self_learning_engine import (
    AnomalySelfLearningEngine,
    FeedbackType,
    ModelState,
    SensitivityLevel,
)


def _engine(**kw) -> AnomalySelfLearningEngine:
    return AnomalySelfLearningEngine(**kw)


class TestEnums:
    def test_feedback_type(self):
        assert FeedbackType.TRUE_POSITIVE == "true_positive"

    def test_model_state(self):
        assert ModelState.ACTIVE == "active"

    def test_sensitivity_level(self):
        assert SensitivityLevel.HIGH == "high"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(metric_name="cpu_usage", service="api")
        assert rec.metric_name == "cpu_usage"
        assert rec.service == "api"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(metric_name=f"m-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(
            metric_name="cpu",
            service="api",
            model_version="v1",
        )
        result = eng.process("v1")
        assert isinstance(result, dict)
        assert result["model_version"] == "v1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestComputeModelAccuracy:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            metric_name="cpu",
            service="api",
            feedback_type=FeedbackType.TRUE_POSITIVE,
        )
        result = eng.compute_model_accuracy()
        assert isinstance(result, dict)


class TestAdjustSensitivity:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            metric_name="cpu",
            service="api",
            feedback_type=FeedbackType.TRUE_POSITIVE,
        )
        result = eng.adjust_sensitivity("api")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", service="api")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0
