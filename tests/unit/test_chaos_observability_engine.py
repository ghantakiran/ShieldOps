"""Tests for ChaosObservabilityEngine."""

from __future__ import annotations

from shieldops.observability.chaos_observability_engine import (
    ChaosObservabilityEngine,
    CoverageLevel,
    ObservabilityGap,
    SignalType,
)


def _engine(**kw) -> ChaosObservabilityEngine:
    return ChaosObservabilityEngine(**kw)


class TestEnums:
    def test_signal_type_values(self):
        assert SignalType.METRIC == "metric"
        assert SignalType.LOG == "log"

    def test_coverage_level_values(self):
        assert CoverageLevel.FULL == "full"
        assert CoverageLevel.PARTIAL == "partial"

    def test_observability_gap_values(self):
        assert ObservabilityGap.MISSING_METRIC == "missing_metric"
        assert ObservabilityGap.BLIND_SPOT == "blind_spot"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(name="co-1", score=50.0)
        assert r.name == "co-1"
        assert r.score == 50.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"co-{i}")
        assert len(eng._records) == 3


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="test", score=40.0)
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
        eng.add_record(name="a", team="t1")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(name="x")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(name="a", score=70.0)
        result = eng.analyze_distribution()
        assert isinstance(result, dict)


class TestIdentifyGaps:
    def test_returns_list(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=30.0)
        result = eng.identify_gaps()
        assert isinstance(result, list)


class TestDetectTrends:
    def test_insufficient(self):
        eng = _engine()
        r = eng.detect_trends()
        assert r["trend"] == "insufficient_data"
