"""Tests for AutonomousCapacityOptimizer."""

from __future__ import annotations

from shieldops.operations.autonomous_capacity_optimizer import (
    AutonomousCapacityOptimizer,
    CapacitySignal,
    OptimizationMode,
    ScalingDirection,
)


def _engine(**kw) -> AutonomousCapacityOptimizer:
    return AutonomousCapacityOptimizer(**kw)


class TestEnums:
    def test_scaling_direction_values(self):
        assert ScalingDirection.UP == "up"
        assert ScalingDirection.DOWN == "down"
        assert ScalingDirection.HORIZONTAL == "horizontal"
        assert ScalingDirection.VERTICAL == "vertical"

    def test_capacity_signal_values(self):
        assert CapacitySignal.CPU == "cpu"
        assert CapacitySignal.MEMORY == "memory"
        assert CapacitySignal.NETWORK == "network"
        assert CapacitySignal.STORAGE == "storage"

    def test_optimization_mode_values(self):
        assert OptimizationMode.CONSERVATIVE == "conservative"
        assert OptimizationMode.BALANCED == "balanced"
        assert OptimizationMode.AGGRESSIVE == "aggressive"
        assert OptimizationMode.CUSTOM == "custom"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="cap-001",
            scaling_direction=ScalingDirection.UP,
            capacity_signal=CapacitySignal.CPU,
            score=75.0,
            service="web",
            team="infra",
        )
        assert r.name == "cap-001"
        assert r.scaling_direction == ScalingDirection.UP
        assert r.score == 75.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=40.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1

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
        eng.record_item(name="t", service="a", team="b")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.record_item(name="test")
        eng.add_analysis(name="test")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestPredictCapacityNeeds:
    def test_with_data(self):
        eng = _engine(threshold=50.0)
        eng.record_item(name="a", service="web", score=85.0)
        eng.record_item(name="b", service="db", score=30.0)
        results = eng.predict_capacity_needs()
        assert len(results) == 2
        assert results[0]["service"] == "web"
        assert results[0]["needs_scaling"] is True

    def test_empty(self):
        eng = _engine()
        assert eng.predict_capacity_needs() == []


class TestGenerateScalingRecommendation:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            name="a",
            capacity_signal=CapacitySignal.CPU,
            score=90.0,
        )
        result = eng.generate_scaling_recommendation()
        recs = result["recommendations"]
        assert len(recs) == 1
        assert recs[0]["signal"] == "cpu"
        assert recs[0]["recommended_action"] == "scale_up"

    def test_empty(self):
        eng = _engine()
        result = eng.generate_scaling_recommendation()
        assert result["total_signals"] == 0


class TestEvaluateScalingOutcome:
    def test_with_data(self):
        eng = _engine(threshold=50.0)
        eng.record_item(
            name="a",
            optimization_mode=OptimizationMode.BALANCED,
            score=80.0,
        )
        eng.record_item(
            name="b",
            optimization_mode=OptimizationMode.BALANCED,
            score=30.0,
        )
        result = eng.evaluate_scaling_outcome()
        balanced = result["outcomes_by_mode"]["balanced"]
        assert balanced["count"] == 2
        assert balanced["success_rate"] == 50.0

    def test_empty(self):
        eng = _engine()
        result = eng.evaluate_scaling_outcome()
        assert result["total_evaluated"] == 0
