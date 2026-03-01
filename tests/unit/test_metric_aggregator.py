"""Tests for shieldops.operations.metric_aggregator — OperationalMetricAggregator."""

from __future__ import annotations

from shieldops.operations.metric_aggregator import (
    AggregationLevel,
    MetricDomain,
    MetricRecord,
    MetricThreshold,
    MetricTrend,
    OperationalMetricAggregator,
    OperationalMetricReport,
)


def _engine(**kw) -> OperationalMetricAggregator:
    return OperationalMetricAggregator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_domain_reliability(self):
        assert MetricDomain.RELIABILITY == "reliability"

    def test_domain_performance(self):
        assert MetricDomain.PERFORMANCE == "performance"

    def test_domain_efficiency(self):
        assert MetricDomain.EFFICIENCY == "efficiency"

    def test_domain_security(self):
        assert MetricDomain.SECURITY == "security"

    def test_domain_cost(self):
        assert MetricDomain.COST == "cost"

    def test_level_platform(self):
        assert AggregationLevel.PLATFORM == "platform"

    def test_level_team(self):
        assert AggregationLevel.TEAM == "team"

    def test_level_service(self):
        assert AggregationLevel.SERVICE == "service"

    def test_level_environment(self):
        assert AggregationLevel.ENVIRONMENT == "environment"

    def test_level_component(self):
        assert AggregationLevel.COMPONENT == "component"

    def test_trend_improving(self):
        assert MetricTrend.IMPROVING == "improving"

    def test_trend_stable(self):
        assert MetricTrend.STABLE == "stable"

    def test_trend_degrading(self):
        assert MetricTrend.DEGRADING == "degrading"

    def test_trend_volatile(self):
        assert MetricTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert MetricTrend.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_metric_record_defaults(self):
        r = MetricRecord()
        assert r.id
        assert r.metric_name == ""
        assert r.domain == MetricDomain.RELIABILITY
        assert r.aggregation_level == AggregationLevel.PLATFORM
        assert r.value == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_metric_threshold_defaults(self):
        t = MetricThreshold()
        assert t.id
        assert t.metric_pattern == ""
        assert t.domain == MetricDomain.RELIABILITY
        assert t.aggregation_level == AggregationLevel.PLATFORM
        assert t.min_value == 0.0
        assert t.max_value == 0.0
        assert t.reason == ""
        assert t.created_at > 0

    def test_metric_report_defaults(self):
        r = OperationalMetricReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_thresholds == 0
        assert r.breached_count == 0
        assert r.avg_metric_value == 0.0
        assert r.by_domain == {}
        assert r.by_level == {}
        assert r.by_trend == {}
        assert r.breached_metrics == []
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
            metric_name="availability",
            domain=MetricDomain.RELIABILITY,
            aggregation_level=AggregationLevel.SERVICE,
            value=99.5,
            team="sre",
        )
        assert r.metric_name == "availability"
        assert r.domain == MetricDomain.RELIABILITY
        assert r.aggregation_level == AggregationLevel.SERVICE
        assert r.value == 99.5
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_metric(metric_name=f"metric-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_metric
# ---------------------------------------------------------------------------


class TestGetMetric:
    def test_found(self):
        eng = _engine()
        r = eng.record_metric(metric_name="latency", value=42.0)
        result = eng.get_metric(r.id)
        assert result is not None
        assert result.value == 42.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_metric("nonexistent") is None


# ---------------------------------------------------------------------------
# list_metrics
# ---------------------------------------------------------------------------


class TestListMetrics:
    def test_list_all(self):
        eng = _engine()
        eng.record_metric(metric_name="m1")
        eng.record_metric(metric_name="m2")
        assert len(eng.list_metrics()) == 2

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_metric(
            metric_name="m1",
            domain=MetricDomain.RELIABILITY,
        )
        eng.record_metric(
            metric_name="m2",
            domain=MetricDomain.COST,
        )
        results = eng.list_metrics(
            domain=MetricDomain.RELIABILITY,
        )
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_metric(
            metric_name="m1",
            aggregation_level=AggregationLevel.PLATFORM,
        )
        eng.record_metric(
            metric_name="m2",
            aggregation_level=AggregationLevel.TEAM,
        )
        results = eng.list_metrics(
            aggregation_level=AggregationLevel.PLATFORM,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_metric(metric_name="m1", team="sre")
        eng.record_metric(metric_name="m2", team="platform")
        results = eng.list_metrics(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_metric(metric_name=f"m-{i}")
        assert len(eng.list_metrics(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_threshold
# ---------------------------------------------------------------------------


class TestAddThreshold:
    def test_basic(self):
        eng = _engine()
        t = eng.add_threshold(
            metric_pattern="latency",
            domain=MetricDomain.PERFORMANCE,
            min_value=0.0,
            max_value=100.0,
            reason="SLA requirement",
        )
        assert t.metric_pattern == "latency"
        assert t.domain == MetricDomain.PERFORMANCE
        assert t.max_value == 100.0
        assert t.reason == "SLA requirement"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_threshold(metric_pattern=f"pat-{i}")
        assert len(eng._thresholds) == 2


# ---------------------------------------------------------------------------
# analyze_metric_health
# ---------------------------------------------------------------------------


class TestAnalyzeMetricHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_metric(
            metric_name="m1",
            domain=MetricDomain.RELIABILITY,
            value=95.0,
        )
        eng.record_metric(
            metric_name="m2",
            domain=MetricDomain.RELIABILITY,
            value=85.0,
        )
        result = eng.analyze_metric_health()
        assert "reliability" in result
        assert result["reliability"]["count"] == 2
        assert result["reliability"]["avg_value"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_metric_health() == {}


# ---------------------------------------------------------------------------
# identify_breached_thresholds
# ---------------------------------------------------------------------------


class TestIdentifyBreachedThresholds:
    def test_detects_breach(self):
        eng = _engine()
        eng.add_threshold(
            metric_pattern="latency",
            min_value=0.0,
            max_value=100.0,
        )
        eng.record_metric(metric_name="latency-p99", value=150.0)
        results = eng.identify_breached_thresholds()
        assert len(results) == 1
        assert results[0]["metric_name"] == "latency-p99"

    def test_no_breach(self):
        eng = _engine()
        eng.add_threshold(
            metric_pattern="latency",
            min_value=0.0,
            max_value=200.0,
        )
        eng.record_metric(metric_name="latency-p99", value=50.0)
        results = eng.identify_breached_thresholds()
        assert len(results) == 0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_breached_thresholds() == []


# ---------------------------------------------------------------------------
# rank_by_metric_value
# ---------------------------------------------------------------------------


class TestRankByMetricValue:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_metric(metric_name="m1", team="sre", value=95.0)
        eng.record_metric(
            metric_name="m2",
            team="platform",
            value=85.0,
        )
        results = eng.rank_by_metric_value()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_value"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_metric_value() == []


# ---------------------------------------------------------------------------
# detect_metric_trends
# ---------------------------------------------------------------------------


class TestDetectMetricTrends:
    def test_stable(self):
        eng = _engine()
        for val in [80.0, 80.0, 80.0, 80.0]:
            eng.record_metric(metric_name="m1", value=val)
        result = eng.detect_metric_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for val in [50.0, 50.0, 90.0, 90.0]:
            eng.record_metric(metric_name="m1", value=val)
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
        eng = _engine()
        eng.add_threshold(
            metric_pattern="latency",
            min_value=0.0,
            max_value=100.0,
        )
        eng.record_metric(
            metric_name="latency-p99",
            domain=MetricDomain.PERFORMANCE,
            value=150.0,
        )
        report = eng.generate_report()
        assert isinstance(report, OperationalMetricReport)
        assert report.total_records == 1
        assert report.breached_count == 1
        assert len(report.breached_metrics) == 1
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
        eng.record_metric(metric_name="m1")
        eng.add_threshold(metric_pattern="pat-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._thresholds) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_thresholds"] == 0
        assert stats["domain_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_metric(
            metric_name="m1",
            domain=MetricDomain.RELIABILITY,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_metrics"] == 1
        assert "reliability" in stats["domain_distribution"]
