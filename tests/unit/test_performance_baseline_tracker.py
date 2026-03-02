"""Tests for shieldops.analytics.performance_baseline_tracker — PerformanceBaselineTracker."""

from __future__ import annotations

from shieldops.analytics.performance_baseline_tracker import (
    BaselineComparison,
    BaselineMetric,
    BaselineRecord,
    BaselineShift,
    BaselineWindow,
    PerformanceBaselineReport,
    PerformanceBaselineTracker,
)


def _engine(**kw) -> PerformanceBaselineTracker:
    return PerformanceBaselineTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_metric_latency_p50(self):
        assert BaselineMetric.LATENCY_P50 == "latency_p50"

    def test_metric_latency_p99(self):
        assert BaselineMetric.LATENCY_P99 == "latency_p99"

    def test_metric_throughput_rps(self):
        assert BaselineMetric.THROUGHPUT_RPS == "throughput_rps"

    def test_metric_error_rate(self):
        assert BaselineMetric.ERROR_RATE == "error_rate"

    def test_metric_resource_utilization(self):
        assert BaselineMetric.RESOURCE_UTILIZATION == "resource_utilization"

    def test_shift_significant_improvement(self):
        assert BaselineShift.SIGNIFICANT_IMPROVEMENT == "significant_improvement"

    def test_shift_minor_improvement(self):
        assert BaselineShift.MINOR_IMPROVEMENT == "minor_improvement"

    def test_shift_stable(self):
        assert BaselineShift.STABLE == "stable"

    def test_shift_minor_degradation(self):
        assert BaselineShift.MINOR_DEGRADATION == "minor_degradation"

    def test_shift_significant_degradation(self):
        assert BaselineShift.SIGNIFICANT_DEGRADATION == "significant_degradation"

    def test_window_hourly(self):
        assert BaselineWindow.HOURLY == "hourly"

    def test_window_daily(self):
        assert BaselineWindow.DAILY == "daily"

    def test_window_weekly(self):
        assert BaselineWindow.WEEKLY == "weekly"

    def test_window_monthly(self):
        assert BaselineWindow.MONTHLY == "monthly"

    def test_window_quarterly(self):
        assert BaselineWindow.QUARTERLY == "quarterly"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_baseline_record_defaults(self):
        r = BaselineRecord()
        assert r.id
        assert r.service_name == ""
        assert r.baseline_metric == BaselineMetric.LATENCY_P50
        assert r.baseline_shift == BaselineShift.SIGNIFICANT_IMPROVEMENT
        assert r.baseline_window == BaselineWindow.HOURLY
        assert r.deviation_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_baseline_comparison_defaults(self):
        c = BaselineComparison()
        assert c.id
        assert c.service_name == ""
        assert c.baseline_metric == BaselineMetric.LATENCY_P50
        assert c.comparison_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_baseline_report_defaults(self):
        r = PerformanceBaselineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_comparisons == 0
        assert r.high_deviation_count == 0
        assert r.avg_deviation_score == 0.0
        assert r.by_metric == {}
        assert r.by_shift == {}
        assert r.by_window == {}
        assert r.top_deviations == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_baseline
# ---------------------------------------------------------------------------


