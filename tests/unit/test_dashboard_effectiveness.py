"""Tests for shieldops.observability.dashboard_effectiveness — DashboardEffectivenessScorer."""

from __future__ import annotations

from shieldops.observability.dashboard_effectiveness import (
    DashboardEffectivenessReport,
    DashboardEffectivenessScorer,
    DashboardIssue,
    DashboardRecord,
    DashboardType,
    UsageFrequency,
    UsageMetric,
)


def _engine(**kw) -> DashboardEffectivenessScorer:
    return DashboardEffectivenessScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_operational(self):
        assert DashboardType.OPERATIONAL == "operational"

    def test_type_executive(self):
        assert DashboardType.EXECUTIVE == "executive"

    def test_type_security(self):
        assert DashboardType.SECURITY == "security"

    def test_type_compliance(self):
        assert DashboardType.COMPLIANCE == "compliance"

    def test_type_performance(self):
        assert DashboardType.PERFORMANCE == "performance"

    def test_frequency_daily(self):
        assert UsageFrequency.DAILY == "daily"

    def test_frequency_weekly(self):
        assert UsageFrequency.WEEKLY == "weekly"

    def test_frequency_monthly(self):
        assert UsageFrequency.MONTHLY == "monthly"

    def test_frequency_rarely(self):
        assert UsageFrequency.RARELY == "rarely"

    def test_frequency_never(self):
        assert UsageFrequency.NEVER == "never"

    def test_issue_stale_data(self):
        assert DashboardIssue.STALE_DATA == "stale_data"

    def test_issue_too_complex(self):
        assert DashboardIssue.TOO_COMPLEX == "too_complex"

    def test_issue_missing_context(self):
        assert DashboardIssue.MISSING_CONTEXT == "missing_context"

    def test_issue_wrong_audience(self):
        assert DashboardIssue.WRONG_AUDIENCE == "wrong_audience"

    def test_issue_no_actionability(self):
        assert DashboardIssue.NO_ACTIONABILITY == "no_actionability"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dashboard_record_defaults(self):
        r = DashboardRecord()
        assert r.id
        assert r.dashboard_name == ""
        assert r.dashboard_type == DashboardType.OPERATIONAL
        assert r.usage_frequency == UsageFrequency.WEEKLY
        assert r.dashboard_issue == DashboardIssue.STALE_DATA
        assert r.effectiveness_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_usage_metric_defaults(self):
        m = UsageMetric()
        assert m.id
        assert m.metric_name == ""
        assert m.dashboard_type == DashboardType.OPERATIONAL
        assert m.view_count == 0
        assert m.avg_session_duration == 0.0
        assert m.description == ""
        assert m.created_at > 0

    def test_dashboard_effectiveness_report_defaults(self):
        r = DashboardEffectivenessReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.ineffective_dashboards == 0
        assert r.avg_effectiveness_score == 0.0
        assert r.by_type == {}
        assert r.by_frequency == {}
        assert r.by_issue == {}
        assert r.top_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_dashboard
# ---------------------------------------------------------------------------


