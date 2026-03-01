"""Tests for shieldops.analytics.perf_benchmark — PerformanceBenchmarkTracker."""

from __future__ import annotations

from shieldops.analytics.perf_benchmark import (
    BenchmarkBaseline,
    BenchmarkRecord,
    BenchmarkReport,
    BenchmarkResult,
    BenchmarkType,
    ComparisonScope,
    PerformanceBenchmarkTracker,
)


def _engine(**kw) -> PerformanceBenchmarkTracker:
    return PerformanceBenchmarkTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_benchmark_type_latency(self):
        assert BenchmarkType.LATENCY == "latency"

    def test_benchmark_type_throughput(self):
        assert BenchmarkType.THROUGHPUT == "throughput"

    def test_benchmark_type_cpu_usage(self):
        assert BenchmarkType.CPU_USAGE == "cpu_usage"

    def test_benchmark_type_memory_usage(self):
        assert BenchmarkType.MEMORY_USAGE == "memory_usage"

    def test_benchmark_type_disk_io(self):
        assert BenchmarkType.DISK_IO == "disk_io"

    def test_benchmark_result_passed(self):
        assert BenchmarkResult.PASSED == "passed"

    def test_benchmark_result_regressed(self):
        assert BenchmarkResult.REGRESSED == "regressed"

    def test_benchmark_result_improved(self):
        assert BenchmarkResult.IMPROVED == "improved"

    def test_benchmark_result_baseline(self):
        assert BenchmarkResult.BASELINE == "baseline"

    def test_benchmark_result_inconclusive(self):
        assert BenchmarkResult.INCONCLUSIVE == "inconclusive"

    def test_comparison_scope_service(self):
        assert ComparisonScope.SERVICE == "service"

    def test_comparison_scope_cluster(self):
        assert ComparisonScope.CLUSTER == "cluster"

    def test_comparison_scope_region(self):
        assert ComparisonScope.REGION == "region"

    def test_comparison_scope_global(self):
        assert ComparisonScope.GLOBAL == "global"

    def test_comparison_scope_historical(self):
        assert ComparisonScope.HISTORICAL == "historical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_benchmark_record_defaults(self):
        r = BenchmarkRecord()
        assert r.id
        assert r.service_name == ""
        assert r.benchmark_type == BenchmarkType.LATENCY
        assert r.benchmark_result == BenchmarkResult.BASELINE
        assert r.comparison_scope == ComparisonScope.SERVICE
        assert r.measured_value == 0.0
        assert r.baseline_value == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_benchmark_baseline_defaults(self):
        p = BenchmarkBaseline()
        assert p.id
        assert p.service_pattern == ""
        assert p.benchmark_type == BenchmarkType.LATENCY
        assert p.comparison_scope == ComparisonScope.SERVICE
        assert p.target_value == 0.0
        assert p.tolerance_pct == 10.0
        assert p.description == ""
        assert p.created_at > 0

    def test_benchmark_report_defaults(self):
        r = BenchmarkReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_baselines == 0
        assert r.regressions == 0
        assert r.avg_measured_value == 0.0
        assert r.by_type == {}
        assert r.by_result == {}
        assert r.by_scope == {}
        assert r.regressed_services == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_benchmark
# ---------------------------------------------------------------------------


