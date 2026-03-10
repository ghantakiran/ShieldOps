"""Tests for FaultPropagationEngine."""

from __future__ import annotations

from shieldops.topology.fault_propagation_engine import (
    FaultPropagationEngine,
    FaultType,
    PropagationPath,
    PropagationRisk,
)


def _engine(**kw) -> FaultPropagationEngine:
    return FaultPropagationEngine(**kw)


class TestEnums:
    def test_propagation_path_values(self):
        assert PropagationPath.UPSTREAM == "upstream"
        assert PropagationPath.DOWNSTREAM == "downstream"

    def test_fault_type_values(self):
        assert FaultType.TIMEOUT == "timeout"
        assert FaultType.ERROR_SPIKE == "error_spike"

    def test_propagation_risk_values(self):
        assert PropagationRisk.CRITICAL == "critical"
        assert PropagationRisk.HIGH == "high"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(name="fp-1", score=65.0)
        assert r.name == "fp-1"
        assert r.score == 65.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"fp-{i}")
        assert len(eng._records) == 3


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=40.0)
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
        eng.record_item(name="a", team="t1")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.record_item(name="x")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="a", score=70.0)
        result = eng.analyze_distribution()
        assert isinstance(result, dict)


class TestIdentifyGaps:
    def test_returns_list(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=30.0)
        result = eng.identify_gaps()
        assert isinstance(result, list)


class TestDetectTrends:
    def test_insufficient(self):
        eng = _engine()
        r = eng.detect_trends()
        assert r["trend"] == "insufficient_data"
