"""Tests for shieldops.analytics.dora_intelligence_engine — DORAIntelligenceEngine."""

from __future__ import annotations

from shieldops.analytics.dora_intelligence_engine import (
    DORAAnalysis,
    DORAIntelligenceEngine,
    DORAIntelligenceReport,
    DORAMetric,
    DORAPerformance,
    DORARecord,
    DORASource,
)


def _engine(**kw) -> DORAIntelligenceEngine:
    return DORAIntelligenceEngine(**kw)


class TestEnums:
    def test_dora_metric_deployment_frequency(self):
        assert DORAMetric.DEPLOYMENT_FREQUENCY == "deployment_frequency"

    def test_dora_metric_lead_time(self):
        assert DORAMetric.LEAD_TIME == "lead_time"

    def test_dora_metric_change_failure_rate(self):
        assert DORAMetric.CHANGE_FAILURE_RATE == "change_failure_rate"

    def test_dora_metric_mttr(self):
        assert DORAMetric.MTTR == "mttr"

    def test_dora_metric_reliability(self):
        assert DORAMetric.RELIABILITY == "reliability"

    def test_dora_source_ci_cd_pipeline(self):
        assert DORASource.CI_CD_PIPELINE == "ci_cd_pipeline"

    def test_dora_source_git_history(self):
        assert DORASource.GIT_HISTORY == "git_history"

    def test_dora_source_incident_tracker(self):
        assert DORASource.INCIDENT_TRACKER == "incident_tracker"

    def test_dora_source_deployment_log(self):
        assert DORASource.DEPLOYMENT_LOG == "deployment_log"

    def test_dora_source_custom(self):
        assert DORASource.CUSTOM == "custom"

    def test_dora_performance_elite(self):
        assert DORAPerformance.ELITE == "elite"

    def test_dora_performance_high(self):
        assert DORAPerformance.HIGH == "high"

    def test_dora_performance_medium(self):
        assert DORAPerformance.MEDIUM == "medium"

    def test_dora_performance_low(self):
        assert DORAPerformance.LOW == "low"

    def test_dora_performance_unknown(self):
        assert DORAPerformance.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = DORARecord()
        assert r.id
        assert r.name == ""
        assert r.dora_metric == DORAMetric.DEPLOYMENT_FREQUENCY
        assert r.dora_source == DORASource.CI_CD_PIPELINE
        assert r.dora_performance == DORAPerformance.UNKNOWN
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = DORAAnalysis()
        assert a.id
        assert a.name == ""
        assert a.dora_metric == DORAMetric.DEPLOYMENT_FREQUENCY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = DORAIntelligenceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_dora_metric == {}
        assert r.by_dora_source == {}
        assert r.by_dora_performance == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            dora_metric=DORAMetric.DEPLOYMENT_FREQUENCY,
            dora_source=DORASource.GIT_HISTORY,
            dora_performance=DORAPerformance.ELITE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.dora_metric == DORAMetric.DEPLOYMENT_FREQUENCY
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_dora_metric(self):
        eng = _engine()
        eng.record_entry(name="a", dora_metric=DORAMetric.DEPLOYMENT_FREQUENCY)
        eng.record_entry(name="b", dora_metric=DORAMetric.LEAD_TIME)
        assert len(eng.list_records(dora_metric=DORAMetric.DEPLOYMENT_FREQUENCY)) == 1

    def test_filter_by_dora_source(self):
        eng = _engine()
        eng.record_entry(name="a", dora_source=DORASource.CI_CD_PIPELINE)
        eng.record_entry(name="b", dora_source=DORASource.GIT_HISTORY)
        assert len(eng.list_records(dora_source=DORASource.CI_CD_PIPELINE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
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
        eng.record_entry(name="a", dora_metric=DORAMetric.LEAD_TIME, score=90.0)
        eng.record_entry(name="b", dora_metric=DORAMetric.LEAD_TIME, score=70.0)
        result = eng.analyze_distribution()
        assert "lead_time" in result
        assert result["lead_time"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
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
        eng.record_entry(name="test", score=50.0)
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
        eng.record_entry(name="test")
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
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
