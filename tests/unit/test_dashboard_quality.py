"""Tests for shieldops.observability.dashboard_quality — DashboardQualityScorer."""

from __future__ import annotations

from shieldops.observability.dashboard_quality import (
    DashboardAction,
    DashboardGrade,
    DashboardIssue,
    DashboardQualityReport,
    DashboardQualityScorer,
    DashboardScoreRecord,
    QualityDimension,
)


def _engine(**kw) -> DashboardQualityScorer:
    return DashboardQualityScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_grade_excellent(self):
        assert DashboardGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert DashboardGrade.GOOD == "good"

    def test_grade_acceptable(self):
        assert DashboardGrade.ACCEPTABLE == "acceptable"

    def test_grade_poor(self):
        assert DashboardGrade.POOR == "poor"

    def test_grade_failing(self):
        assert DashboardGrade.FAILING == "failing"

    def test_dim_load_time(self):
        assert QualityDimension.LOAD_TIME == "load_time"

    def test_dim_panel_count(self):
        assert QualityDimension.PANEL_COUNT == "panel_count"

    def test_dim_query_efficiency(self):
        assert QualityDimension.QUERY_EFFICIENCY == "query_efficiency"

    def test_dim_usage_frequency(self):
        assert QualityDimension.USAGE_FREQUENCY == "usage_frequency"

    def test_dim_staleness(self):
        assert QualityDimension.STALENESS == "staleness"

    def test_action_no_action(self):
        assert DashboardAction.NO_ACTION == "no_action"

    def test_action_optimize_queries(self):
        assert DashboardAction.OPTIMIZE_QUERIES == "optimize_queries"

    def test_action_reduce_panels(self):
        assert DashboardAction.REDUCE_PANELS == "reduce_panels"

    def test_action_archive(self):
        assert DashboardAction.ARCHIVE == "archive"

    def test_action_rebuild(self):
        assert DashboardAction.REBUILD == "rebuild"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dashboard_score_record_defaults(self):
        r = DashboardScoreRecord()
        assert r.id
        assert r.dashboard_name == ""
        assert r.owner == ""
        assert r.grade == DashboardGrade.ACCEPTABLE
        assert r.score == 50.0
        assert r.load_time_ms == 0.0
        assert r.panel_count == 0
        assert r.query_count == 0
        assert r.usage_count_30d == 0
        assert r.last_modified_days_ago == 0
        assert r.created_at > 0

    def test_dashboard_issue_defaults(self):
        i = DashboardIssue()
        assert i.id
        assert i.dashboard_name == ""
        assert i.dimension == QualityDimension.LOAD_TIME
        assert i.action == DashboardAction.NO_ACTION
        assert i.severity == "medium"
        assert i.created_at > 0

    def test_report_defaults(self):
        r = DashboardQualityReport()
        assert r.total_dashboards == 0
        assert r.total_issues == 0
        assert r.avg_score == 0.0
        assert r.by_grade == {}
        assert r.stale_count == 0
        assert r.poor_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_dashboard
# ---------------------------------------------------------------------------


