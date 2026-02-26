"""Tests for shieldops.analytics.api_performance — APIPerformanceProfiler."""

from __future__ import annotations

from shieldops.analytics.api_performance import (
    APIPerformanceProfiler,
    APIPerformanceReport,
    EndpointProfile,
    LatencyPercentile,
    PerformanceRecord,
    PerformanceTier,
    PerformanceTrend,
)


def _engine(**kw) -> APIPerformanceProfiler:
    return APIPerformanceProfiler(**kw)


class TestEnums:
    def test_tier_fast(self):
        assert PerformanceTier.FAST == "fast"

    def test_tier_acceptable(self):
        assert PerformanceTier.ACCEPTABLE == "acceptable"

    def test_tier_slow(self):
        assert PerformanceTier.SLOW == "slow"

    def test_tier_degraded(self):
        assert PerformanceTier.DEGRADED == "degraded"

    def test_tier_critical(self):
        assert PerformanceTier.CRITICAL == "critical"

    def test_percentile_p50(self):
        assert LatencyPercentile.P50 == "p50"

    def test_percentile_p75(self):
        assert LatencyPercentile.P75 == "p75"

    def test_percentile_p90(self):
        assert LatencyPercentile.P90 == "p90"

    def test_percentile_p95(self):
        assert LatencyPercentile.P95 == "p95"

    def test_percentile_p99(self):
        assert LatencyPercentile.P99 == "p99"

    def test_trend_improving(self):
        assert PerformanceTrend.IMPROVING == "improving"

    def test_trend_stable(self):
        assert PerformanceTrend.STABLE == "stable"

    def test_trend_degrading(self):
        assert PerformanceTrend.DEGRADING == "degrading"

    def test_trend_volatile(self):
        assert PerformanceTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert PerformanceTrend.INSUFFICIENT_DATA == "insufficient_data"


class TestModels:
    def test_performance_record_defaults(self):
        r = PerformanceRecord()
        assert r.id
        assert r.endpoint_name == ""
        assert r.tier == PerformanceTier.ACCEPTABLE
        assert r.percentile == LatencyPercentile.P50
        assert r.latency_ms == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_endpoint_profile_defaults(self):
        r = EndpointProfile()
        assert r.id
        assert r.profile_name == ""
        assert r.tier == PerformanceTier.ACCEPTABLE
        assert r.percentile == LatencyPercentile.P50
        assert r.avg_latency_ms == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = APIPerformanceReport()
        assert r.total_records == 0
        assert r.total_profiles == 0
        assert r.avg_latency_ms == 0.0
        assert r.by_tier == {}
        assert r.by_percentile == {}
        assert r.slow_endpoint_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordPerformance:
    def test_basic(self):
        eng = _engine()
        r = eng.record_performance("/api/v1/users", latency_ms=120.0)
        assert r.endpoint_name == "/api/v1/users"
        assert r.latency_ms == 120.0

    def test_with_tier(self):
        eng = _engine()
        r = eng.record_performance("/api/v1/health", tier=PerformanceTier.FAST)
        assert r.tier == PerformanceTier.FAST

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_performance(f"/api/v1/ep-{i}")
        assert len(eng._records) == 3


class TestGetPerformance:
    def test_found(self):
        eng = _engine()
        r = eng.record_performance("/api/v1/users")
        assert eng.get_performance(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_performance("nonexistent") is None


class TestListPerformances:
    def test_list_all(self):
        eng = _engine()
        eng.record_performance("/api/v1/users")
        eng.record_performance("/api/v1/orders")
        assert len(eng.list_performances()) == 2

    def test_filter_by_endpoint(self):
        eng = _engine()
        eng.record_performance("/api/v1/users")
        eng.record_performance("/api/v1/orders")
        results = eng.list_performances(endpoint_name="/api/v1/users")
        assert len(results) == 1

    def test_filter_by_tier(self):
        eng = _engine()
        eng.record_performance("/api/v1/users", tier=PerformanceTier.FAST)
        eng.record_performance("/api/v1/orders", tier=PerformanceTier.SLOW)
        results = eng.list_performances(tier=PerformanceTier.FAST)
        assert len(results) == 1


class TestAddEndpointProfile:
    def test_basic(self):
        eng = _engine()
        p = eng.add_endpoint_profile("users-ep", avg_latency_ms=50.0)
        assert p.profile_name == "users-ep"
        assert p.avg_latency_ms == 50.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_endpoint_profile(f"profile-{i}")
        assert len(eng._profiles) == 2


class TestAnalyzeEndpointPerformance:
    def test_with_data(self):
        eng = _engine()
        eng.record_performance("/api/v1/users", latency_ms=200.0)
        eng.record_performance("/api/v1/users", latency_ms=300.0)
        result = eng.analyze_endpoint_performance("/api/v1/users")
        assert result["endpoint_name"] == "/api/v1/users"
        assert result["total"] == 2
        assert result["avg_latency"] == 250.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_endpoint_performance("/ghost")
        assert result["status"] == "no_data"


class TestIdentifySlowEndpoints:
    def test_with_slow(self):
        eng = _engine()
        eng.record_performance("/api/v1/users", tier=PerformanceTier.SLOW)
        eng.record_performance("/api/v1/users", tier=PerformanceTier.DEGRADED)
        eng.record_performance("/api/v1/orders", tier=PerformanceTier.FAST)
        results = eng.identify_slow_endpoints()
        assert len(results) == 1
        assert results[0]["endpoint_name"] == "/api/v1/users"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_endpoints() == []


class TestRankByLatency:
    def test_with_data(self):
        eng = _engine()
        eng.record_performance("/api/v1/users", latency_ms=100.0)
        eng.record_performance("/api/v1/orders", latency_ms=600.0)
        results = eng.rank_by_latency()
        assert results[0]["endpoint_name"] == "/api/v1/orders"
        assert results[0]["avg_latency_ms"] == 600.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_latency() == []


class TestDetectPerformanceDegradation:
    def test_with_degradation(self):
        eng = _engine()
        for i in range(5):
            eng.record_performance("/api/v1/users", latency_ms=float(100 + i * 50))
        results = eng.detect_performance_degradation()
        assert len(results) == 1
        assert results[0]["endpoint_name"] == "/api/v1/users"
        assert results[0]["degradation"] == "degrading"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_performance_degradation() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_performance("/api/v1/users", latency_ms=600.0, tier=PerformanceTier.SLOW)
        eng.record_performance("/api/v1/orders", latency_ms=50.0, tier=PerformanceTier.FAST)
        eng.add_endpoint_profile("p1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_profiles == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_performance("/api/v1/users")
        eng.add_endpoint_profile("p1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._profiles) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_profiles"] == 0
        assert stats["tier_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_performance("/api/v1/users", tier=PerformanceTier.FAST)
        eng.record_performance("/api/v1/orders", tier=PerformanceTier.SLOW)
        eng.add_endpoint_profile("p1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_profiles"] == 1
        assert stats["unique_endpoints"] == 2
