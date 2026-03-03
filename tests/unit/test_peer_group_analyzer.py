"""Tests for shieldops.analytics.peer_group_analyzer — PeerGroupAnalyzer."""

from __future__ import annotations

from shieldops.analytics.peer_group_analyzer import (
    DeviationSeverity,
    DeviationType,
    GroupingCriteria,
    PeerGroupAnalysis,
    PeerGroupAnalyzer,
    PeerGroupRecord,
    PeerGroupReport,
)


def _engine(**kw) -> PeerGroupAnalyzer:
    return PeerGroupAnalyzer(**kw)


class TestEnums:
    def test_criteria_role(self):
        assert GroupingCriteria.ROLE == "role"

    def test_criteria_department(self):
        assert GroupingCriteria.DEPARTMENT == "department"

    def test_criteria_location(self):
        assert GroupingCriteria.LOCATION == "location"

    def test_criteria_access_level(self):
        assert GroupingCriteria.ACCESS_LEVEL == "access_level"

    def test_criteria_behavior_pattern(self):
        assert GroupingCriteria.BEHAVIOR_PATTERN == "behavior_pattern"

    def test_deviation_access_anomaly(self):
        assert DeviationType.ACCESS_ANOMALY == "access_anomaly"

    def test_deviation_time_anomaly(self):
        assert DeviationType.TIME_ANOMALY == "time_anomaly"

    def test_deviation_volume_anomaly(self):
        assert DeviationType.VOLUME_ANOMALY == "volume_anomaly"

    def test_deviation_pattern_anomaly(self):
        assert DeviationType.PATTERN_ANOMALY == "pattern_anomaly"

    def test_deviation_resource_anomaly(self):
        assert DeviationType.RESOURCE_ANOMALY == "resource_anomaly"

    def test_severity_low(self):
        assert DeviationSeverity.LOW == "low"

    def test_severity_medium(self):
        assert DeviationSeverity.MEDIUM == "medium"

    def test_severity_high(self):
        assert DeviationSeverity.HIGH == "high"

    def test_severity_critical(self):
        assert DeviationSeverity.CRITICAL == "critical"

    def test_severity_normal(self):
        assert DeviationSeverity.NORMAL == "normal"


class TestModels:
    def test_record_defaults(self):
        r = PeerGroupRecord()
        assert r.id
        assert r.group_name == ""
        assert r.grouping_criteria == GroupingCriteria.ROLE
        assert r.deviation_type == DeviationType.ACCESS_ANOMALY
        assert r.deviation_severity == DeviationSeverity.NORMAL
        assert r.deviation_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PeerGroupAnalysis()
        assert a.id
        assert a.group_name == ""
        assert a.grouping_criteria == GroupingCriteria.ROLE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PeerGroupReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_deviation_score == 0.0
        assert r.by_grouping_criteria == {}
        assert r.by_deviation_type == {}
        assert r.by_deviation_severity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_deviation(
            group_name="eng-team",
            grouping_criteria=GroupingCriteria.DEPARTMENT,
            deviation_type=DeviationType.RESOURCE_ANOMALY,
            deviation_severity=DeviationSeverity.HIGH,
            deviation_score=85.0,
            service="compute-svc",
            team="engineering",
        )
        assert r.group_name == "eng-team"
        assert r.grouping_criteria == GroupingCriteria.DEPARTMENT
        assert r.deviation_score == 85.0
        assert r.service == "compute-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_deviation(group_name=f"group-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_deviation(group_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_deviation(group_name="a")
        eng.record_deviation(group_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_grouping_criteria(self):
        eng = _engine()
        eng.record_deviation(group_name="a", grouping_criteria=GroupingCriteria.ROLE)
        eng.record_deviation(group_name="b", grouping_criteria=GroupingCriteria.DEPARTMENT)
        assert len(eng.list_records(grouping_criteria=GroupingCriteria.ROLE)) == 1

    def test_filter_by_deviation_type(self):
        eng = _engine()
        eng.record_deviation(group_name="a", deviation_type=DeviationType.ACCESS_ANOMALY)
        eng.record_deviation(group_name="b", deviation_type=DeviationType.VOLUME_ANOMALY)
        assert len(eng.list_records(deviation_type=DeviationType.ACCESS_ANOMALY)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_deviation(group_name="a", team="sec")
        eng.record_deviation(group_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_deviation(group_name=f"g-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            group_name="test", analysis_score=88.5, breached=True, description="deviation"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(group_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_deviation(
            group_name="a",
            grouping_criteria=GroupingCriteria.ROLE,
            deviation_score=90.0,
        )
        eng.record_deviation(
            group_name="b",
            grouping_criteria=GroupingCriteria.ROLE,
            deviation_score=70.0,
        )
        result = eng.analyze_distribution()
        assert "role" in result
        assert result["role"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_deviation(group_name="a", deviation_score=60.0)
        eng.record_deviation(group_name="b", deviation_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_deviation(group_name="a", deviation_score=50.0)
        eng.record_deviation(group_name="b", deviation_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["deviation_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_deviation(group_name="a", service="auth", deviation_score=90.0)
        eng.record_deviation(group_name="b", service="api", deviation_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(group_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(group_name="a", analysis_score=20.0)
        eng.add_analysis(group_name="b", analysis_score=20.0)
        eng.add_analysis(group_name="c", analysis_score=80.0)
        eng.add_analysis(group_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_deviation(group_name="test", deviation_score=50.0)
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
        eng.record_deviation(group_name="test")
        eng.add_analysis(group_name="test")
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
        eng.record_deviation(group_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