class TestRecordBenchmark:
    def test_basic(self):
        eng = _engine()
        r = eng.record_benchmark(
            service_name="api-gateway",
            benchmark_type=BenchmarkType.THROUGHPUT,
            benchmark_result=BenchmarkResult.PASSED,
            comparison_scope=ComparisonScope.CLUSTER,
            measured_value=1500.0,
            baseline_value=1400.0,
            team="sre",
        )
        assert r.service_name == "api-gateway"
        assert r.benchmark_type == BenchmarkType.THROUGHPUT
        assert r.benchmark_result == BenchmarkResult.PASSED
        assert r.comparison_scope == ComparisonScope.CLUSTER
        assert r.measured_value == 1500.0
        assert r.baseline_value == 1400.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_benchmark(service_name=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_benchmark
# ---------------------------------------------------------------------------


class TestGetBenchmark:
    def test_found(self):
        eng = _engine()
        r = eng.record_benchmark(
            service_name="api-gateway",
            benchmark_result=BenchmarkResult.REGRESSED,
        )
        result = eng.get_benchmark(r.id)
        assert result is not None
        assert result.benchmark_result == BenchmarkResult.REGRESSED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_benchmark("nonexistent") is None


# ---------------------------------------------------------------------------
# list_benchmarks
# ---------------------------------------------------------------------------


class TestListBenchmarks:
    def test_list_all(self):
        eng = _engine()
        eng.record_benchmark(service_name="svc-001")
        eng.record_benchmark(service_name="svc-002")
        assert len(eng.list_benchmarks()) == 2

    def test_filter_by_benchmark_type(self):
        eng = _engine()
        eng.record_benchmark(
            service_name="svc-001",
            benchmark_type=BenchmarkType.LATENCY,
        )
        eng.record_benchmark(
            service_name="svc-002",
            benchmark_type=BenchmarkType.CPU_USAGE,
        )
        results = eng.list_benchmarks(benchmark_type=BenchmarkType.LATENCY)
        assert len(results) == 1

    def test_filter_by_benchmark_result(self):
        eng = _engine()
        eng.record_benchmark(
            service_name="svc-001",
            benchmark_result=BenchmarkResult.REGRESSED,
        )
        eng.record_benchmark(
            service_name="svc-002",
            benchmark_result=BenchmarkResult.PASSED,
        )
        results = eng.list_benchmarks(benchmark_result=BenchmarkResult.REGRESSED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_benchmark(service_name="svc-001", team="sre")
        eng.record_benchmark(service_name="svc-002", team="platform")
        results = eng.list_benchmarks(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_benchmark(service_name=f"svc-{i}")
        assert len(eng.list_benchmarks(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_baseline
# ---------------------------------------------------------------------------


class TestAddBaseline:
    def test_basic(self):
        eng = _engine()
        p = eng.add_baseline(
            service_pattern="api-*",
            benchmark_type=BenchmarkType.MEMORY_USAGE,
            comparison_scope=ComparisonScope.REGION,
            target_value=512.0,
            tolerance_pct=15.0,
            description="Memory usage baseline",
        )
        assert p.service_pattern == "api-*"
        assert p.benchmark_type == BenchmarkType.MEMORY_USAGE
        assert p.comparison_scope == ComparisonScope.REGION
        assert p.target_value == 512.0
        assert p.tolerance_pct == 15.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_baseline(service_pattern=f"pat-{i}")
        assert len(eng._baselines) == 2


# ---------------------------------------------------------------------------
# analyze_benchmark_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeBenchmarkDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_benchmark(
            service_name="svc-001",
            benchmark_type=BenchmarkType.LATENCY,
            measured_value=100.0,
        )
        eng.record_benchmark(
            service_name="svc-002",
            benchmark_type=BenchmarkType.LATENCY,
            measured_value=200.0,
        )
        result = eng.analyze_benchmark_distribution()
        assert "latency" in result
        assert result["latency"]["count"] == 2
        assert result["latency"]["avg_measured_value"] == 150.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_benchmark_distribution() == {}


# ---------------------------------------------------------------------------
# identify_regressions
# ---------------------------------------------------------------------------


class TestIdentifyRegressions:
    def test_detects_regressions(self):
        eng = _engine()
        eng.record_benchmark(
            service_name="svc-001",
            benchmark_result=BenchmarkResult.REGRESSED,
        )
        eng.record_benchmark(
            service_name="svc-002",
            benchmark_result=BenchmarkResult.PASSED,
        )
        results = eng.identify_regressions()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_regressions() == []


# ---------------------------------------------------------------------------
# rank_by_deviation
# ---------------------------------------------------------------------------


class TestRankByDeviation:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_benchmark(
            service_name="svc-001",
            team="sre",
            measured_value=200.0,
            baseline_value=100.0,
        )
        eng.record_benchmark(
            service_name="svc-002",
            team="platform",
            measured_value=110.0,
            baseline_value=100.0,
        )
        results = eng.rank_by_deviation()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_deviation"] == 100.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_deviation() == []


# ---------------------------------------------------------------------------
# detect_benchmark_trends
# ---------------------------------------------------------------------------


class TestDetectBenchmarkTrends:
    def test_stable(self):
        eng = _engine()
        for val in [100.0, 100.0, 100.0, 100.0]:
            eng.record_benchmark(service_name="svc", measured_value=val)
        result = eng.detect_benchmark_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [50.0, 50.0, 70.0, 70.0]:
            eng.record_benchmark(service_name="svc", measured_value=val)
        result = eng.detect_benchmark_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_benchmark_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_benchmark(
            service_name="svc-001",
            benchmark_type=BenchmarkType.LATENCY,
            benchmark_result=BenchmarkResult.REGRESSED,
            measured_value=250.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, BenchmarkReport)
        assert report.total_records == 1
        assert report.regressions == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_benchmark(service_name="svc-001")
        eng.add_baseline(service_pattern="p1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._baselines) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_baselines"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_benchmark(
            service_name="svc-001",
            benchmark_type=BenchmarkType.DISK_IO,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "disk_io" in stats["type_distribution"]
