"""Tests for shieldops.security.posture_benchmark — SecurityPostureBenchmarker."""

from __future__ import annotations

from shieldops.security.posture_benchmark import (
    BenchmarkCategory,
    BenchmarkComparison,
    BenchmarkGrade,
    BenchmarkRecord,
    BenchmarkSource,
    PostureBenchmarkReport,
    SecurityPostureBenchmarker,
)


def _engine(**kw) -> SecurityPostureBenchmarker:
    return SecurityPostureBenchmarker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # BenchmarkCategory (5)
    def test_category_identity(self):
        assert BenchmarkCategory.IDENTITY == "identity"

    def test_category_network(self):
        assert BenchmarkCategory.NETWORK == "network"

    def test_category_data(self):
        assert BenchmarkCategory.DATA == "data"

    def test_category_application(self):
        assert BenchmarkCategory.APPLICATION == "application"

    def test_category_infrastructure(self):
        assert BenchmarkCategory.INFRASTRUCTURE == "infrastructure"

    # BenchmarkGrade (5)
    def test_grade_leading(self):
        assert BenchmarkGrade.LEADING == "leading"

    def test_grade_above_average(self):
        assert BenchmarkGrade.ABOVE_AVERAGE == "above_average"

    def test_grade_average(self):
        assert BenchmarkGrade.AVERAGE == "average"

    def test_grade_below_average(self):
        assert BenchmarkGrade.BELOW_AVERAGE == "below_average"

    def test_grade_lagging(self):
        assert BenchmarkGrade.LAGGING == "lagging"

    # BenchmarkSource (5)
    def test_source_industry_standard(self):
        assert BenchmarkSource.INDUSTRY_STANDARD == "industry_standard"

    def test_source_peer_group(self):
        assert BenchmarkSource.PEER_GROUP == "peer_group"

    def test_source_internal_baseline(self):
        assert BenchmarkSource.INTERNAL_BASELINE == "internal_baseline"

    def test_source_regulatory(self):
        assert BenchmarkSource.REGULATORY == "regulatory"

    def test_source_best_practice(self):
        assert BenchmarkSource.BEST_PRACTICE == "best_practice"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_benchmark_record_defaults(self):
        r = BenchmarkRecord()
        assert r.id
        assert r.service == ""
        assert r.category == BenchmarkCategory.INFRASTRUCTURE
        assert r.grade == BenchmarkGrade.AVERAGE
        assert r.source == BenchmarkSource.INDUSTRY_STANDARD
        assert r.benchmark_score == 0.0
        assert r.peer_score == 0.0
        assert r.passing is False
        assert r.created_at > 0

    def test_benchmark_comparison_defaults(self):
        r = BenchmarkComparison()
        assert r.id
        assert r.comparison_name == ""
        assert r.category == BenchmarkCategory.INFRASTRUCTURE
        assert r.source == BenchmarkSource.INDUSTRY_STANDARD
        assert r.our_score == 0.0
        assert r.benchmark_score == 0.0
        assert r.delta == 0.0
        assert r.service == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = PostureBenchmarkReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_comparisons == 0
        assert r.leading_count == 0
        assert r.lagging_count == 0
        assert r.avg_benchmark_score == 0.0
        assert r.by_category == {}
        assert r.by_grade == {}
        assert r.by_source == {}
        assert r.top_lagging_services == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_benchmark
# -------------------------------------------------------------------


