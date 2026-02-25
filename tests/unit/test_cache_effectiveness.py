"""Tests for shieldops.analytics.cache_effectiveness — CacheEffectivenessAnalyzer."""

from __future__ import annotations

import pytest

from shieldops.analytics.cache_effectiveness import (
    CacheEffectivenessAnalyzer,
    CacheEffectivenessReport,
    CacheHealth,
    CacheLayer,
    CacheMetricRecord,
    CacheRecommendation,
    OptimizationAction,
)


def _engine(**kw) -> CacheEffectivenessAnalyzer:
    return CacheEffectivenessAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # CacheLayer (5)
    def test_layer_application(self):
        assert CacheLayer.APPLICATION == "application"

    def test_layer_cdn(self):
        assert CacheLayer.CDN == "cdn"

    def test_layer_database(self):
        assert CacheLayer.DATABASE == "database"

    def test_layer_api_gateway(self):
        assert CacheLayer.API_GATEWAY == "api_gateway"

    def test_layer_distributed(self):
        assert CacheLayer.DISTRIBUTED == "distributed"

    # CacheHealth (5)
    def test_health_excellent(self):
        assert CacheHealth.EXCELLENT == "excellent"

    def test_health_good(self):
        assert CacheHealth.GOOD == "good"

    def test_health_fair(self):
        assert CacheHealth.FAIR == "fair"

    def test_health_poor(self):
        assert CacheHealth.POOR == "poor"

    def test_health_critical(self):
        assert CacheHealth.CRITICAL == "critical"

    # OptimizationAction (5)
    def test_action_increase_size(self):
        assert OptimizationAction.INCREASE_SIZE == "increase_size"

    def test_action_decrease_ttl(self):
        assert OptimizationAction.DECREASE_TTL == "decrease_ttl"

    def test_action_increase_ttl(self):
        assert OptimizationAction.INCREASE_TTL == "increase_ttl"

    def test_action_add_cache_layer(self):
        assert OptimizationAction.ADD_CACHE_LAYER == "add_cache_layer"

    def test_action_no_action(self):
        assert OptimizationAction.NO_ACTION == "no_action"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_cache_metric_record_defaults(self):
        r = CacheMetricRecord()
        assert r.id
        assert r.cache_name == ""
        assert r.layer == CacheLayer.APPLICATION
        assert r.hit_rate_pct == 0.0
        assert r.miss_rate_pct == 0.0
        assert r.eviction_rate == 0.0
        assert r.avg_latency_ms == 0.0
        assert r.size_mb == 0.0
        assert r.health == CacheHealth.GOOD
        assert r.details == ""
        assert r.created_at > 0

    def test_cache_recommendation_defaults(self):
        r = CacheRecommendation()
        assert r.id
        assert r.cache_name == ""
        assert r.action == OptimizationAction.NO_ACTION
        assert r.expected_improvement_pct == 0.0
        assert r.reason == ""
        assert r.created_at > 0

    def test_cache_effectiveness_report_defaults(self):
        r = CacheEffectivenessReport()
        assert r.total_caches == 0
        assert r.total_recommendations == 0
        assert r.avg_hit_rate_pct == 0.0
        assert r.by_layer == {}
        assert r.by_health == {}
        assert r.underperforming_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_metrics
# -------------------------------------------------------------------


class TestRecordMetrics:
    def test_basic(self):
        eng = _engine()
        r = eng.record_metrics("redis-main", hit_rate_pct=95.0, miss_rate_pct=5.0)
        assert r.cache_name == "redis-main"
        assert r.hit_rate_pct == 95.0
        assert r.health == CacheHealth.EXCELLENT  # >=95

    def test_auto_health_from_hit_rate(self):
        eng = _engine()
        r = eng.record_metrics("slow-cache", hit_rate_pct=40.0)
        assert r.health == CacheHealth.CRITICAL  # <50

    def test_explicit_health_overrides(self):
        eng = _engine()
        r = eng.record_metrics("cache-x", hit_rate_pct=40.0, health=CacheHealth.FAIR)
        assert r.health == CacheHealth.FAIR

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_metrics(f"cache-{i}", hit_rate_pct=90.0)
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_metrics
# -------------------------------------------------------------------


