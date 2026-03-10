"""Tests for ServiceDegradationEngine."""

from __future__ import annotations

from shieldops.sla.service_degradation_engine import (
    DegradationCause,
    DegradationLevel,
    MitigationAction,
    ServiceDegradationEngine,
)


def _engine(**kw) -> ServiceDegradationEngine:
    return ServiceDegradationEngine(**kw)


class TestEnums:
    def test_degradation_level_values(self):
        assert DegradationLevel.NONE == "none"
        assert DegradationLevel.MAJOR == "major"

    def test_degradation_cause_values(self):
        assert DegradationCause.CAPACITY == "capacity"
        assert DegradationCause.DEPENDENCY == "dependency"

    def test_mitigation_action_values(self):
        assert MitigationAction.SCALE == "scale"
        assert MitigationAction.FAILOVER == "failover"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(name="sd-1", score=45.0)
        assert r.name == "sd-1"
        assert r.score == 45.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"sd-{i}")
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
