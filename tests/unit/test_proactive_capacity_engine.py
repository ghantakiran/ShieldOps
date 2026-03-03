"""Tests for shieldops.operations.proactive_capacity_engine — ProactiveCapacityEngine."""

from __future__ import annotations

from shieldops.operations.proactive_capacity_engine import (
    CapacityAction,
    ForecastAccuracy,
    ProactiveCapacityEngine,
    ProactiveCapacityEngineAnalysis,
    ProactiveCapacityEngineRecord,
    ProactiveCapacityEngineReport,
    ResourceType,
)


def _engine(**kw) -> ProactiveCapacityEngine:
    return ProactiveCapacityEngine(**kw)


class TestEnums:
    def test_resource_type_first(self):
        assert ResourceType.CPU == "cpu"

    def test_resource_type_second(self):
        assert ResourceType.MEMORY == "memory"

    def test_resource_type_third(self):
        assert ResourceType.STORAGE == "storage"

    def test_resource_type_fourth(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_type_fifth(self):
        assert ResourceType.GPU == "gpu"

    def test_capacity_action_first(self):
        assert CapacityAction.SCALE_UP == "scale_up"

    def test_capacity_action_second(self):
        assert CapacityAction.SCALE_OUT == "scale_out"

    def test_capacity_action_third(self):
        assert CapacityAction.OPTIMIZE == "optimize"

    def test_capacity_action_fourth(self):
        assert CapacityAction.MIGRATE == "migrate"

    def test_capacity_action_fifth(self):
        assert CapacityAction.RESERVE == "reserve"

    def test_forecast_accuracy_first(self):
        assert ForecastAccuracy.EXCELLENT == "excellent"

    def test_forecast_accuracy_second(self):
        assert ForecastAccuracy.GOOD == "good"

    def test_forecast_accuracy_third(self):
        assert ForecastAccuracy.FAIR == "fair"

    def test_forecast_accuracy_fourth(self):
        assert ForecastAccuracy.POOR == "poor"

    def test_forecast_accuracy_fifth(self):
        assert ForecastAccuracy.UNRELIABLE == "unreliable"


class TestModels:
    def test_record_defaults(self):
        r = ProactiveCapacityEngineRecord()
        assert r.id
        assert r.name == ""
        assert r.resource_type == ResourceType.CPU
        assert r.capacity_action == CapacityAction.SCALE_UP
        assert r.forecast_accuracy == ForecastAccuracy.EXCELLENT
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ProactiveCapacityEngineAnalysis()
        assert a.id
        assert a.name == ""
        assert a.resource_type == ResourceType.CPU
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ProactiveCapacityEngineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_resource_type == {}
        assert r.by_capacity_action == {}
        assert r.by_forecast_accuracy == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            resource_type=ResourceType.CPU,
            capacity_action=CapacityAction.SCALE_OUT,
            forecast_accuracy=ForecastAccuracy.FAIR,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.resource_type == ResourceType.CPU
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_resource_type(self):
        eng = _engine()
        eng.record_item(name="a", resource_type=ResourceType.MEMORY)
        eng.record_item(name="b", resource_type=ResourceType.CPU)
        assert len(eng.list_records(resource_type=ResourceType.MEMORY)) == 1

    def test_filter_by_capacity_action(self):
        eng = _engine()
        eng.record_item(name="a", capacity_action=CapacityAction.SCALE_UP)
        eng.record_item(name="b", capacity_action=CapacityAction.SCALE_OUT)
        assert len(eng.list_records(capacity_action=CapacityAction.SCALE_UP)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="a", resource_type=ResourceType.MEMORY, score=90.0)
        eng.record_item(name="b", resource_type=ResourceType.MEMORY, score=70.0)
        result = eng.analyze_distribution()
        assert "memory" in result
        assert result["memory"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(name="a", service="auth", score=90.0)
        eng.record_item(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_item(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
