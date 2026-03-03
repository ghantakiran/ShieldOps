"""Tests for shieldops.analytics.operational_analytics_hub — OperationalAnalyticsHub."""

from __future__ import annotations

from shieldops.analytics.operational_analytics_hub import (
    AnalyticsCategory,
    InsightType,
    OperationalAnalyticsHub,
    OperationalAnalyticsHubAnalysis,
    OperationalAnalyticsHubRecord,
    OperationalAnalyticsHubReport,
    TimeHorizon,
)


def _engine(**kw) -> OperationalAnalyticsHub:
    return OperationalAnalyticsHub(**kw)


class TestEnums:
    def test_analytics_category_first(self):
        assert AnalyticsCategory.RELIABILITY == "reliability"

    def test_analytics_category_second(self):
        assert AnalyticsCategory.PERFORMANCE == "performance"

    def test_analytics_category_third(self):
        assert AnalyticsCategory.COST == "cost"

    def test_analytics_category_fourth(self):
        assert AnalyticsCategory.SECURITY == "security"

    def test_analytics_category_fifth(self):
        assert AnalyticsCategory.PRODUCTIVITY == "productivity"

    def test_time_horizon_first(self):
        assert TimeHorizon.REAL_TIME == "real_time"

    def test_time_horizon_second(self):
        assert TimeHorizon.HOURLY == "hourly"

    def test_time_horizon_third(self):
        assert TimeHorizon.DAILY == "daily"

    def test_time_horizon_fourth(self):
        assert TimeHorizon.WEEKLY == "weekly"

    def test_time_horizon_fifth(self):
        assert TimeHorizon.MONTHLY == "monthly"

    def test_insight_type_first(self):
        assert InsightType.TREND == "trend"

    def test_insight_type_second(self):
        assert InsightType.ANOMALY == "anomaly"

    def test_insight_type_third(self):
        assert InsightType.CORRELATION == "correlation"

    def test_insight_type_fourth(self):
        assert InsightType.PREDICTION == "prediction"

    def test_insight_type_fifth(self):
        assert InsightType.RECOMMENDATION == "recommendation"


class TestModels:
    def test_record_defaults(self):
        r = OperationalAnalyticsHubRecord()
        assert r.id
        assert r.name == ""
        assert r.analytics_category == AnalyticsCategory.RELIABILITY
        assert r.time_horizon == TimeHorizon.REAL_TIME
        assert r.insight_type == InsightType.TREND
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = OperationalAnalyticsHubAnalysis()
        assert a.id
        assert a.name == ""
        assert a.analytics_category == AnalyticsCategory.RELIABILITY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = OperationalAnalyticsHubReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_analytics_category == {}
        assert r.by_time_horizon == {}
        assert r.by_insight_type == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            analytics_category=AnalyticsCategory.RELIABILITY,
            time_horizon=TimeHorizon.HOURLY,
            insight_type=InsightType.CORRELATION,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.analytics_category == AnalyticsCategory.RELIABILITY
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

    def test_filter_by_analytics_category(self):
        eng = _engine()
        eng.record_item(name="a", analytics_category=AnalyticsCategory.PERFORMANCE)
        eng.record_item(name="b", analytics_category=AnalyticsCategory.RELIABILITY)
        assert len(eng.list_records(analytics_category=AnalyticsCategory.PERFORMANCE)) == 1

    def test_filter_by_time_horizon(self):
        eng = _engine()
        eng.record_item(name="a", time_horizon=TimeHorizon.REAL_TIME)
        eng.record_item(name="b", time_horizon=TimeHorizon.HOURLY)
        assert len(eng.list_records(time_horizon=TimeHorizon.REAL_TIME)) == 1

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
        eng.record_item(name="a", analytics_category=AnalyticsCategory.PERFORMANCE, score=90.0)
        eng.record_item(name="b", analytics_category=AnalyticsCategory.PERFORMANCE, score=70.0)
        result = eng.analyze_distribution()
        assert "performance" in result
        assert result["performance"]["count"] == 2

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