class TestRecordBenchmark:
    def test_basic(self):
        eng = _engine()
        r = eng.record_benchmark("api-gateway")
        assert r.service == "api-gateway"
        assert r.grade == BenchmarkGrade.AVERAGE

    def test_with_params(self):
        eng = _engine()
        r = eng.record_benchmark(
            "auth-service",
            category=BenchmarkCategory.IDENTITY,
            grade=BenchmarkGrade.LAGGING,
            source=BenchmarkSource.REGULATORY,
            benchmark_score=45.0,
            peer_score=72.0,
            passing=False,
        )
        assert r.category == BenchmarkCategory.IDENTITY
        assert r.grade == BenchmarkGrade.LAGGING
        assert r.benchmark_score == 45.0
        assert r.passing is False

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_benchmark("svc-a")
        r2 = eng.record_benchmark("svc-b")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_benchmark(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_benchmark
# -------------------------------------------------------------------


class TestGetBenchmark:
    def test_found(self):
        eng = _engine()
        r = eng.record_benchmark("svc-x")
        assert eng.get_benchmark(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_benchmark("nonexistent") is None


# -------------------------------------------------------------------
# list_benchmarks
# -------------------------------------------------------------------


class TestListBenchmarks:
    def test_list_all(self):
        eng = _engine()
        eng.record_benchmark("svc-a")
        eng.record_benchmark("svc-b")
        assert len(eng.list_benchmarks()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_benchmark("svc-a", category=BenchmarkCategory.IDENTITY)
        eng.record_benchmark("svc-b", category=BenchmarkCategory.NETWORK)
        results = eng.list_benchmarks(category=BenchmarkCategory.IDENTITY)
        assert len(results) == 1
        assert results[0].category == BenchmarkCategory.IDENTITY

    def test_filter_by_grade(self):
        eng = _engine()
        eng.record_benchmark("svc-a", grade=BenchmarkGrade.LAGGING)
        eng.record_benchmark("svc-b", grade=BenchmarkGrade.LEADING)
        results = eng.list_benchmarks(grade=BenchmarkGrade.LAGGING)
        assert len(results) == 1

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_benchmark("svc-a", source=BenchmarkSource.REGULATORY)
        eng.record_benchmark("svc-b", source=BenchmarkSource.PEER_GROUP)
        results = eng.list_benchmarks(source=BenchmarkSource.REGULATORY)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_benchmark(f"svc-{i}")
        assert len(eng.list_benchmarks(limit=5)) == 5


# -------------------------------------------------------------------
# add_comparison
# -------------------------------------------------------------------


class TestAddComparison:
    def test_basic(self):
        eng = _engine()
        c = eng.add_comparison("nist-cis-comparison")
        assert c.comparison_name == "nist-cis-comparison"
        assert c.category == BenchmarkCategory.INFRASTRUCTURE

    def test_with_params(self):
        eng = _engine()
        c = eng.add_comparison(
            "peer-identity-benchmark",
            category=BenchmarkCategory.IDENTITY,
            source=BenchmarkSource.PEER_GROUP,
            our_score=65.0,
            benchmark_score=80.0,
            delta=-15.0,
            service="auth-service",
        )
        assert c.category == BenchmarkCategory.IDENTITY
        assert c.our_score == 65.0
        assert c.delta == -15.0

    def test_unique_comparison_ids(self):
        eng = _engine()
        c1 = eng.add_comparison("comp-a")
        c2 = eng.add_comparison("comp-b")
        assert c1.id != c2.id


# -------------------------------------------------------------------
# analyze_benchmark_by_category
# -------------------------------------------------------------------


class TestAnalyzeBenchmarkByCategory:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_benchmark_by_category()
        assert result["total_categories"] == 0
        assert result["breakdown"] == []

    def test_with_data(self):
        eng = _engine()
        for _ in range(3):
            eng.record_benchmark("svc-a", category=BenchmarkCategory.IDENTITY, benchmark_score=80.0)
        eng.record_benchmark("svc-b", category=BenchmarkCategory.NETWORK, benchmark_score=40.0)
        result = eng.analyze_benchmark_by_category()
        assert result["total_categories"] == 2
        cats = [b["category"] for b in result["breakdown"]]
        assert "identity" in cats

    def test_lagging_counted(self):
        eng = _engine()
        eng.record_benchmark("svc-a", category=BenchmarkCategory.DATA, grade=BenchmarkGrade.LAGGING)
        eng.record_benchmark("svc-b", category=BenchmarkCategory.DATA, grade=BenchmarkGrade.LEADING)
        result = eng.analyze_benchmark_by_category()
        data_cat = next(b for b in result["breakdown"] if b["category"] == "data")
        assert data_cat["lagging_count"] == 1


# -------------------------------------------------------------------
# identify_lagging_areas
# -------------------------------------------------------------------


class TestIdentifyLaggingAreas:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_lagging_areas() == []

    def test_only_lagging_returned(self):
        eng = _engine()
        eng.record_benchmark("svc-a", grade=BenchmarkGrade.LEADING)
        eng.record_benchmark("svc-b", grade=BenchmarkGrade.LAGGING)
        results = eng.identify_lagging_areas()
        assert len(results) == 1
        assert results[0]["service"] == "svc-b"

    def test_multiple_lagging(self):
        eng = _engine()
        for i in range(3):
            eng.record_benchmark(f"svc-{i}", grade=BenchmarkGrade.LAGGING)
        eng.record_benchmark("passing-svc", grade=BenchmarkGrade.ABOVE_AVERAGE)
        results = eng.identify_lagging_areas()
        assert len(results) == 3


# -------------------------------------------------------------------
# rank_by_benchmark_score
# -------------------------------------------------------------------


class TestRankByBenchmarkScore:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_benchmark_score() == []

    def test_ascending_order(self):
        eng = _engine()
        eng.record_benchmark("high-score-svc", benchmark_score=95.0)
        eng.record_benchmark("low-score-svc", benchmark_score=30.0)
        results = eng.rank_by_benchmark_score()
        assert results[0]["service"] == "low-score-svc"
        assert results[0]["avg_benchmark_score"] <= results[-1]["avg_benchmark_score"]


# -------------------------------------------------------------------
# detect_benchmark_trends
# -------------------------------------------------------------------


class TestDetectBenchmarkTrends:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_benchmark("svc")
        result = eng.detect_benchmark_trends()
        assert result["trend"] == "insufficient_data"

    def test_stable_trend(self):
        eng = _engine()
        for _ in range(8):
            eng.record_benchmark("svc", benchmark_score=70.0)
        result = eng.detect_benchmark_trends()
        assert result["trend"] in ("stable", "improving", "worsening")

    def test_improving_trend(self):
        eng = _engine()
        for _ in range(8):
            eng.record_benchmark("svc", benchmark_score=40.0)
        for _ in range(8):
            eng.record_benchmark("svc", benchmark_score=85.0)
        result = eng.detect_benchmark_trends()
        assert result["trend"] == "improving"
        assert result["total_records"] == 16


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert isinstance(report, PostureBenchmarkReport)
        assert report.total_records == 0
        assert report.recommendations

    def test_with_data(self):
        eng = _engine()
        eng.add_comparison("cis-bench", service="payments")
        eng.record_benchmark("payments", grade=BenchmarkGrade.LAGGING, benchmark_score=40.0)
        eng.record_benchmark("inventory", grade=BenchmarkGrade.LEADING, benchmark_score=90.0)
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_comparisons == 1
        assert report.lagging_count == 1
        assert report.leading_count == 1
        assert report.by_grade


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_records_and_comparisons(self):
        eng = _engine()
        eng.record_benchmark("svc-a")
        eng.add_comparison("comp-a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._comparisons) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_comparisons"] == 0
        assert stats["passing_count"] == 0

    def test_populated(self):
        eng = _engine(min_benchmark_score=75.0)
        eng.record_benchmark(
            "svc-a",
            category=BenchmarkCategory.IDENTITY,
            grade=BenchmarkGrade.LEADING,
            benchmark_score=92.0,
            passing=True,
        )
        eng.record_benchmark(
            "svc-b",
            category=BenchmarkCategory.NETWORK,
            grade=BenchmarkGrade.LAGGING,
            benchmark_score=35.0,
        )
        eng.add_comparison("comp-a")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_comparisons"] == 1
        assert stats["passing_count"] == 1
        assert stats["min_benchmark_score"] == 75.0
        assert stats["unique_services"] == 2
        assert stats["avg_benchmark_score"] > 0.0
