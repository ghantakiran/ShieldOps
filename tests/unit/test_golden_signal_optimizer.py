"""Tests for shieldops.observability.golden_signal_optimizer — GoldenSignalOptimizer."""

from __future__ import annotations

from shieldops.observability.golden_signal_optimizer import (
    GoldenSignal,
    GoldenSignalOptimizer,
    GoldenSignalRecord,
    SignalHealth,
    ThresholdAction,
)


def _engine(**kw) -> GoldenSignalOptimizer:
    return GoldenSignalOptimizer(**kw)


class TestEnums:
    def test_signal_latency(self):
        assert GoldenSignal.LATENCY == "latency"

    def test_signal_traffic(self):
        assert GoldenSignal.TRAFFIC == "traffic"

    def test_health_healthy(self):
        assert SignalHealth.OPTIMAL == "optimal"

    def test_threshold_action(self):
        assert ThresholdAction.TIGHTEN == "tighten"


class TestModels:
    def test_record_defaults(self):
        r = GoldenSignalRecord()
        assert r.id
        assert r.current_value == 0.0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(service="api-gw", signal=GoldenSignal.LATENCY, current_value=150.0)
        assert rec.service == "api-gw"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(service=f"svc-{i}", signal=GoldenSignal.ERRORS, current_value=float(i))
        assert len(eng._records) == 3


class TestCoverage:
    def test_basic(self):
        eng = _engine()
        eng.add_record(service="api", signal=GoldenSignal.LATENCY, coverage_pct=80.0)
        result = eng.compute_coverage()
        assert isinstance(result, dict)


class TestThresholds:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            service="api", signal=GoldenSignal.LATENCY, current_value=150.0, threshold_value=200.0
        )
        result = eng.recommend_thresholds("api")
        assert isinstance(result, list)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(service="api", signal=GoldenSignal.LATENCY, current_value=100.0)
        result = eng.process("api")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(service="api", signal=GoldenSignal.LATENCY, current_value=100.0)
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(service="api", signal=GoldenSignal.LATENCY)
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(service="api", signal=GoldenSignal.LATENCY)
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
