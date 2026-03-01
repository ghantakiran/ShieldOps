"""Tests for shieldops.analytics.service_latency — ServiceLatencyAnalyzer."""

from __future__ import annotations

from shieldops.analytics.service_latency import (
    LatencyBaseline,
    LatencyImpact,
    LatencyRecord,
    LatencySource,
    LatencyTier,
    ServiceLatencyAnalyzer,
    ServiceLatencyReport,
)


def _engine(**kw) -> ServiceLatencyAnalyzer:
    return ServiceLatencyAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_tier_fast(self):
        assert LatencyTier.FAST == "fast"

    def test_tier_acceptable(self):
        assert LatencyTier.ACCEPTABLE == "acceptable"

    def test_tier_slow(self):
        assert LatencyTier.SLOW == "slow"

    def test_tier_degraded(self):
        assert LatencyTier.DEGRADED == "degraded"

    def test_tier_critical(self):
        assert LatencyTier.CRITICAL == "critical"

    def test_source_application(self):
        assert LatencySource.APPLICATION == "application"

    def test_source_database(self):
        assert LatencySource.DATABASE == "database"

    def test_source_network(self):
        assert LatencySource.NETWORK == "network"

    def test_source_external_api(self):
        assert LatencySource.EXTERNAL_API == "external_api"

    def test_source_queue(self):
        assert LatencySource.QUEUE == "queue"

    def test_impact_severe(self):
        assert LatencyImpact.SEVERE == "severe"

    def test_impact_high(self):
        assert LatencyImpact.HIGH == "high"

    def test_impact_moderate(self):
        assert LatencyImpact.MODERATE == "moderate"

    def test_impact_low(self):
        assert LatencyImpact.LOW == "low"

    def test_impact_none(self):
        assert LatencyImpact.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_latency_record_defaults(self):
        r = LatencyRecord()
        assert r.id
        assert r.service == ""
        assert r.latency_ms == 0.0
        assert r.latency_tier == LatencyTier.ACCEPTABLE
        assert r.latency_source == LatencySource.APPLICATION
        assert r.impact == LatencyImpact.LOW
        assert r.team == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_latency_baseline_defaults(self):
        b = LatencyBaseline()
        assert b.id
        assert b.service_pattern == ""
        assert b.latency_tier == LatencyTier.ACCEPTABLE
        assert b.latency_source == LatencySource.APPLICATION
        assert b.baseline_ms == 0.0
        assert b.threshold_ms == 0.0
        assert b.reason == ""
        assert b.created_at > 0

    def test_service_latency_report_defaults(self):
        r = ServiceLatencyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_baselines == 0
        assert r.slow_count == 0
        assert r.avg_latency_ms == 0.0
        assert r.by_tier == {}
        assert r.by_source == {}
        assert r.by_impact == {}
        assert r.bottleneck_services == []
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
            service="api-gateway",
            latency_ms=120.5,
            latency_tier=LatencyTier.SLOW,
            latency_source=LatencySource.NETWORK,
            impact=LatencyImpact.HIGH,
            team="sre",
        )
        assert r.service == "api-gateway"
        assert r.latency_ms == 120.5
        assert r.latency_tier == LatencyTier.SLOW
        assert r.latency_source == LatencySource.NETWORK
        assert r.impact == LatencyImpact.HIGH
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_latency(service=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_latency
# ---------------------------------------------------------------------------


class TestGetLatency:
    def test_found(self):
        eng = _engine()
        r = eng.record_latency(
            service="api-gateway",
            latency_tier=LatencyTier.SLOW,
        )
        result = eng.get_latency(r.id)
        assert result is not None
        assert result.latency_tier == LatencyTier.SLOW

    def test_not_found(self):
        eng = _engine()
        assert eng.get_latency("nonexistent") is None


# ---------------------------------------------------------------------------
# list_latencies
# ---------------------------------------------------------------------------


class TestListLatencies:
    def test_list_all(self):
        eng = _engine()
        eng.record_latency(service="svc-1")
        eng.record_latency(service="svc-2")
        assert len(eng.list_latencies()) == 2

    def test_filter_by_tier(self):
        eng = _engine()
        eng.record_latency(
            service="svc-1",
            latency_tier=LatencyTier.FAST,
        )
        eng.record_latency(
            service="svc-2",
            latency_tier=LatencyTier.SLOW,
        )
        results = eng.list_latencies(tier=LatencyTier.FAST)
        assert len(results) == 1

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_latency(
            service="svc-1",
            latency_source=LatencySource.DATABASE,
        )
        eng.record_latency(
            service="svc-2",
            latency_source=LatencySource.NETWORK,
        )
        results = eng.list_latencies(source=LatencySource.DATABASE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_latency(service="svc-1", team="sre")
        eng.record_latency(service="svc-2", team="platform")
        results = eng.list_latencies(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_latency(service=f"svc-{i}")
        assert len(eng.list_latencies(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_baseline
# ---------------------------------------------------------------------------


class TestAddBaseline:
    def test_basic(self):
        eng = _engine()
        b = eng.add_baseline(
            service_pattern="api-*",
            latency_tier=LatencyTier.FAST,
            latency_source=LatencySource.APPLICATION,
            baseline_ms=50.0,
            threshold_ms=200.0,
            reason="SLO target",
        )
        assert b.service_pattern == "api-*"
        assert b.latency_tier == LatencyTier.FAST
        assert b.baseline_ms == 50.0
        assert b.threshold_ms == 200.0
        assert b.reason == "SLO target"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_baseline(service_pattern=f"pat-{i}")
        assert len(eng._baselines) == 2


# ---------------------------------------------------------------------------
# analyze_latency_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeLatencyDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_latency(
            service="svc-1",
            latency_tier=LatencyTier.FAST,
            latency_ms=50.0,
        )
        eng.record_latency(
            service="svc-2",
            latency_tier=LatencyTier.FAST,
            latency_ms=100.0,
        )
        result = eng.analyze_latency_distribution()
        assert "fast" in result
        assert result["fast"]["count"] == 2
        assert result["fast"]["avg_latency"] == 75.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_latency_distribution() == {}


# ---------------------------------------------------------------------------
# identify_slow_services
# ---------------------------------------------------------------------------


class TestIdentifySlowServices:
    def test_detects_slow(self):
        eng = _engine()
        eng.record_latency(
            service="svc-1",
            latency_tier=LatencyTier.SLOW,
            latency_ms=300.0,
        )
        eng.record_latency(
            service="svc-2",
            latency_tier=LatencyTier.FAST,
            latency_ms=20.0,
        )
        results = eng.identify_slow_services()
        assert len(results) == 1
        assert results[0]["service"] == "svc-1"

    def test_includes_degraded_and_critical(self):
        eng = _engine()
        eng.record_latency(
            service="svc-d",
            latency_tier=LatencyTier.DEGRADED,
            latency_ms=400.0,
        )
        eng.record_latency(
            service="svc-c",
            latency_tier=LatencyTier.CRITICAL,
            latency_ms=800.0,
        )
        results = eng.identify_slow_services()
        assert len(results) == 2
        assert results[0]["service"] == "svc-c"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_services() == []


# ---------------------------------------------------------------------------
# rank_by_latency
# ---------------------------------------------------------------------------


class TestRankByLatency:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_latency(service="svc-a", latency_ms=100.0)
        eng.record_latency(service="svc-a", latency_ms=200.0)
        eng.record_latency(service="svc-b", latency_ms=50.0)
        results = eng.rank_by_latency()
        assert len(results) == 2
        assert results[0]["service"] == "svc-a"
        assert results[0]["avg_latency"] == 150.0
        assert results[0]["record_count"] == 2

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
            eng.record_latency(service="svc", latency_ms=ms)
        result = eng.detect_latency_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for ms in [50.0, 50.0, 200.0, 200.0]:
            eng.record_latency(service="svc", latency_ms=ms)
        result = eng.detect_latency_trends()
        assert result["trend"] == "increasing"
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
        eng = _engine()
        eng.record_latency(
            service="api-gateway",
            latency_tier=LatencyTier.SLOW,
            latency_source=LatencySource.NETWORK,
            latency_ms=300.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, ServiceLatencyReport)
        assert report.total_records == 1
        assert report.slow_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]

    def test_high_latency_recommendation(self):
        eng = _engine(max_latency_threshold_ms=100.0)
        eng.record_latency(
            service="svc-1",
            latency_ms=250.0,
            latency_tier=LatencyTier.SLOW,
        )
        report = eng.generate_report()
        assert any("above latency" in r for r in report.recommendations)


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_latency(service="svc-1")
        eng.add_baseline(service_pattern="pat-1")
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
        assert stats["tier_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_latency(
            service="api-gateway",
            latency_tier=LatencyTier.SLOW,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "slow" in stats["tier_distribution"]
