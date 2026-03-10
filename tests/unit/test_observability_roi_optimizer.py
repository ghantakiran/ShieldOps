"""Tests for ObservabilityRoiOptimizer."""

from __future__ import annotations

from shieldops.observability.observability_roi_optimizer import (
    CostCategory,
    ObservabilityRoiOptimizer,
    OptimizationAction,
    SignalValue,
)


def _engine(**kw) -> ObservabilityRoiOptimizer:
    return ObservabilityRoiOptimizer(**kw)


class TestEnums:
    def test_signal_value(self):
        assert SignalValue.CRITICAL == "critical"
        assert SignalValue.LOW == "low"

    def test_cost_category(self):
        assert CostCategory.INGESTION == "ingestion"
        assert CostCategory.STORAGE == "storage"

    def test_optimization_action(self):
        assert OptimizationAction.DOWNSAMPLE == "downsample"
        assert OptimizationAction.DROP == "drop"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="sig-1", service="api")
        assert rec.name == "sig-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"s-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="sig-1", score=70.0)
        result = eng.process("sig-1")
        assert result["key"] == "sig-1"
        assert result["avg_score"] == 70.0

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


class TestComputeSignalRoi:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            service="api",
            score=80.0,
            monthly_cost_usd=100.0,
        )
        result = eng.compute_signal_roi()
        assert isinstance(result, dict)
        assert "api" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_signal_roi()
        assert result["status"] == "no_data"


class TestIdentifyWastefulSignals:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            service="api",
            signal_value=SignalValue.LOW,
            monthly_cost_usd=200.0,
            usage_frequency=0.01,
        )
        result = eng.identify_wasteful_signals()
        assert isinstance(result, list)
        assert len(result) >= 1


class TestRecommendBudgetAllocation:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            cost_category=CostCategory.INGESTION,
            monthly_cost_usd=500.0,
            score=70.0,
        )
        result = eng.recommend_budget_allocation()
        assert "total_budget" in result

    def test_empty(self):
        eng = _engine()
        result = eng.recommend_budget_allocation()
        assert result["status"] == "no_data"
