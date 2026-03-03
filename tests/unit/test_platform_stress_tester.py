"""Tests for shieldops.operations.platform_stress_tester."""

from __future__ import annotations

from shieldops.operations.platform_stress_tester import (
    PlatformStressReport,
    PlatformStressTester,
    StressAnalysis,
    StressResult,
    StressTest,
    StressType,
    TargetResource,
)


def _engine(**kw) -> PlatformStressTester:
    return PlatformStressTester(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_stress_type_load(self):
        assert StressType.LOAD == "load"

    def test_stress_type_spike(self):
        assert StressType.SPIKE == "spike"

    def test_stress_type_soak(self):
        assert StressType.SOAK == "soak"

    def test_stress_type_breakpoint(self):
        assert StressType.BREAKPOINT == "breakpoint"

    def test_stress_type_capacity(self):
        assert StressType.CAPACITY == "capacity"

    def test_resource_cpu(self):
        assert TargetResource.CPU == "cpu"

    def test_resource_memory(self):
        assert TargetResource.MEMORY == "memory"

    def test_resource_network(self):
        assert TargetResource.NETWORK == "network"

    def test_resource_disk(self):
        assert TargetResource.DISK == "disk"

    def test_resource_connections(self):
        assert TargetResource.CONNECTIONS == "connections"

    def test_result_passed(self):
        assert StressResult.PASSED == "passed"

    def test_result_degraded(self):
        assert StressResult.DEGRADED == "degraded"

    def test_result_failed(self):
        assert StressResult.FAILED == "failed"

    def test_result_bottleneck(self):
        assert StressResult.BOTTLENECK == "bottleneck"

    def test_result_crashed(self):
        assert StressResult.CRASHED == "crashed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_stress_test_defaults(self):
        r = StressTest()
        assert r.id
        assert r.stress_type == StressType.LOAD
        assert r.target_resource == TargetResource.CPU
        assert r.stress_result == StressResult.PASSED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_stress_analysis_defaults(self):
        a = StressAnalysis()
        assert a.id
        assert a.stress_type == StressType.LOAD
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_platform_stress_report_defaults(self):
        r = PlatformStressReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_stress_type == {}
        assert r.by_resource == {}
        assert r.by_result == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._threshold == 50.0
        assert eng._records == []
        assert eng._analyses == []

    def test_custom_max_records(self):
        eng = _engine(max_records=10000)
        assert eng._max_records == 10000

    def test_custom_threshold(self):
        eng = _engine(threshold=90.0)
        assert eng._threshold == 90.0


# ---------------------------------------------------------------------------
# record_test / get_test
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_test(
            service="api-platform",
            stress_type=StressType.SPIKE,
            target_resource=TargetResource.MEMORY,
            stress_result=StressResult.PASSED,
            score=88.0,
            team="perf",
        )
        assert r.service == "api-platform"
        assert r.stress_type == StressType.SPIKE
        assert r.target_resource == TargetResource.MEMORY
        assert r.stress_result == StressResult.PASSED
        assert r.score == 88.0
        assert r.team == "perf"

    def test_record_stored(self):
        eng = _engine()
        eng.record_test(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_test(service="svc-a", score=77.0)
        result = eng.get_test(r.id)
        assert result is not None
        assert result.score == 77.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_test("nonexistent") is None


# ---------------------------------------------------------------------------
# list_tests
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_test(service="svc-a")
        eng.record_test(service="svc-b")
        assert len(eng.list_tests()) == 2

    def test_filter_by_stress_type(self):
        eng = _engine()
        eng.record_test(service="svc-a", stress_type=StressType.LOAD)
        eng.record_test(service="svc-b", stress_type=StressType.SOAK)
        results = eng.list_tests(stress_type=StressType.LOAD)
        assert len(results) == 1

    def test_filter_by_resource(self):
        eng = _engine()
        eng.record_test(service="svc-a", target_resource=TargetResource.CPU)
        eng.record_test(service="svc-b", target_resource=TargetResource.DISK)
        results = eng.list_tests(target_resource=TargetResource.CPU)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_test(service="svc-a", team="perf")
        eng.record_test(service="svc-b", team="platform")
        assert len(eng.list_tests(team="perf")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_test(service=f"svc-{i}")
        assert len(eng.list_tests(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            stress_type=StressType.BREAKPOINT,
            analysis_score=38.0,
            threshold=50.0,
            breached=True,
            description="breakpoint reached early",
        )
        assert a.stress_type == StressType.BREAKPOINT
        assert a.analysis_score == 38.0
        assert a.breached is True

    def test_stored(self):
        eng = _engine()
        eng.add_analysis()
        assert len(eng._analyses) == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _ in range(5):
            eng.add_analysis()
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_test(service="s1", stress_type=StressType.LOAD, score=80.0)
        eng.record_test(service="s2", stress_type=StressType.LOAD, score=60.0)
        result = eng.analyze_distribution()
        assert "load" in result
        assert result["load"]["count"] == 2
        assert result["load"]["avg_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_stress_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_test(service="svc-a", score=60.0)
        eng.record_test(service="svc-b", score=90.0)
        results = eng.identify_stress_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_test(service="svc-a", score=55.0)
        eng.record_test(service="svc-b", score=35.0)
        results = eng.identify_stress_gaps()
        assert results[0]["score"] == 35.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_test(service="svc-a", score=90.0)
        eng.record_test(service="svc-b", score=40.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "svc-b"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_score_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_score_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_test(
            service="svc-a",
            stress_type=StressType.CAPACITY,
            target_resource=TargetResource.CONNECTIONS,
            stress_result=StressResult.BOTTLENECK,
            score=45.0,
        )
        report = eng.generate_report()
        assert isinstance(report, PlatformStressReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_test(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_test(
            service="svc-a",
            stress_type=StressType.LOAD,
            team="perf",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "load" in stats["stress_type_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_test(service=f"svc-{i}")
        assert len(eng._records) == 3