class TestRecordDashboard:
    def test_basic(self):
        eng = _engine()
        r = eng.record_dashboard(
            dashboard_name="sre-overview",
            dashboard_type=DashboardType.OPERATIONAL,
            usage_frequency=UsageFrequency.DAILY,
            dashboard_issue=DashboardIssue.STALE_DATA,
            effectiveness_score=85.0,
            team="sre",
        )
        assert r.dashboard_name == "sre-overview"
        assert r.dashboard_type == DashboardType.OPERATIONAL
        assert r.usage_frequency == UsageFrequency.DAILY
        assert r.dashboard_issue == DashboardIssue.STALE_DATA
        assert r.effectiveness_score == 85.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_dashboard(dashboard_name=f"dash-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_dashboard
# ---------------------------------------------------------------------------


class TestGetDashboard:
    def test_found(self):
        eng = _engine()
        r = eng.record_dashboard(
            dashboard_name="sre-overview",
            dashboard_type=DashboardType.SECURITY,
        )
        result = eng.get_dashboard(r.id)
        assert result is not None
        assert result.dashboard_type == DashboardType.SECURITY

    def test_not_found(self):
        eng = _engine()
        assert eng.get_dashboard("nonexistent") is None


# ---------------------------------------------------------------------------
# list_dashboards
# ---------------------------------------------------------------------------


class TestListDashboards:
    def test_list_all(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="dash-1")
        eng.record_dashboard(dashboard_name="dash-2")
        assert len(eng.list_dashboards()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_dashboard(
            dashboard_name="dash-1",
            dashboard_type=DashboardType.OPERATIONAL,
        )
        eng.record_dashboard(
            dashboard_name="dash-2",
            dashboard_type=DashboardType.EXECUTIVE,
        )
        results = eng.list_dashboards(dashboard_type=DashboardType.OPERATIONAL)
        assert len(results) == 1

    def test_filter_by_frequency(self):
        eng = _engine()
        eng.record_dashboard(
            dashboard_name="dash-1",
            usage_frequency=UsageFrequency.DAILY,
        )
        eng.record_dashboard(
            dashboard_name="dash-2",
            usage_frequency=UsageFrequency.NEVER,
        )
        results = eng.list_dashboards(frequency=UsageFrequency.DAILY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="dash-1", team="sre")
        eng.record_dashboard(dashboard_name="dash-2", team="platform")
        results = eng.list_dashboards(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_dashboard(dashboard_name=f"dash-{i}")
        assert len(eng.list_dashboards(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            metric_name="page-views",
            dashboard_type=DashboardType.OPERATIONAL,
            view_count=500,
            avg_session_duration=45.0,
            description="Page view metric",
        )
        assert m.metric_name == "page-views"
        assert m.dashboard_type == DashboardType.OPERATIONAL
        assert m.view_count == 500
        assert m.avg_session_duration == 45.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(metric_name=f"metric-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_dashboard_usage
# ---------------------------------------------------------------------------


class TestAnalyzeDashboardUsage:
    def test_with_data(self):
        eng = _engine()
        eng.record_dashboard(
            dashboard_name="dash-1",
            dashboard_type=DashboardType.OPERATIONAL,
            effectiveness_score=90.0,
        )
        eng.record_dashboard(
            dashboard_name="dash-2",
            dashboard_type=DashboardType.OPERATIONAL,
            effectiveness_score=80.0,
        )
        result = eng.analyze_dashboard_usage()
        assert "operational" in result
        assert result["operational"]["count"] == 2
        assert result["operational"]["avg_effectiveness_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_dashboard_usage() == {}


# ---------------------------------------------------------------------------
# identify_ineffective_dashboards
# ---------------------------------------------------------------------------


class TestIdentifyIneffectiveDashboards:
    def test_detects_rarely(self):
        eng = _engine()
        eng.record_dashboard(
            dashboard_name="dash-1",
            usage_frequency=UsageFrequency.RARELY,
            effectiveness_score=20.0,
        )
        eng.record_dashboard(
            dashboard_name="dash-2",
            usage_frequency=UsageFrequency.DAILY,
        )
        results = eng.identify_ineffective_dashboards()
        assert len(results) == 1
        assert results[0]["dashboard_name"] == "dash-1"

    def test_detects_never(self):
        eng = _engine()
        eng.record_dashboard(
            dashboard_name="dash-1",
            usage_frequency=UsageFrequency.NEVER,
        )
        results = eng.identify_ineffective_dashboards()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_ineffective_dashboards() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="d-1", team="sre", effectiveness_score=90.0)
        eng.record_dashboard(dashboard_name="d-2", team="sre", effectiveness_score=80.0)
        eng.record_dashboard(dashboard_name="d-3", team="platform", effectiveness_score=70.0)
        results = eng.rank_by_effectiveness()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_effectiveness_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# ---------------------------------------------------------------------------
# detect_usage_trends
# ---------------------------------------------------------------------------


class TestDetectUsageTrends:
    def test_stable(self):
        eng = _engine()
        for s in [30.0, 30.0, 30.0, 30.0]:
            eng.add_metric(metric_name="m", avg_session_duration=s)
        result = eng.detect_usage_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [20.0, 20.0, 60.0, 60.0]:
            eng.add_metric(metric_name="m", avg_session_duration=s)
        result = eng.detect_usage_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_usage_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_dashboard(
            dashboard_name="dash-1",
            dashboard_type=DashboardType.OPERATIONAL,
            usage_frequency=UsageFrequency.NEVER,
            effectiveness_score=40.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, DashboardEffectivenessReport)
        assert report.total_records == 1
        assert report.ineffective_dashboards == 1
        assert report.avg_effectiveness_score == 40.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable limits" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_dashboard(dashboard_name="dash-1")
        eng.add_metric(metric_name="m1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_dashboard(
            dashboard_name="dash-1",
            dashboard_type=DashboardType.OPERATIONAL,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_dashboards"] == 1
        assert "operational" in stats["type_distribution"]