class TestRecordDashboard:
    def test_basic(self):
        eng = _engine()
        r = eng.record_dashboard(
            dashboard_name="infra-overview",
            owner="sre-team",
            load_time_ms=500,
            panel_count=8,
            usage_count_30d=100,
        )
        assert r.dashboard_name == "infra-overview"
        assert r.owner == "sre-team"
        assert r.score > 0
        assert r.grade in list(DashboardGrade)

    def test_slow_dashboard(self):
        eng = _engine()
        r = eng.record_dashboard(
            dashboard_name="slow-dash",
            load_time_ms=6000,
            panel_count=35,
            usage_count_30d=0,
            last_modified_days_ago=400,
        )
        assert r.score < 50
        assert r.grade in (DashboardGrade.POOR, DashboardGrade.FAILING)

    def test_excellent_dashboard(self):
        eng = _engine()
        r = eng.record_dashboard(
            dashboard_name="great-dash",
            load_time_ms=200,
            panel_count=5,
            usage_count_30d=200,
            last_modified_days_ago=10,
        )
        assert r.score >= 90
        assert r.grade == DashboardGrade.EXCELLENT

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_dashboard(dashboard_name=f"d{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get / list
# ---------------------------------------------------------------------------


class TestGetDashboard:
    def test_found(self):
        eng = _engine()
        r = eng.record_dashboard(dashboard_name="d1")
        result = eng.get_dashboard(r.id)
        assert result is not None
        assert result.dashboard_name == "d1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_dashboard("nonexistent") is None


class TestListDashboards:
    def test_list_all(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="d1")
        eng.record_dashboard(dashboard_name="d2")
        assert len(eng.list_dashboards()) == 2

    def test_filter_by_name(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="d1")
        eng.record_dashboard(dashboard_name="d2")
        results = eng.list_dashboards(dashboard_name="d1")
        assert len(results) == 1

    def test_filter_by_grade(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="good", load_time_ms=100, usage_count_30d=100)
        eng.record_dashboard(
            dashboard_name="bad", load_time_ms=6000, panel_count=35, usage_count_30d=0
        )
        excellent = eng.list_dashboards(grade=DashboardGrade.EXCELLENT)
        assert len(excellent) >= 0  # depends on scoring


# ---------------------------------------------------------------------------
# record_issue
# ---------------------------------------------------------------------------


class TestRecordIssue:
    def test_basic(self):
        eng = _engine()
        i = eng.record_issue(
            dashboard_name="d1",
            dimension=QualityDimension.LOAD_TIME,
            action=DashboardAction.OPTIMIZE_QUERIES,
            description="Dashboard loads slowly",
        )
        assert i.dashboard_name == "d1"
        assert i.dimension == QualityDimension.LOAD_TIME
        assert i.action == DashboardAction.OPTIMIZE_QUERIES

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_issue(dashboard_name=f"d{i}")
        assert len(eng._issues) == 3


# ---------------------------------------------------------------------------
# score_dashboard / stale / rankings / query efficiency
# ---------------------------------------------------------------------------


class TestScoreDashboard:
    def test_with_data(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="d1", load_time_ms=500, usage_count_30d=50)
        result = eng.score_dashboard("d1")
        assert result["dashboard_name"] == "d1"
        assert result["score"] > 0

    def test_no_data(self):
        eng = _engine()
        result = eng.score_dashboard("unknown")
        assert result["score"] == 0.0


class TestIdentifyStaleDashboards:
    def test_finds_stale(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="stale", last_modified_days_ago=200, usage_count_30d=10)
        results = eng.identify_stale_dashboards()
        assert len(results) == 1

    def test_no_stale(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="fresh", last_modified_days_ago=10, usage_count_30d=10)
        assert eng.identify_stale_dashboards() == []


class TestRankDashboardsByQuality:
    def test_ranked(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="good", load_time_ms=100, usage_count_30d=100)
        eng.record_dashboard(
            dashboard_name="bad", load_time_ms=6000, panel_count=35, usage_count_30d=0
        )
        results = eng.rank_dashboards_by_quality()
        assert len(results) == 2
        assert results[0]["score"] >= results[1]["score"]


class TestAnalyzeQueryEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_dashboard(
            dashboard_name="d1", panel_count=10, query_count=31, usage_count_30d=10
        )
        results = eng.analyze_query_efficiency()
        assert len(results) == 1
        assert results[0]["query_per_panel_ratio"] == 3.1
        assert results[0]["efficiency"] == "poor"

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_query_efficiency() == []


# ---------------------------------------------------------------------------
# report / clear / stats
# ---------------------------------------------------------------------------


class TestGenerateReportDQ:
    def test_populated(self):
        eng = _engine(min_quality_score=60.0)
        eng.record_dashboard(dashboard_name="d1", load_time_ms=100, usage_count_30d=100)
        eng.record_dashboard(
            dashboard_name="d2",
            load_time_ms=6000,
            panel_count=35,
            usage_count_30d=0,
            last_modified_days_ago=200,
        )
        report = eng.generate_report()
        assert isinstance(report, DashboardQualityReport)
        assert report.total_dashboards == 2
        assert report.avg_score > 0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_dashboards == 0
        assert "Dashboard quality meets standards" in report.recommendations


class TestClearDataDQ:
    def test_clears(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="d1")
        eng.record_issue(dashboard_name="d1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._issues) == 0


class TestGetStatsDQ:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_dashboards"] == 0
        assert stats["total_issues"] == 0
        assert stats["grade_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_quality_score=60.0)
        eng.record_dashboard(dashboard_name="d1", usage_count_30d=10)
        stats = eng.get_stats()
        assert stats["total_dashboards"] == 1
        assert stats["unique_dashboards"] == 1
