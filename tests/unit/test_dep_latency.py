"""Tests for shieldops.topology.dep_latency — DependencyLatencyTracker."""

from __future__ import annotations

from shieldops.topology.dep_latency import (
    DependencyLatencyReport,
    DependencyLatencyTracker,
    LatencyBreakdown,
    LatencyRecord,
    LatencySource,
    LatencyTier,
    LatencyTrend,
)


def _engine(**kw) -> DependencyLatencyTracker:
    return DependencyLatencyTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_tier_fast(self):
        assert LatencyTier.FAST == "fast"

    def test_tier_normal(self):
        assert LatencyTier.NORMAL == "normal"

    def test_tier_slow(self):
        assert LatencyTier.SLOW == "slow"

    def test_tier_degraded(self):
        assert LatencyTier.DEGRADED == "degraded"

    def test_tier_critical(self):
        assert LatencyTier.CRITICAL == "critical"

    def test_source_network(self):
        assert LatencySource.NETWORK == "network"

    def test_source_processing(self):
        assert LatencySource.PROCESSING == "processing"

    def test_source_queue(self):
        assert LatencySource.QUEUE == "queue"

    def test_source_database(self):
        assert LatencySource.DATABASE == "database"

    def test_source_external_api(self):
        assert LatencySource.EXTERNAL_API == "external_api"

    def test_trend_improving(self):
        assert LatencyTrend.IMPROVING == "improving"

    def test_trend_stable(self):
        assert LatencyTrend.STABLE == "stable"

    def test_trend_degrading(self):
        assert LatencyTrend.DEGRADING == "degrading"

    def test_trend_volatile(self):
        assert LatencyTrend.VOLATILE == "volatile"

    def test_trend_unknown(self):
        assert LatencyTrend.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_latency_record_defaults(self):
        r = LatencyRecord()
        assert r.id
        assert r.service == ""
        assert r.dependency == ""
        assert r.latency_ms == 0.0
        assert r.latency_tier == LatencyTier.NORMAL
        assert r.latency_source == LatencySource.NETWORK
        assert r.created_at > 0

    def test_latency_breakdown_defaults(self):
        b = LatencyBreakdown()
        assert b.id
        assert b.record_id == ""
        assert b.component == ""
        assert b.component_latency_ms == 0.0
        assert b.percentage == 0.0
        assert b.created_at > 0

    def test_report_defaults(self):
        r = DependencyLatencyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_breakdowns == 0
        assert r.avg_latency_ms == 0.0
        assert r.slow_dependency_count == 0
        assert r.by_tier == {}
        assert r.by_source == {}
        assert r.slowest_dependencies == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_latency
# ---------------------------------------------------------------------------


class TestRecordLatency:
    def test_basic(self):
        eng = _engine()
        r = eng.record_latency(
            service="api",
            dependency="postgres",
            latency_ms=350.0,
            latency_tier=LatencyTier.SLOW,
            latency_source=LatencySource.DATABASE,
        )
        assert r.service == "api"
        assert r.dependency == "postgres"
        assert r.latency_ms == 350.0
        assert r.latency_tier == LatencyTier.SLOW

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_latency(service="svc", dependency=f"dep-{i}", latency_ms=100.0)
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_latency
# ---------------------------------------------------------------------------


class TestGetLatency:
    def test_found(self):
        eng = _engine()
        r = eng.record_latency(service="api", dependency="redis", latency_ms=10.0)
        result = eng.get_latency(r.id)
        assert result is not None
        assert result.latency_ms == 10.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_latency("nonexistent") is None


# ---------------------------------------------------------------------------
# list_latencies
# ---------------------------------------------------------------------------


