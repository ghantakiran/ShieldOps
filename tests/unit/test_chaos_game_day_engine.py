"""Tests for ChaosGameDayEngine."""

from __future__ import annotations

from shieldops.operations.chaos_game_day_engine import (
    ChaosGameDayEngine,
    GameDayPhase,
    GameDayResult,
    ScenarioType,
)


def _engine(**kw) -> ChaosGameDayEngine:
    return ChaosGameDayEngine(**kw)


class TestEnums:
    def test_game_day_phase_values(self):
        assert GameDayPhase.PLANNING == "planning"
        assert GameDayPhase.EXECUTION == "execution"

    def test_scenario_type_values(self):
        assert ScenarioType.SERVICE_OUTAGE == "service_outage"
        assert ScenarioType.NETWORK_PARTITION == "network_partition"

    def test_game_day_result_values(self):
        assert GameDayResult.SUCCESS == "success"
        assert GameDayResult.FAILURE == "failure"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(name="gd-1", score=60.0)
        assert r.name == "gd-1"
        assert r.score == 60.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"gd-{i}")
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