class TestGetMetrics:
    def test_found(self):
        eng = _engine()
        r = eng.record_metrics("redis-main", hit_rate_pct=90.0)
        assert eng.get_metrics(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_metrics("nonexistent") is None


# -------------------------------------------------------------------
# list_metrics
# -------------------------------------------------------------------


class TestListMetrics:
    def test_list_all(self):
        eng = _engine()
        eng.record_metrics("cache-a", hit_rate_pct=90.0)
        eng.record_metrics("cache-b", hit_rate_pct=80.0)
        assert len(eng.list_metrics()) == 2

    def test_filter_by_cache_name(self):
        eng = _engine()
        eng.record_metrics("cache-a", hit_rate_pct=90.0)
        eng.record_metrics("cache-b", hit_rate_pct=80.0)
        results = eng.list_metrics(cache_name="cache-a")
        assert len(results) == 1
        assert results[0].cache_name == "cache-a"

    def test_filter_by_layer(self):
        eng = _engine()
        eng.record_metrics("c1", layer=CacheLayer.CDN, hit_rate_pct=90.0)
        eng.record_metrics("c2", layer=CacheLayer.DATABASE, hit_rate_pct=80.0)
        results = eng.list_metrics(layer=CacheLayer.CDN)
        assert len(results) == 1
        assert results[0].cache_name == "c1"


# -------------------------------------------------------------------
# add_recommendation
# -------------------------------------------------------------------


class TestAddRecommendation:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_recommendation(
            "redis-main",
            action=OptimizationAction.INCREASE_SIZE,
            expected_improvement_pct=15.0,
            reason="High eviction rate",
        )
        assert rec.cache_name == "redis-main"
        assert rec.action == OptimizationAction.INCREASE_SIZE
        assert rec.expected_improvement_pct == 15.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_recommendation(f"cache-{i}")
        assert len(eng._recommendations) == 2


# -------------------------------------------------------------------
# analyze_cache_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeCacheEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_metrics(
            "redis-main",
            hit_rate_pct=92.0,
            miss_rate_pct=8.0,
            layer=CacheLayer.DISTRIBUTED,
        )
        result = eng.analyze_cache_effectiveness("redis-main")
        assert result["cache_name"] == "redis-main"
        assert result["hit_rate_pct"] == 92.0
        assert result["health"] == "good"
        assert result["layer"] == "distributed"

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_cache_effectiveness("ghost-cache")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_underperforming_caches
# -------------------------------------------------------------------


class TestIdentifyUnderperformingCaches:
    def test_with_underperforming(self):
        eng = _engine(min_hit_rate_pct=80.0)
        eng.record_metrics("good-cache", hit_rate_pct=95.0)
        eng.record_metrics("bad-cache", hit_rate_pct=60.0)
        eng.record_metrics("worse-cache", hit_rate_pct=30.0)
        results = eng.identify_underperforming_caches()
        assert len(results) == 2
        # Sorted by hit_rate asc
        assert results[0]["cache_name"] == "worse-cache"
        assert results[0]["gap_pct"] == pytest.approx(50.0)

    def test_empty(self):
        eng = _engine()
        assert eng.identify_underperforming_caches() == []


# -------------------------------------------------------------------
# rank_caches_by_hit_rate
# -------------------------------------------------------------------


class TestRankCachesByHitRate:
    def test_with_data(self):
        eng = _engine()
        eng.record_metrics("c1", hit_rate_pct=70.0)
        eng.record_metrics("c2", hit_rate_pct=95.0)
        eng.record_metrics("c3", hit_rate_pct=85.0)
        results = eng.rank_caches_by_hit_rate()
        assert len(results) == 3
        assert results[0]["cache_name"] == "c2"
        assert results[0]["hit_rate_pct"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_caches_by_hit_rate() == []


# -------------------------------------------------------------------
# estimate_latency_impact
# -------------------------------------------------------------------


class TestEstimateLatencyImpact:
    def test_with_data(self):
        eng = _engine(min_hit_rate_pct=80.0)
        eng.record_metrics("slow-cache", hit_rate_pct=60.0, avg_latency_ms=100.0)
        eng.record_metrics("ok-cache", hit_rate_pct=90.0, avg_latency_ms=50.0)
        results = eng.estimate_latency_impact()
        assert len(results) == 1  # only slow-cache below 80%
        assert results[0]["cache_name"] == "slow-cache"
        # gap = 80 - 60 = 20; saving = 100 * 20/100 = 20.0
        assert results[0]["estimated_saving_ms"] == pytest.approx(20.0)

    def test_empty(self):
        eng = _engine()
        assert eng.estimate_latency_impact() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_hit_rate_pct=80.0)
        eng.record_metrics("c1", hit_rate_pct=95.0, layer=CacheLayer.CDN)
        eng.record_metrics("c2", hit_rate_pct=40.0, layer=CacheLayer.APPLICATION)
        eng.add_recommendation("c2", action=OptimizationAction.INCREASE_SIZE)
        report = eng.generate_report()
        assert report.total_caches == 2
        assert report.total_recommendations == 1
        assert report.by_layer != {}
        assert report.by_health != {}
        assert report.underperforming_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_caches == 0
        assert report.avg_hit_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_metrics("c1", hit_rate_pct=90.0)
        eng.add_recommendation("c1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._recommendations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_caches"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["layer_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_metrics("c1", hit_rate_pct=90.0, layer=CacheLayer.CDN)
        eng.record_metrics("c2", hit_rate_pct=80.0, layer=CacheLayer.APPLICATION)
        eng.add_recommendation("c1")
        stats = eng.get_stats()
        assert stats["total_caches"] == 2
        assert stats["total_recommendations"] == 1
        assert stats["unique_caches"] == 2
        assert stats["min_hit_rate_pct"] == 80.0