class TestRecordBaseline:
    def test_basic(self):
        eng = _engine()
        r = eng.record_baseline(
            service_name="api-gateway",
            baseline_metric=BaselineMetric.LATENCY_P99,
            baseline_shift=BaselineShift.MINOR_DEGRADATION,
            baseline_window=BaselineWindow.DAILY,
            deviation_score=3.5,
            service="api-gateway",
            team="sre",
        )
        assert r.service_name == "api-gateway"
        assert r.baseline_metric == BaselineMetric.LATENCY_P99
        assert r.baseline_shift == BaselineShift.MINOR_DEGRADATION
        assert r.baseline_window == BaselineWindow.DAILY
        assert r.deviation_score == 3.5
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_baseline(service_name=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_baseline
# ---------------------------------------------------------------------------


class TestGetBaseline:
    def test_found(self):
        eng = _engine()
        r = eng.record_baseline(
            service_name="api-gateway",
            baseline_metric=BaselineMetric.ERROR_RATE,
        )
        result = eng.get_baseline(r.id)
        assert result is not None
        assert result.baseline_metric == BaselineMetric.ERROR_RATE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_baseline("nonexistent") is None


# ---------------------------------------------------------------------------
# list_baselines
# ---------------------------------------------------------------------------


class TestListBaselines:
    def test_list_all(self):
        eng = _engine()
        eng.record_baseline(service_name="svc-001")
        eng.record_baseline(service_name="svc-002")
        assert len(eng.list_baselines()) == 2

    def test_filter_by_metric(self):
        eng = _engine()
        eng.record_baseline(
            service_name="svc-001",
            baseline_metric=BaselineMetric.LATENCY_P50,
        )
        eng.record_baseline(
            service_name="svc-002",
            baseline_metric=BaselineMetric.THROUGHPUT_RPS,
        )
        results = eng.list_baselines(baseline_metric=BaselineMetric.LATENCY_P50)
        assert len(results) == 1

    def test_filter_by_shift(self):
        eng = _engine()
        eng.record_baseline(
            service_name="svc-001",
            baseline_shift=BaselineShift.STABLE,
        )
        eng.record_baseline(
            service_name="svc-002",
            baseline_shift=BaselineShift.SIGNIFICANT_DEGRADATION,
        )
        results = eng.list_baselines(baseline_shift=BaselineShift.STABLE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_baseline(service_name="svc-001", team="sre")
        eng.record_baseline(service_name="svc-002", team="platform")
        results = eng.list_baselines(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_baseline(service_name=f"svc-{i}")
        assert len(eng.list_baselines(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_comparison
# ---------------------------------------------------------------------------


class TestAddComparison:
    def test_basic(self):
        eng = _engine()
        c = eng.add_comparison(
            service_name="api-gateway",
            baseline_metric=BaselineMetric.ERROR_RATE,
            comparison_score=72.0,
            threshold=70.0,
            breached=True,
            description="Deviation above target",
        )
        assert c.service_name == "api-gateway"
        assert c.baseline_metric == BaselineMetric.ERROR_RATE
        assert c.comparison_score == 72.0
        assert c.threshold == 70.0
        assert c.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_comparison(service_name=f"svc-{i}")
        assert len(eng._comparisons) == 2


# ---------------------------------------------------------------------------
# analyze_baseline_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeBaselineDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_baseline(
            service_name="svc-001",
            baseline_metric=BaselineMetric.LATENCY_P50,
            deviation_score=1.5,
        )
        eng.record_baseline(
            service_name="svc-002",
            baseline_metric=BaselineMetric.LATENCY_P50,
            deviation_score=2.5,
        )
        result = eng.analyze_baseline_distribution()
        assert "latency_p50" in result
        assert result["latency_p50"]["count"] == 2
        assert result["latency_p50"]["avg_deviation_score"] == 2.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_baseline_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_deviations
# ---------------------------------------------------------------------------


class TestIdentifyHighDeviations:
    def test_detects_high(self):
        eng = _engine(deviation_threshold=2.0)
        eng.record_baseline(
            service_name="svc-001",
            deviation_score=3.5,
        )
        eng.record_baseline(
            service_name="svc-002",
            deviation_score=1.0,
        )
        results = eng.identify_high_deviations()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-001"

    def test_sorted_descending(self):
        eng = _engine(deviation_threshold=2.0)
        eng.record_baseline(service_name="svc-001", deviation_score=3.0)
        eng.record_baseline(service_name="svc-002", deviation_score=5.0)
        results = eng.identify_high_deviations()
        assert len(results) == 2
        assert results[0]["deviation_score"] == 5.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_deviations() == []


# ---------------------------------------------------------------------------
# rank_by_deviation
# ---------------------------------------------------------------------------


class TestRankByDeviation:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_baseline(service_name="svc-001", deviation_score=1.0, service="svc-a")
        eng.record_baseline(service_name="svc-002", deviation_score=5.0, service="svc-b")
        results = eng.rank_by_deviation()
        assert len(results) == 2
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_deviation_score"] == 5.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_deviation() == []


# ---------------------------------------------------------------------------
# detect_baseline_trends
# ---------------------------------------------------------------------------


class TestDetectBaselineTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_comparison(service_name="svc-001", comparison_score=70.0)
        result = eng.detect_baseline_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_comparison(service_name="svc-001", comparison_score=50.0)
        eng.add_comparison(service_name="svc-002", comparison_score=50.0)
        eng.add_comparison(service_name="svc-003", comparison_score=80.0)
        eng.add_comparison(service_name="svc-004", comparison_score=80.0)
        result = eng.detect_baseline_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_baseline_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(deviation_threshold=2.0)
        eng.record_baseline(
            service_name="api-gateway",
            baseline_metric=BaselineMetric.LATENCY_P99,
            baseline_shift=BaselineShift.SIGNIFICANT_DEGRADATION,
            deviation_score=4.0,
        )
        report = eng.generate_report()
        assert isinstance(report, PerformanceBaselineReport)
        assert report.total_records == 1
        assert report.high_deviation_count == 1
        assert len(report.top_deviations) == 1
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
        eng.record_baseline(service_name="svc-001")
        eng.add_comparison(service_name="svc-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._comparisons) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_comparisons"] == 0
        assert stats["metric_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_baseline(
            service_name="svc-001",
            baseline_metric=BaselineMetric.LATENCY_P50,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "latency_p50" in stats["metric_distribution"]
