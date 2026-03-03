"""Tests for shieldops.operations.recovery_time_benchmarker."""

from __future__ import annotations

from shieldops.operations.recovery_time_benchmarker import (
    BenchmarkAnalysis,
    BenchmarkResult,
    RecoveryBenchmark,
    RecoveryBenchmarkReport,
    RecoveryTarget,
    RecoveryTimeBenchmarker,
    RecoveryType,
)


def _engine(**kw) -> RecoveryTimeBenchmarker:
    return RecoveryTimeBenchmarker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_recovery_type_failover(self):
        assert RecoveryType.FAILOVER == "failover"

    def test_recovery_type_restart(self):
        assert RecoveryType.RESTART == "restart"

    def test_recovery_type_rollback(self):
        assert RecoveryType.ROLLBACK == "rollback"

    def test_recovery_type_rebuild(self):
        assert RecoveryType.REBUILD == "rebuild"

    def test_recovery_type_restore(self):
        assert RecoveryType.RESTORE == "restore"

    def test_result_exceeds(self):
        assert BenchmarkResult.EXCEEDS == "exceeds"

    def test_result_meets(self):
        assert BenchmarkResult.MEETS == "meets"

    def test_result_below(self):
        assert BenchmarkResult.BELOW == "below"

    def test_result_critical(self):
        assert BenchmarkResult.CRITICAL == "critical"

    def test_result_untested(self):
        assert BenchmarkResult.UNTESTED == "untested"

    def test_target_rto(self):
        assert RecoveryTarget.RTO == "rto"

    def test_target_rpo(self):
        assert RecoveryTarget.RPO == "rpo"

    def test_target_mttr(self):
        assert RecoveryTarget.MTTR == "mttr"

    def test_target_mttd(self):
        assert RecoveryTarget.MTTD == "mttd"

    def test_target_mttf(self):
        assert RecoveryTarget.MTTF == "mttf"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_recovery_benchmark_defaults(self):
        r = RecoveryBenchmark()
        assert r.id
        assert r.recovery_type == RecoveryType.FAILOVER
        assert r.benchmark_result == BenchmarkResult.MEETS
        assert r.recovery_target == RecoveryTarget.RTO
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_benchmark_analysis_defaults(self):
        a = BenchmarkAnalysis()
        assert a.id
        assert a.recovery_type == RecoveryType.FAILOVER
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_recovery_benchmark_report_defaults(self):
        r = RecoveryBenchmarkReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_recovery_type == {}
        assert r.by_result == {}
        assert r.by_target == {}
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
        eng = _engine(max_records=2000)
        assert eng._max_records == 2000

    def test_custom_threshold(self):
        eng = _engine(threshold=80.0)
        assert eng._threshold == 80.0


# ---------------------------------------------------------------------------
# record_benchmark / get_benchmark
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_benchmark(
            service="db-primary",
            recovery_type=RecoveryType.ROLLBACK,
            benchmark_result=BenchmarkResult.EXCEEDS,
            recovery_target=RecoveryTarget.RPO,
            score=95.0,
            team="data",
        )
        assert r.service == "db-primary"
        assert r.recovery_type == RecoveryType.ROLLBACK
        assert r.benchmark_result == BenchmarkResult.EXCEEDS
        assert r.recovery_target == RecoveryTarget.RPO
        assert r.score == 95.0
        assert r.team == "data"

    def test_record_stored(self):
        eng = _engine()
        eng.record_benchmark(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_benchmark(service="svc-a", score=70.0)
        result = eng.get_benchmark(r.id)
        assert result is not None
        assert result.score == 70.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_benchmark("nonexistent") is None


# ---------------------------------------------------------------------------
# list_benchmarks
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_benchmark(service="svc-a")
        eng.record_benchmark(service="svc-b")
        assert len(eng.list_benchmarks()) == 2

    def test_filter_by_recovery_type(self):
        eng = _engine()
        eng.record_benchmark(service="svc-a", recovery_type=RecoveryType.FAILOVER)
        eng.record_benchmark(service="svc-b", recovery_type=RecoveryType.RESTORE)
        results = eng.list_benchmarks(recovery_type=RecoveryType.FAILOVER)
        assert len(results) == 1

    def test_filter_by_result(self):
        eng = _engine()
        eng.record_benchmark(service="svc-a", benchmark_result=BenchmarkResult.MEETS)
        eng.record_benchmark(service="svc-b", benchmark_result=BenchmarkResult.CRITICAL)
        results = eng.list_benchmarks(benchmark_result=BenchmarkResult.MEETS)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_benchmark(service="svc-a", team="data")
        eng.record_benchmark(service="svc-b", team="platform")
        assert len(eng.list_benchmarks(team="data")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_benchmark(service=f"svc-{i}")
        assert len(eng.list_benchmarks(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            recovery_type=RecoveryType.REBUILD,
            analysis_score=40.0,
            threshold=50.0,
            breached=True,
            description="rebuild slow",
        )
        assert a.recovery_type == RecoveryType.REBUILD
        assert a.analysis_score == 40.0
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
        eng.record_benchmark(service="s1", recovery_type=RecoveryType.FAILOVER, score=80.0)
        eng.record_benchmark(service="s2", recovery_type=RecoveryType.FAILOVER, score=60.0)
        result = eng.analyze_distribution()
        assert "failover" in result
        assert result["failover"]["count"] == 2
        assert result["failover"]["avg_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_benchmark_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_benchmark(service="svc-a", score=60.0)
        eng.record_benchmark(service="svc-b", score=90.0)
        results = eng.identify_benchmark_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_benchmark(service="svc-a", score=55.0)
        eng.record_benchmark(service="svc-b", score=35.0)
        results = eng.identify_benchmark_gaps()
        assert results[0]["score"] == 35.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_benchmark(service="svc-a", score=85.0)
        eng.record_benchmark(service="svc-b", score=45.0)
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
        eng.record_benchmark(
            service="svc-a",
            recovery_type=RecoveryType.RESTART,
            benchmark_result=BenchmarkResult.BELOW,
            recovery_target=RecoveryTarget.MTTR,
            score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RecoveryBenchmarkReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_benchmark(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_benchmark(
            service="svc-a",
            recovery_type=RecoveryType.FAILOVER,
            team="data",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "failover" in stats["type_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_benchmark(service=f"svc-{i}")
        assert len(eng._records) == 3
