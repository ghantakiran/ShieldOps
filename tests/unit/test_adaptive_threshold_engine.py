"""Tests for AdaptiveThresholdEngine."""

from __future__ import annotations

from shieldops.observability.adaptive_threshold_engine import (
    AdaptiveThresholdEngine,
    AdjustmentReason,
    ThresholdHealth,
    ThresholdStrategy,
)


def _engine(**kw) -> AdaptiveThresholdEngine:
    return AdaptiveThresholdEngine(**kw)


class TestEnums:
    def test_threshold_strategy(self):
        assert ThresholdStrategy.STATIC == "static"

    def test_adjustment_reason(self):
        assert AdjustmentReason.SEASONALITY == "seasonality"

    def test_threshold_health(self):
        assert ThresholdHealth.OPTIMAL == "optimal"


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
        eng.add_record(metric_name="cpu", service="api")
        result = eng.process("cpu")
        assert isinstance(result, dict)
        assert result["metric_name"] == "cpu"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestComputeOptimalThreshold:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            metric_name="cpu",
            service="api",
            false_positive_rate=0.1,
        )
        result = eng.compute_optimal_threshold("cpu")
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
