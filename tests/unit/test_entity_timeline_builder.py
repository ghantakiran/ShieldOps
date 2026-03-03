"""Tests for shieldops.analytics.entity_timeline_builder — EntityTimelineBuilder."""

from __future__ import annotations

from shieldops.analytics.entity_timeline_builder import (
    CorrelationLevel,
    EntityTimelineBuilder,
    EntityTimelineReport,
    EventCategory,
    TimelineAnalysis,
    TimelineRecord,
    TimelineScope,
)


def _engine(**kw) -> EntityTimelineBuilder:
    return EntityTimelineBuilder(**kw)


class TestEnums:
    def test_category_authentication(self):
        assert EventCategory.AUTHENTICATION == "authentication"

    def test_category_authorization(self):
        assert EventCategory.AUTHORIZATION == "authorization"

    def test_category_data_access(self):
        assert EventCategory.DATA_ACCESS == "data_access"

    def test_category_network(self):
        assert EventCategory.NETWORK == "network"

    def test_category_system(self):
        assert EventCategory.SYSTEM == "system"

    def test_scope_hour(self):
        assert TimelineScope.HOUR == "hour"

    def test_scope_day(self):
        assert TimelineScope.DAY == "day"

    def test_scope_week(self):
        assert TimelineScope.WEEK == "week"

    def test_scope_month(self):
        assert TimelineScope.MONTH == "month"

    def test_scope_quarter(self):
        assert TimelineScope.QUARTER == "quarter"

    def test_correlation_none(self):
        assert CorrelationLevel.NONE == "none"

    def test_correlation_weak(self):
        assert CorrelationLevel.WEAK == "weak"

    def test_correlation_moderate(self):
        assert CorrelationLevel.MODERATE == "moderate"

    def test_correlation_strong(self):
        assert CorrelationLevel.STRONG == "strong"

    def test_correlation_unknown(self):
        assert CorrelationLevel.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = TimelineRecord()
        assert r.id
        assert r.entity_name == ""
        assert r.event_category == EventCategory.AUTHENTICATION
        assert r.timeline_scope == TimelineScope.DAY
        assert r.correlation_level == CorrelationLevel.UNKNOWN
        assert r.timeline_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = TimelineAnalysis()
        assert a.id
        assert a.entity_name == ""
        assert a.event_category == EventCategory.AUTHENTICATION
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = EntityTimelineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_timeline_score == 0.0
        assert r.by_event_category == {}
        assert r.by_timeline_scope == {}
        assert r.by_correlation_level == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_timeline(
            entity_name="user-timeline-001",
            event_category=EventCategory.DATA_ACCESS,
            timeline_scope=TimelineScope.WEEK,
            correlation_level=CorrelationLevel.STRONG,
            timeline_score=85.0,
            service="forensic-svc",
            team="security",
        )
        assert r.entity_name == "user-timeline-001"
        assert r.event_category == EventCategory.DATA_ACCESS
        assert r.timeline_score == 85.0
        assert r.service == "forensic-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_timeline(entity_name=f"tl-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_timeline(entity_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_timeline(entity_name="a")
        eng.record_timeline(entity_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_event_category(self):
        eng = _engine()
        eng.record_timeline(entity_name="a", event_category=EventCategory.AUTHENTICATION)
        eng.record_timeline(entity_name="b", event_category=EventCategory.NETWORK)
        assert len(eng.list_records(event_category=EventCategory.AUTHENTICATION)) == 1

    def test_filter_by_timeline_scope(self):
        eng = _engine()
        eng.record_timeline(entity_name="a", timeline_scope=TimelineScope.DAY)
        eng.record_timeline(entity_name="b", timeline_scope=TimelineScope.WEEK)
        assert len(eng.list_records(timeline_scope=TimelineScope.DAY)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_timeline(entity_name="a", team="sec")
        eng.record_timeline(entity_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_timeline(entity_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            entity_name="test",
            analysis_score=88.5,
            breached=True,
            description="correlated events",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(entity_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_timeline(
            entity_name="a",
            event_category=EventCategory.AUTHENTICATION,
            timeline_score=90.0,
        )
        eng.record_timeline(
            entity_name="b",
            event_category=EventCategory.AUTHENTICATION,
            timeline_score=70.0,
        )
        result = eng.analyze_distribution()
        assert "authentication" in result
        assert result["authentication"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_timeline(entity_name="a", timeline_score=60.0)
        eng.record_timeline(entity_name="b", timeline_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_timeline(entity_name="a", timeline_score=50.0)
        eng.record_timeline(entity_name="b", timeline_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["timeline_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_timeline(entity_name="a", service="auth", timeline_score=90.0)
        eng.record_timeline(entity_name="b", service="api", timeline_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(entity_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(entity_name="a", analysis_score=20.0)
        eng.add_analysis(entity_name="b", analysis_score=20.0)
        eng.add_analysis(entity_name="c", analysis_score=80.0)
        eng.add_analysis(entity_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_timeline(entity_name="test", timeline_score=50.0)
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
        eng.record_timeline(entity_name="test")
        eng.add_analysis(entity_name="test")
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
        eng.record_timeline(entity_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
