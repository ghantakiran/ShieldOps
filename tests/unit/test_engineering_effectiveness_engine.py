"""Tests for EngineeringEffectivenessEngine."""

from __future__ import annotations

from shieldops.analytics.engineering_effectiveness_engine import (
    EffectivenessMetric,
    EngineeringEffectivenessEngine,
    EngineeringEffectivenessEngineAnalysis,
    EngineeringEffectivenessEngineRecord,
    EngineeringEffectivenessEngineReport,
    ImprovementArea,
    TeamPerformance,
)


def _engine(**kw) -> EngineeringEffectivenessEngine:
    return EngineeringEffectivenessEngine(**kw)


class TestEnums:
    def test_effectiveness_metric_first(self):
        assert EffectivenessMetric.DORA_METRICS == "dora_metrics"

    def test_effectiveness_metric_second(self):
        assert EffectivenessMetric.CYCLE_TIME == "cycle_time"

    def test_effectiveness_metric_third(self):
        assert EffectivenessMetric.CODE_QUALITY == "code_quality"

    def test_effectiveness_metric_fourth(self):
        assert EffectivenessMetric.INCIDENT_RESPONSE == "incident_response"

    def test_effectiveness_metric_fifth(self):
        assert EffectivenessMetric.AUTOMATION_RATE == "automation_rate"

    def test_team_performance_first(self):
        assert TeamPerformance.ELITE == "elite"

    def test_team_performance_second(self):
        assert TeamPerformance.HIGH == "high"

    def test_team_performance_third(self):
        assert TeamPerformance.MEDIUM == "medium"

    def test_team_performance_fourth(self):
        assert TeamPerformance.LOW == "low"

    def test_team_performance_fifth(self):
        assert TeamPerformance.UNKNOWN == "unknown"

    def test_improvement_area_first(self):
        assert ImprovementArea.DEPLOYMENT == "deployment"

    def test_improvement_area_second(self):
        assert ImprovementArea.TESTING == "testing"

    def test_improvement_area_third(self):
        assert ImprovementArea.MONITORING == "monitoring"

    def test_improvement_area_fourth(self):
        assert ImprovementArea.INCIDENT_MGMT == "incident_mgmt"

    def test_improvement_area_fifth(self):
        assert ImprovementArea.AUTOMATION == "automation"


class TestModels:
    def test_record_defaults(self):
        r = EngineeringEffectivenessEngineRecord()
        assert r.id
        assert r.name == ""
        assert r.effectiveness_metric == EffectivenessMetric.DORA_METRICS
        assert r.team_performance == TeamPerformance.ELITE
        assert r.improvement_area == ImprovementArea.DEPLOYMENT
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = EngineeringEffectivenessEngineAnalysis()
        assert a.id
        assert a.name == ""
        assert a.effectiveness_metric == EffectivenessMetric.DORA_METRICS
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = EngineeringEffectivenessEngineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_effectiveness_metric == {}
        assert r.by_team_performance == {}
        assert r.by_improvement_area == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            effectiveness_metric=EffectivenessMetric.DORA_METRICS,
            team_performance=TeamPerformance.HIGH,
            improvement_area=ImprovementArea.MONITORING,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.effectiveness_metric == EffectivenessMetric.DORA_METRICS
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

    def test_filter_by_effectiveness_metric(self):
        eng = _engine()
        eng.record_item(name="a", effectiveness_metric=EffectivenessMetric.CYCLE_TIME)
        eng.record_item(name="b", effectiveness_metric=EffectivenessMetric.DORA_METRICS)
        assert len(eng.list_records(effectiveness_metric=EffectivenessMetric.CYCLE_TIME)) == 1

    def test_filter_by_team_performance(self):
        eng = _engine()
        eng.record_item(name="a", team_performance=TeamPerformance.ELITE)
        eng.record_item(name="b", team_performance=TeamPerformance.HIGH)
        assert len(eng.list_records(team_performance=TeamPerformance.ELITE)) == 1

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
        eng.record_item(name="a", effectiveness_metric=EffectivenessMetric.CYCLE_TIME, score=90.0)
        eng.record_item(name="b", effectiveness_metric=EffectivenessMetric.CYCLE_TIME, score=70.0)
        result = eng.analyze_distribution()
        assert "cycle_time" in result
        assert result["cycle_time"]["count"] == 2

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
