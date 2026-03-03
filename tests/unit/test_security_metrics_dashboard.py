"""Tests for shieldops.compliance.security_metrics_dashboard — SecurityMetricsDashboard."""

from __future__ import annotations

from shieldops.compliance.security_metrics_dashboard import (
    MetricAnalysis,
    MetricCategory,
    MetricRecord,
    MetricStatus,
    MetricTimeframe,
    SecurityMetricsDashboard,
    SecurityMetricsReport,
)


def _engine(**kw) -> SecurityMetricsDashboard:
    return SecurityMetricsDashboard(**kw)


class TestEnums:
    def test_category_vulnerability(self):
        assert MetricCategory.VULNERABILITY == "vulnerability"

    def test_category_incident(self):
        assert MetricCategory.INCIDENT == "incident"

    def test_category_compliance(self):
        assert MetricCategory.COMPLIANCE == "compliance"

    def test_category_access(self):
        assert MetricCategory.ACCESS == "access"

    def test_category_threat(self):
        assert MetricCategory.THREAT == "threat"

    def test_timeframe_realtime(self):
        assert MetricTimeframe.REALTIME == "realtime"

    def test_timeframe_daily(self):
        assert MetricTimeframe.DAILY == "daily"

    def test_timeframe_weekly(self):
        assert MetricTimeframe.WEEKLY == "weekly"

    def test_timeframe_monthly(self):
        assert MetricTimeframe.MONTHLY == "monthly"

    def test_timeframe_quarterly(self):
        assert MetricTimeframe.QUARTERLY == "quarterly"

    def test_status_on_target(self):
        assert MetricStatus.ON_TARGET == "on_target"

    def test_status_at_risk(self):
        assert MetricStatus.AT_RISK == "at_risk"

    def test_status_off_target(self):
        assert MetricStatus.OFF_TARGET == "off_target"

    def test_status_improving(self):
        assert MetricStatus.IMPROVING == "improving"

    def test_status_degrading(self):
        assert MetricStatus.DEGRADING == "degrading"


class TestModels:
    def test_record_defaults(self):
        r = MetricRecord()
        assert r.id
        assert r.metric_name == ""
        assert r.metric_category == MetricCategory.VULNERABILITY
        assert r.metric_timeframe == MetricTimeframe.REALTIME
        assert r.metric_status == MetricStatus.ON_TARGET
        assert r.metric_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = MetricAnalysis()
        assert a.id
        assert a.metric_name == ""
        assert a.metric_category == MetricCategory.VULNERABILITY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = SecurityMetricsReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_metric_score == 0.0
        assert r.by_category == {}
        assert r.by_timeframe == {}
        assert r.by_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_metric(
            metric_name="mttr-critical",
            metric_category=MetricCategory.INCIDENT,
            metric_timeframe=MetricTimeframe.MONTHLY,
            metric_status=MetricStatus.AT_RISK,
            metric_score=85.0,
            service="dashboard-svc",
            team="security",
        )
        assert r.metric_name == "mttr-critical"
        assert r.metric_category == MetricCategory.INCIDENT
        assert r.metric_score == 85.0
        assert r.service == "dashboard-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_metric(metric_name=f"met-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_metric(metric_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_metric(metric_name="a")
        eng.record_metric(metric_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_metric_category(self):
        eng = _engine()
        eng.record_metric(metric_name="a", metric_category=MetricCategory.VULNERABILITY)
        eng.record_metric(metric_name="b", metric_category=MetricCategory.INCIDENT)
        assert len(eng.list_records(metric_category=MetricCategory.VULNERABILITY)) == 1

    def test_filter_by_metric_status(self):
        eng = _engine()
        eng.record_metric(metric_name="a", metric_status=MetricStatus.ON_TARGET)
        eng.record_metric(metric_name="b", metric_status=MetricStatus.AT_RISK)
        assert len(eng.list_records(metric_status=MetricStatus.ON_TARGET)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_metric(metric_name="a", team="sec")
        eng.record_metric(metric_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_metric(metric_name=f"m-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            metric_name="test",
            analysis_score=88.5,
            breached=True,
            description="metric off target",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(metric_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_metric(
            metric_name="a",
            metric_category=MetricCategory.VULNERABILITY,
            metric_score=90.0,
        )
        eng.record_metric(
            metric_name="b",
            metric_category=MetricCategory.VULNERABILITY,
            metric_score=70.0,
        )
        result = eng.analyze_distribution()
        assert "vulnerability" in result
        assert result["vulnerability"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_metric(metric_name="a", metric_score=60.0)
        eng.record_metric(metric_name="b", metric_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_metric(metric_name="a", metric_score=50.0)
        eng.record_metric(metric_name="b", metric_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["metric_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_metric(metric_name="a", service="auth", metric_score=90.0)
        eng.record_metric(metric_name="b", service="api", metric_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(metric_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(metric_name="a", analysis_score=20.0)
        eng.add_analysis(metric_name="b", analysis_score=20.0)
        eng.add_analysis(metric_name="c", analysis_score=80.0)
        eng.add_analysis(metric_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_metric(metric_name="test", metric_score=50.0)
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
        eng.record_metric(metric_name="test")
        eng.add_analysis(metric_name="test")
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
        eng.record_metric(metric_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
