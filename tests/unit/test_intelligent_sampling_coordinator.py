"""Tests for IntelligentSamplingCoordinator."""

from __future__ import annotations

from shieldops.observability.intelligent_sampling_coordinator import (
    IntelligentSamplingCoordinator,
    SamplingOutcome,
    SamplingStrategy,
    TraceImportance,
)


def _engine(**kw) -> IntelligentSamplingCoordinator:
    return IntelligentSamplingCoordinator(**kw)


class TestEnums:
    def test_sampling_strategy(self):
        assert SamplingStrategy.HEAD == "head"
        assert SamplingStrategy.ADAPTIVE == "adaptive"

    def test_trace_importance(self):
        assert TraceImportance.CRITICAL == "critical"
        assert TraceImportance.NOISE == "noise"

    def test_sampling_outcome(self):
        assert SamplingOutcome.SAMPLED == "sampled"
        assert SamplingOutcome.DROPPED == "dropped"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="s-1", service="api")
        assert rec.name == "s-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"s-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="s-1", score=65.0)
        result = eng.process("s-1")
        assert result["key"] == "s-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(name="s1", service="api")
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
        eng.add_record(name="s1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(name="s1", service="api")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestComputeSamplingAccuracy:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            strategy=SamplingStrategy.TAIL,
            accuracy=0.9,
        )
        result = eng.compute_sampling_accuracy()
        assert "overall_accuracy" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_sampling_accuracy()
        assert result["status"] == "no_data"


class TestOptimizeSamplingRates:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            service="api",
            importance=TraceImportance.NOISE,
            sample_rate=0.8,
        )
        result = eng.optimize_sampling_rates()
        assert isinstance(result, list)
        assert len(result) >= 1


class TestDetectSamplingBias:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            importance=TraceImportance.CRITICAL,
            outcome=SamplingOutcome.DROPPED,
        )
        result = eng.detect_sampling_bias()
        assert "biases_detected" in result

    def test_empty(self):
        eng = _engine()
        result = eng.detect_sampling_bias()
        assert result["status"] == "no_data"
