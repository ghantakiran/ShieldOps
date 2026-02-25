"""Tests for shieldops.analytics.perf_regression."""

from __future__ import annotations

from shieldops.analytics.perf_regression import (
    ComparisonMethod,
    MetricCategory,
    PerformanceRegressionDetector,
    RegressionBaseline,
    RegressionReport,
    RegressionSeverity,
    RegressionTest,
)


def _engine(**kw) -> PerformanceRegressionDetector:
    return PerformanceRegressionDetector(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # RegressionSeverity (5 values)

    def test_severity_none(self):
        assert RegressionSeverity.NONE == "none"

    def test_severity_minor(self):
        assert RegressionSeverity.MINOR == "minor"

    def test_severity_moderate(self):
        assert RegressionSeverity.MODERATE == "moderate"

    def test_severity_major(self):
        assert RegressionSeverity.MAJOR == "major"

    def test_severity_critical(self):
        assert RegressionSeverity.CRITICAL == "critical"

    # MetricCategory (5 values)

    def test_category_latency(self):
        assert MetricCategory.LATENCY == "latency"

    def test_category_throughput(self):
        assert MetricCategory.THROUGHPUT == "throughput"

    def test_category_error_rate(self):
        assert MetricCategory.ERROR_RATE == "error_rate"

    def test_category_cpu_usage(self):
        assert MetricCategory.CPU_USAGE == "cpu_usage"

    def test_category_memory_usage(self):
        assert MetricCategory.MEMORY_USAGE == "memory_usage"

    # ComparisonMethod (5 values)

    def test_method_mean_shift(self):
        assert ComparisonMethod.MEAN_SHIFT == "mean_shift"

    def test_method_percentile_shift(self):
        assert ComparisonMethod.PERCENTILE_SHIFT == "percentile_shift"

    def test_method_variance_change(self):
        assert ComparisonMethod.VARIANCE_CHANGE == "variance_change"

    def test_method_trend_break(self):
        assert ComparisonMethod.TREND_BREAK == "trend_break"

    def test_method_distribution_shift(self):
        assert ComparisonMethod.DISTRIBUTION_SHIFT == "distribution_shift"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_regression_test_defaults(self):
        rt = RegressionTest()
        assert rt.id
        assert rt.service_name == ""
        assert rt.deployment_id == ""
        assert rt.metric_category == MetricCategory.LATENCY
        assert rt.before_value == 0.0
        assert rt.after_value == 0.0
        assert rt.change_pct == 0.0
        assert rt.severity == RegressionSeverity.NONE
        assert rt.method == ComparisonMethod.MEAN_SHIFT
        assert rt.is_significant is False
        assert rt.created_at > 0

    def test_regression_baseline_defaults(self):
        rb = RegressionBaseline()
        assert rb.id
        assert rb.service_name == ""
        assert rb.metric_category == MetricCategory.LATENCY
        assert rb.baseline_mean == 0.0
        assert rb.baseline_p95 == 0.0
        assert rb.baseline_std == 0.0
        assert rb.sample_count == 0
        assert rb.created_at > 0

    def test_regression_report_defaults(self):
        rr = RegressionReport()
        assert rr.total_tests == 0
        assert rr.regressions_found == 0
        assert rr.regression_rate_pct == 0.0
        assert rr.by_severity == {}
        assert rr.by_category == {}
        assert rr.by_method == {}
        assert rr.top_regressions == []
        assert rr.recommendations == []
        assert rr.generated_at > 0


# -------------------------------------------------------------------
# run_test
# -------------------------------------------------------------------


class TestRunTest:
    def test_basic_run(self):
        eng = _engine()
        t = eng.run_test("svc-a", "deploy-1")
        assert t.service_name == "svc-a"
        assert t.deployment_id == "deploy-1"
        assert len(eng.list_tests()) == 1

    def test_run_assigns_unique_ids(self):
        eng = _engine()
        t1 = eng.run_test("svc-a")
        t2 = eng.run_test("svc-b")
        assert t1.id != t2.id

    def test_change_pct_calculated(self):
        eng = _engine()
        t = eng.run_test(
            "svc-a",
            before_value=100.0,
            after_value=150.0,
        )
        assert t.change_pct == 50.0

    def test_severity_assigned(self):
        eng = _engine()
        t = eng.run_test(
            "svc-a",
            before_value=100.0,
            after_value=300.0,
        )
        assert t.severity == RegressionSeverity.CRITICAL

    def test_eviction_at_max(self):
        eng = _engine(max_tests=3)
        ids = []
        for i in range(4):
            t = eng.run_test(f"svc-{i}")
            ids.append(t.id)
        tests = eng.list_tests(limit=100)
        assert len(tests) == 3
        found = {t.id for t in tests}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_test
# -------------------------------------------------------------------


class TestGetTest:
    def test_get_existing(self):
        eng = _engine()
        t = eng.run_test("svc-a")
        found = eng.get_test(t.id)
        assert found is not None
        assert found.id == t.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_test("nonexistent") is None


# -------------------------------------------------------------------
# list_tests
# -------------------------------------------------------------------


class TestListTests:
    def test_list_all(self):
        eng = _engine()
        eng.run_test("svc-a")
        eng.run_test("svc-b")
        eng.run_test("svc-c")
        assert len(eng.list_tests()) == 3

    def test_filter_by_service(self):
        eng = _engine()
        eng.run_test("svc-a")
        eng.run_test("svc-b")
        eng.run_test("svc-a")
        results = eng.list_tests(service_name="svc-a")
        assert len(results) == 2

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.run_test(f"svc-{i}")
        results = eng.list_tests(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# create_baseline
# -------------------------------------------------------------------


class TestCreateBaseline:
    def test_basic_baseline(self):
        eng = _engine()
        bl = eng.create_baseline(
            "svc-a",
            values=[10.0, 20.0, 30.0, 40.0, 50.0],
        )
        assert bl.service_name == "svc-a"
        assert bl.baseline_mean == 30.0
        assert bl.sample_count == 5

    def test_empty_values(self):
        eng = _engine()
        bl = eng.create_baseline("svc-a")
        assert bl.baseline_mean == 0.0
        assert bl.sample_count == 0

    def test_baseline_p95(self):
        eng = _engine()
        vals = list(range(1, 101))
        bl = eng.create_baseline(
            "svc-a",
            values=[float(v) for v in vals],
        )
        assert bl.baseline_p95 == 96.0


# -------------------------------------------------------------------
# detect_regression
# -------------------------------------------------------------------


class TestDetectRegression:
    def test_detect_existing(self):
        eng = _engine()
        t = eng.run_test(
            "svc-a",
            before_value=100.0,
            after_value=250.0,
        )
        result = eng.detect_regression(t.id)
        assert result is not None
        assert result["is_regression"] is True

    def test_detect_not_found(self):
        eng = _engine()
        assert eng.detect_regression("nope") is None

    def test_detect_no_regression(self):
        eng = _engine()
        t = eng.run_test(
            "svc-a",
            before_value=100.0,
            after_value=101.0,
        )
        result = eng.detect_regression(t.id)
        assert result is not None
        assert result["is_regression"] is False


# -------------------------------------------------------------------
# compare_deployments
# -------------------------------------------------------------------


class TestCompareDeployments:
    def test_comparison(self):
        eng = _engine()
        eng.run_test(
            "svc-a",
            "deploy-1",
            after_value=100.0,
        )
        eng.run_test(
            "svc-a",
            "deploy-2",
            after_value=200.0,
        )
        comps = eng.compare_deployments(
            "deploy-1",
            "deploy-2",
        )
        assert len(comps) == 1
        assert comps[0]["service_name"] == "svc-a"

    def test_empty_comparison(self):
        eng = _engine()
        comps = eng.compare_deployments("a", "b")
        assert comps == []


# -------------------------------------------------------------------
# identify_degrading_services
# -------------------------------------------------------------------


class TestIdentifyDegradingServices:
    def test_degrading_detected(self):
        eng = _engine()
        eng.run_test(
            "svc-a",
            before_value=100.0,
            after_value=250.0,
        )
        eng.run_test(
            "svc-a",
            before_value=100.0,
            after_value=300.0,
        )
        degrading = eng.identify_degrading_services()
        assert len(degrading) == 1
        assert degrading[0]["service_name"] == "svc-a"

    def test_no_degrading(self):
        eng = _engine()
        eng.run_test(
            "svc-a",
            before_value=100.0,
            after_value=101.0,
        )
        degrading = eng.identify_degrading_services()
        assert degrading == []


# -------------------------------------------------------------------
# calculate_false_positive_rate
# -------------------------------------------------------------------


class TestCalculateFalsePositiveRate:
    def test_no_significant(self):
        eng = _engine()
        eng.run_test(
            "svc-a",
            before_value=100.0,
            after_value=100.0,
        )
        assert eng.calculate_false_positive_rate() == 0.0

    def test_with_data(self):
        eng = _engine()
        eng.run_test(
            "svc-a",
            before_value=100.0,
            after_value=250.0,
        )
        rate = eng.calculate_false_positive_rate()
        assert isinstance(rate, float)


# -------------------------------------------------------------------
# generate_regression_report
# -------------------------------------------------------------------


class TestGenerateRegressionReport:
    def test_basic_report(self):
        eng = _engine()
        eng.run_test(
            "svc-a",
            before_value=100.0,
            after_value=250.0,
        )
        eng.run_test(
            "svc-b",
            before_value=100.0,
            after_value=101.0,
        )
        report = eng.generate_regression_report()
        assert report.total_tests == 2
        assert report.regressions_found >= 1
        assert isinstance(report.by_severity, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_regression_report()
        assert report.total_tests == 0
        assert report.regressions_found == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.run_test("svc-a")
        eng.run_test("svc-b")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_tests()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_tests"] == 0
        assert stats["total_baselines"] == 0
        assert stats["significance_threshold"] == 0.05
        assert stats["severity_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.run_test(
            "svc-a",
            before_value=100.0,
            after_value=250.0,
        )
        eng.run_test(
            "svc-b",
            before_value=100.0,
            after_value=101.0,
        )
        stats = eng.get_stats()
        assert stats["total_tests"] == 2
        assert len(stats["severity_distribution"]) > 0