class TestListLatencies:
    def test_list_all(self):
        eng = _engine()
        eng.record_latency(service="a", dependency="x", latency_ms=100.0)
        eng.record_latency(service="b", dependency="y", latency_ms=200.0)
        assert len(eng.list_latencies()) == 2

    def test_filter_by_tier(self):
        eng = _engine()
        eng.record_latency(
            service="a", dependency="x", latency_ms=100.0, latency_tier=LatencyTier.FAST
        )
        eng.record_latency(
            service="b", dependency="y", latency_ms=800.0, latency_tier=LatencyTier.CRITICAL
        )
        results = eng.list_latencies(tier=LatencyTier.FAST)
        assert len(results) == 1

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_latency(
            service="a",
            dependency="x",
            latency_ms=100.0,
            latency_source=LatencySource.DATABASE,
        )
        eng.record_latency(
            service="b",
            dependency="y",
            latency_ms=200.0,
            latency_source=LatencySource.NETWORK,
        )
        results = eng.list_latencies(source=LatencySource.DATABASE)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_latency(service="api", dependency="x", latency_ms=100.0)
        eng.record_latency(service="worker", dependency="y", latency_ms=200.0)
        results = eng.list_latencies(service="api")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_latency(service="svc", dependency=f"dep-{i}", latency_ms=100.0)
        assert len(eng.list_latencies(limit=4)) == 4


# ---------------------------------------------------------------------------
# add_breakdown
# ---------------------------------------------------------------------------


class TestAddBreakdown:
    def test_basic(self):
        eng = _engine()
        b = eng.add_breakdown(
            record_id="REC-001",
            component="query_exec",
            component_latency_ms=250.0,
            percentage=71.4,
        )
        assert b.record_id == "REC-001"
        assert b.component == "query_exec"
        assert b.component_latency_ms == 250.0
        assert b.percentage == 71.4

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_breakdown(record_id="R", component=f"c-{i}")
        assert len(eng._breakdowns) == 2


# ---------------------------------------------------------------------------
# analyze_latency_by_dependency
# ---------------------------------------------------------------------------


class TestAnalyzeLatencyByDependency:
    def test_with_data(self):
        eng = _engine()
        eng.record_latency(service="a", dependency="postgres", latency_ms=400.0)
        eng.record_latency(service="b", dependency="postgres", latency_ms=600.0)
        result = eng.analyze_latency_by_dependency()
        assert "postgres" in result
        assert result["postgres"]["count"] == 2
        assert result["postgres"]["avg_latency_ms"] == 500.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_latency_by_dependency() == {}


# ---------------------------------------------------------------------------
# identify_slow_dependencies
# ---------------------------------------------------------------------------


class TestIdentifySlowDependencies:
    def test_detects_slow(self):
        eng = _engine(max_latency_ms=500.0)
        eng.record_latency(service="a", dependency="slow-db", latency_ms=800.0)
        eng.record_latency(service="b", dependency="fast-cache", latency_ms=50.0)
        results = eng.identify_slow_dependencies()
        assert len(results) == 1
        assert results[0]["dependency"] == "slow-db"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_dependencies() == []


# ---------------------------------------------------------------------------
# rank_by_latency
# ---------------------------------------------------------------------------


class TestRankByLatency:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_latency(service="api", dependency="x", latency_ms=300.0)
        eng.record_latency(service="worker", dependency="y", latency_ms=100.0)
        results = eng.rank_by_latency()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_latency_ms"] == 300.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_latency() == []


# ---------------------------------------------------------------------------
# detect_latency_trends
# ---------------------------------------------------------------------------


class TestDetectLatencyTrends:
    def test_stable(self):
        eng = _engine()
        for ms in [100.0, 100.0, 100.0, 100.0]:
            eng.record_latency(service="svc", dependency="dep", latency_ms=ms)
        result = eng.detect_latency_trends()
        assert result["trend"] == "stable"

    def test_degrading(self):
        eng = _engine()
        for ms in [50.0, 50.0, 700.0, 700.0]:
            eng.record_latency(service="svc", dependency="dep", latency_ms=ms)
        result = eng.detect_latency_trends()
        assert result["trend"] == "degrading"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_latency_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_latency_ms=500.0)
        eng.record_latency(
            service="api",
            dependency="slow-db",
            latency_ms=800.0,
            latency_tier=LatencyTier.CRITICAL,
        )
        report = eng.generate_report()
        assert isinstance(report, DependencyLatencyReport)
        assert report.total_records == 1
        assert report.slow_dependency_count == 1
        assert len(report.slowest_dependencies) == 1
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
        eng.record_latency(service="api", dependency="db", latency_ms=100.0)
        eng.add_breakdown(record_id="R", component="query")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._breakdowns) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_breakdowns"] == 0
        assert stats["tier_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_latency(
            service="api", dependency="db", latency_ms=100.0, latency_tier=LatencyTier.FAST
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_dependencies"] == 1
        assert "fast" in stats["tier_distribution"]
