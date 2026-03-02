"""Tests for shieldops.security.soc_metrics_dashboard — SOCMetricsDashboard."""

from __future__ import annotations

from shieldops.security.soc_metrics_dashboard import (
    MetricAnalysis,
    MetricType,
    PerformanceLevel,
    SOCMetricRecord,
    SOCMetricsDashboard,
    SOCMetricsReport,
    SOCTier,
)


def _engine(**kw) -> SOCMetricsDashboard:
    return SOCMetricsDashboard(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_metric_type_mttd(self):
        assert MetricType.MTTD == "mttd"

    def test_metric_type_mttc(self):
        assert MetricType.MTTC == "mttc"

    def test_metric_type_mttr(self):
        assert MetricType.MTTR == "mttr"

    def test_metric_type_false_positive_rate(self):
        assert MetricType.FALSE_POSITIVE_RATE == "false_positive_rate"

    def test_metric_type_analyst_efficiency(self):
        assert MetricType.ANALYST_EFFICIENCY == "analyst_efficiency"

    def test_soc_tier_tier_1(self):
        assert SOCTier.TIER_1 == "tier_1"

    def test_soc_tier_tier_2(self):
        assert SOCTier.TIER_2 == "tier_2"

    def test_soc_tier_tier_3(self):
        assert SOCTier.TIER_3 == "tier_3"

    def test_soc_tier_automation(self):
        assert SOCTier.AUTOMATION == "automation"

    def test_soc_tier_management(self):
        assert SOCTier.MANAGEMENT == "management"

    def test_performance_excellent(self):
        assert PerformanceLevel.EXCELLENT == "excellent"

    def test_performance_good(self):
        assert PerformanceLevel.GOOD == "good"

    def test_performance_average(self):
        assert PerformanceLevel.AVERAGE == "average"

    def test_performance_below_average(self):
        assert PerformanceLevel.BELOW_AVERAGE == "below_average"

    def test_performance_critical(self):
        assert PerformanceLevel.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_soc_metric_record_defaults(self):
        r = SOCMetricRecord()
        assert r.id
        assert r.metric_name == ""
        assert r.metric_type == MetricType.MTTD
        assert r.soc_tier == SOCTier.TIER_1
        assert r.performance_level == PerformanceLevel.EXCELLENT
        assert r.metric_value == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_metric_analysis_defaults(self):
        c = MetricAnalysis()
        assert c.id
        assert c.metric_name == ""
        assert c.metric_type == MetricType.MTTD
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_soc_metrics_report_defaults(self):
        r = SOCMetricsReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.below_target_count == 0
        assert r.avg_metric_value == 0.0
        assert r.by_type == {}
        assert r.by_tier == {}
        assert r.by_performance == {}
        assert r.top_below_target == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_metric
# ---------------------------------------------------------------------------


class TestRecordMetric:
    def test_basic(self):
        eng = _engine()
        r = eng.record_metric(
            metric_name="mean-time-to-detect",
            metric_type=MetricType.MTTC,
            soc_tier=SOCTier.TIER_2,
            performance_level=PerformanceLevel.GOOD,
            metric_value=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.metric_name == "mean-time-to-detect"
        assert r.metric_type == MetricType.MTTC
        assert r.soc_tier == SOCTier.TIER_2
        assert r.performance_level == PerformanceLevel.GOOD
        assert r.metric_value == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_metric(metric_name=f"METRIC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_metric
# ---------------------------------------------------------------------------


class TestGetMetric:
    def test_found(self):
        eng = _engine()
        r = eng.record_metric(
            metric_name="mean-time-to-detect",
            performance_level=PerformanceLevel.EXCELLENT,
        )
        result = eng.get_metric(r.id)
        assert result is not None
        assert result.performance_level == PerformanceLevel.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_metric("nonexistent") is None


# ---------------------------------------------------------------------------
# list_metrics
# ---------------------------------------------------------------------------


class TestListMetrics:
    def test_list_all(self):
        eng = _engine()
        eng.record_metric(metric_name="METRIC-001")
        eng.record_metric(metric_name="METRIC-002")
        assert len(eng.list_metrics()) == 2

    def test_filter_by_metric_type(self):
        eng = _engine()
        eng.record_metric(
            metric_name="METRIC-001",
            metric_type=MetricType.MTTD,
        )
        eng.record_metric(
            metric_name="METRIC-002",
            metric_type=MetricType.MTTR,
        )
        results = eng.list_metrics(metric_type=MetricType.MTTD)
        assert len(results) == 1

    def test_filter_by_soc_tier(self):
        eng = _engine()
        eng.record_metric(
            metric_name="METRIC-001",
            soc_tier=SOCTier.TIER_1,
        )
        eng.record_metric(
            metric_name="METRIC-002",
            soc_tier=SOCTier.TIER_3,
        )
        results = eng.list_metrics(
            soc_tier=SOCTier.TIER_1,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_metric(metric_name="METRIC-001", team="security")
        eng.record_metric(metric_name="METRIC-002", team="platform")
        results = eng.list_metrics(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_metric(metric_name=f"METRIC-{i}")
        assert len(eng.list_metrics(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            metric_name="mean-time-to-detect",
            metric_type=MetricType.MTTC,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="metric below target",
        )
        assert a.metric_name == "mean-time-to-detect"
        assert a.metric_type == MetricType.MTTC
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(metric_name=f"METRIC-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_metric_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeMetricDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_metric(
            metric_name="METRIC-001",
            metric_type=MetricType.MTTD,
            metric_value=90.0,
        )
        eng.record_metric(
            metric_name="METRIC-002",
            metric_type=MetricType.MTTD,
            metric_value=70.0,
        )
        result = eng.analyze_metric_distribution()
        assert "mttd" in result
        assert result["mttd"]["count"] == 2
        assert result["mttd"]["avg_metric_value"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_metric_distribution() == {}


# ---------------------------------------------------------------------------
# identify_below_target_metrics
# ---------------------------------------------------------------------------


class TestIdentifyBelowTargetMetrics:
    def test_detects_below_threshold(self):
        eng = _engine(metric_target_threshold=80.0)
        eng.record_metric(metric_name="METRIC-001", metric_value=60.0)
        eng.record_metric(metric_name="METRIC-002", metric_value=90.0)
        results = eng.identify_below_target_metrics()
        assert len(results) == 1
        assert results[0]["metric_name"] == "METRIC-001"

    def test_sorted_ascending(self):
        eng = _engine(metric_target_threshold=80.0)
        eng.record_metric(metric_name="METRIC-001", metric_value=50.0)
        eng.record_metric(metric_name="METRIC-002", metric_value=30.0)
        results = eng.identify_below_target_metrics()
        assert len(results) == 2
        assert results[0]["metric_value"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_below_target_metrics() == []


# ---------------------------------------------------------------------------
# rank_by_metric_value
# ---------------------------------------------------------------------------


class TestRankByMetricValue:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_metric(metric_name="METRIC-001", service="auth-svc", metric_value=90.0)
        eng.record_metric(metric_name="METRIC-002", service="api-gw", metric_value=50.0)
        results = eng.rank_by_metric_value()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_metric_value"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_metric_value() == []


# ---------------------------------------------------------------------------
# detect_metric_trends
# ---------------------------------------------------------------------------


class TestDetectMetricTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(metric_name="METRIC-001", analysis_score=50.0)
        result = eng.detect_metric_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(metric_name="METRIC-001", analysis_score=20.0)
        eng.add_analysis(metric_name="METRIC-002", analysis_score=20.0)
        eng.add_analysis(metric_name="METRIC-003", analysis_score=80.0)
        eng.add_analysis(metric_name="METRIC-004", analysis_score=80.0)
        result = eng.detect_metric_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_metric_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(metric_target_threshold=80.0)
        eng.record_metric(
            metric_name="mean-time-to-detect",
            metric_type=MetricType.MTTC,
            soc_tier=SOCTier.TIER_2,
            performance_level=PerformanceLevel.GOOD,
            metric_value=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SOCMetricsReport)
        assert report.total_records == 1
        assert report.below_target_count == 1
        assert len(report.top_below_target) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_metric(metric_name="METRIC-001")
        eng.add_analysis(metric_name="METRIC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_metric(
            metric_name="METRIC-001",
            metric_type=MetricType.MTTD,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "mttd" in stats["type_distribution"]
