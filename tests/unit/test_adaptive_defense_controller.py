"""Tests for shieldops.security.adaptive_defense_controller — AdaptiveDefenseController."""

from __future__ import annotations

from shieldops.security.adaptive_defense_controller import (
    AdaptationTrigger,
    AdaptiveDefenseController,
    AdaptiveDefenseControllerAnalysis,
    AdaptiveDefenseControllerRecord,
    AdaptiveDefenseControllerReport,
    DefenseMode,
    ResponseSpeed,
)


def _engine(**kw) -> AdaptiveDefenseController:
    return AdaptiveDefenseController(**kw)


class TestEnums:
    def test_defense_mode_first(self):
        assert DefenseMode.NORMAL == "normal"

    def test_defense_mode_second(self):
        assert DefenseMode.ELEVATED == "elevated"

    def test_defense_mode_third(self):
        assert DefenseMode.HIGH_ALERT == "high_alert"

    def test_defense_mode_fourth(self):
        assert DefenseMode.LOCKDOWN == "lockdown"

    def test_defense_mode_fifth(self):
        assert DefenseMode.RECOVERY == "recovery"

    def test_adaptation_trigger_first(self):
        assert AdaptationTrigger.THREAT_LEVEL == "threat_level"

    def test_adaptation_trigger_second(self):
        assert AdaptationTrigger.ANOMALY == "anomaly"

    def test_adaptation_trigger_third(self):
        assert AdaptationTrigger.INCIDENT == "incident"

    def test_adaptation_trigger_fourth(self):
        assert AdaptationTrigger.INTELLIGENCE == "intelligence"

    def test_adaptation_trigger_fifth(self):
        assert AdaptationTrigger.POLICY == "policy"

    def test_response_speed_first(self):
        assert ResponseSpeed.IMMEDIATE == "immediate"

    def test_response_speed_second(self):
        assert ResponseSpeed.FAST == "fast"

    def test_response_speed_third(self):
        assert ResponseSpeed.STANDARD == "standard"

    def test_response_speed_fourth(self):
        assert ResponseSpeed.DELIBERATE == "deliberate"

    def test_response_speed_fifth(self):
        assert ResponseSpeed.PLANNED == "planned"


class TestModels:
    def test_record_defaults(self):
        r = AdaptiveDefenseControllerRecord()
        assert r.id
        assert r.name == ""
        assert r.defense_mode == DefenseMode.NORMAL
        assert r.adaptation_trigger == AdaptationTrigger.THREAT_LEVEL
        assert r.response_speed == ResponseSpeed.IMMEDIATE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = AdaptiveDefenseControllerAnalysis()
        assert a.id
        assert a.name == ""
        assert a.defense_mode == DefenseMode.NORMAL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AdaptiveDefenseControllerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_defense_mode == {}
        assert r.by_adaptation_trigger == {}
        assert r.by_response_speed == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            defense_mode=DefenseMode.NORMAL,
            adaptation_trigger=AdaptationTrigger.ANOMALY,
            response_speed=ResponseSpeed.STANDARD,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.defense_mode == DefenseMode.NORMAL
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

    def test_filter_by_defense_mode(self):
        eng = _engine()
        eng.record_item(name="a", defense_mode=DefenseMode.ELEVATED)
        eng.record_item(name="b", defense_mode=DefenseMode.NORMAL)
        assert len(eng.list_records(defense_mode=DefenseMode.ELEVATED)) == 1

    def test_filter_by_adaptation_trigger(self):
        eng = _engine()
        eng.record_item(name="a", adaptation_trigger=AdaptationTrigger.THREAT_LEVEL)
        eng.record_item(name="b", adaptation_trigger=AdaptationTrigger.ANOMALY)
        assert len(eng.list_records(adaptation_trigger=AdaptationTrigger.THREAT_LEVEL)) == 1

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
        eng.record_item(name="a", defense_mode=DefenseMode.ELEVATED, score=90.0)
        eng.record_item(name="b", defense_mode=DefenseMode.ELEVATED, score=70.0)
        result = eng.analyze_distribution()
        assert "elevated" in result
        assert result["elevated"]["count"] == 2

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
