"""Tests for shieldops.topology.network_latency — NetworkLatencyMapper."""

from __future__ import annotations

from shieldops.topology.network_latency import (
    LatencyCategory,
    LatencyHealth,
    LatencyPath,
    LatencyRecord,
    NetworkLatencyMapper,
    NetworkLatencyReport,
    PathType,
)


def _engine(**kw) -> NetworkLatencyMapper:
    return NetworkLatencyMapper(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # LatencyCategory (5)
    def test_category_intra_az(self):
        assert LatencyCategory.INTRA_AZ == "intra_az"

    def test_category_cross_az(self):
        assert LatencyCategory.CROSS_AZ == "cross_az"

    def test_category_cross_region(self):
        assert LatencyCategory.CROSS_REGION == "cross_region"

    def test_category_cross_cloud(self):
        assert LatencyCategory.CROSS_CLOUD == "cross_cloud"

    def test_category_external(self):
        assert LatencyCategory.EXTERNAL == "external"

    # LatencyHealth (5)
    def test_health_optimal(self):
        assert LatencyHealth.OPTIMAL == "optimal"

    def test_health_acceptable(self):
        assert LatencyHealth.ACCEPTABLE == "acceptable"

    def test_health_degraded(self):
        assert LatencyHealth.DEGRADED == "degraded"

    def test_health_poor(self):
        assert LatencyHealth.POOR == "poor"

    def test_health_critical(self):
        assert LatencyHealth.CRITICAL == "critical"

    # PathType (5)
    def test_path_direct(self):
        assert PathType.DIRECT == "direct"

    def test_path_load_balanced(self):
        assert PathType.LOAD_BALANCED == "load_balanced"

    def test_path_proxied(self):
        assert PathType.PROXIED == "proxied"

    def test_path_mesh(self):
        assert PathType.MESH == "mesh"

    def test_path_vpn(self):
        assert PathType.VPN == "vpn"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_latency_record_defaults(self):
        r = LatencyRecord()
        assert r.id
        assert r.path_name == ""
        assert r.category == LatencyCategory.INTRA_AZ
        assert r.health == LatencyHealth.OPTIMAL
        assert r.path_type == PathType.DIRECT
        assert r.latency_ms == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_latency_path_defaults(self):
        r = LatencyPath()
        assert r.id
        assert r.path_name == ""
        assert r.category == LatencyCategory.INTRA_AZ
        assert r.health == LatencyHealth.OPTIMAL
        assert r.source_service == ""
        assert r.target_service == ""
        assert r.created_at > 0

    def test_network_latency_report_defaults(self):
        r = NetworkLatencyReport()
        assert r.total_measurements == 0
        assert r.total_paths == 0
        assert r.healthy_rate_pct == 0.0
        assert r.by_category == {}
        assert r.by_health == {}
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_latency
# -------------------------------------------------------------------


class TestRecordLatency:
    def test_basic(self):
        eng = _engine()
        r = eng.record_latency("us-east-to-west", category=LatencyCategory.CROSS_REGION)
        assert r.path_name == "us-east-to-west"
        assert r.category == LatencyCategory.CROSS_REGION

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_latency(
            "api-to-db",
            category=LatencyCategory.INTRA_AZ,
            health=LatencyHealth.POOR,
            path_type=PathType.DIRECT,
            latency_ms=250.0,
            details="High latency on DB path",
        )
        assert r.health == LatencyHealth.POOR
        assert r.path_type == PathType.DIRECT
        assert r.latency_ms == 250.0
        assert r.details == "High latency on DB path"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_latency(f"path-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_latency
# -------------------------------------------------------------------


class TestGetLatency:
    def test_found(self):
        eng = _engine()
        r = eng.record_latency("us-east-to-west")
        assert eng.get_latency(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_latency("nonexistent") is None


# -------------------------------------------------------------------
# list_latencies
# -------------------------------------------------------------------


class TestListLatencies:
    def test_list_all(self):
        eng = _engine()
        eng.record_latency("path-a")
        eng.record_latency("path-b")
        assert len(eng.list_latencies()) == 2

    def test_filter_by_path_name(self):
        eng = _engine()
        eng.record_latency("path-a")
        eng.record_latency("path-b")
        results = eng.list_latencies(path_name="path-a")
        assert len(results) == 1
        assert results[0].path_name == "path-a"

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_latency("path-a", category=LatencyCategory.INTRA_AZ)
        eng.record_latency("path-b", category=LatencyCategory.CROSS_REGION)
        results = eng.list_latencies(category=LatencyCategory.CROSS_REGION)
        assert len(results) == 1
        assert results[0].path_name == "path-b"


# -------------------------------------------------------------------
# add_path
# -------------------------------------------------------------------


class TestAddPath:
    def test_basic(self):
        eng = _engine()
        p = eng.add_path(
            "api-to-db",
            category=LatencyCategory.INTRA_AZ,
            health=LatencyHealth.OPTIMAL,
            source_service="api-gateway",
            target_service="postgres-primary",
        )
        assert p.path_name == "api-to-db"
        assert p.category == LatencyCategory.INTRA_AZ
        assert p.source_service == "api-gateway"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_path(f"path-{i}")
        assert len(eng._paths) == 2


# -------------------------------------------------------------------
# analyze_network_health
# -------------------------------------------------------------------


class TestAnalyzeNetworkHealth:
    def test_with_data(self):
        eng = _engine(max_acceptable_ms=100.0)
        eng.record_latency("path-a", latency_ms=50.0)
        eng.record_latency("path-a", latency_ms=80.0)
        eng.record_latency("path-a", latency_ms=120.0)
        result = eng.analyze_network_health("path-a")
        assert result["avg_latency"] == 83.33
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_network_health("unknown-path")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(max_acceptable_ms=100.0)
        eng.record_latency("path-a", latency_ms=50.0)
        eng.record_latency("path-a", latency_ms=60.0)
        result = eng.analyze_network_health("path-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_high_latency_paths
# -------------------------------------------------------------------


class TestIdentifyHighLatencyPaths:
    def test_with_high_latency(self):
        eng = _engine()
        eng.record_latency("path-a", health=LatencyHealth.POOR)
        eng.record_latency("path-a", health=LatencyHealth.CRITICAL)
        eng.record_latency("path-b", health=LatencyHealth.OPTIMAL)
        results = eng.identify_high_latency_paths()
        assert len(results) == 1
        assert results[0]["path_name"] == "path-a"
        assert results[0]["high_latency_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_latency_paths() == []

    def test_single_poor_not_returned(self):
        eng = _engine()
        eng.record_latency("path-a", health=LatencyHealth.POOR)
        assert eng.identify_high_latency_paths() == []


# -------------------------------------------------------------------
# rank_by_latency
# -------------------------------------------------------------------


class TestRankByLatency:
    def test_with_data(self):
        eng = _engine()
        eng.record_latency("path-a", latency_ms=10.0)
        eng.record_latency("path-b", latency_ms=200.0)
        results = eng.rank_by_latency()
        assert results[0]["path_name"] == "path-b"
        assert results[0]["avg_latency_ms"] == 200.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_latency() == []


# -------------------------------------------------------------------
# detect_latency_anomalies
# -------------------------------------------------------------------


class TestDetectLatencyAnomalies:
    def test_with_anomalies(self):
        eng = _engine()
        for _ in range(5):
            eng.record_latency("path-a", health=LatencyHealth.DEGRADED)
        eng.record_latency("path-b", health=LatencyHealth.OPTIMAL)
        results = eng.detect_latency_anomalies()
        assert len(results) == 1
        assert results[0]["path_name"] == "path-a"
        assert results[0]["degraded_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_latency_anomalies() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_latency("path-a", health=LatencyHealth.DEGRADED)
        assert eng.detect_latency_anomalies() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_latency("path-a", health=LatencyHealth.CRITICAL)
        eng.record_latency("path-b", health=LatencyHealth.OPTIMAL)
        eng.add_path("path-c")
        report = eng.generate_report()
        assert report.total_measurements == 2
        assert report.total_paths == 1
        assert report.by_category != {}
        assert report.by_health != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_measurements == 0
        assert report.healthy_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_latency("path-a")
        eng.add_path("path-b")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._paths) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_measurements"] == 0
        assert stats["total_paths"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_acceptable_ms=100.0)
        eng.record_latency("path-a", category=LatencyCategory.INTRA_AZ)
        eng.record_latency("path-b", category=LatencyCategory.CROSS_REGION)
        eng.add_path("path-c")
        stats = eng.get_stats()
        assert stats["total_measurements"] == 2
        assert stats["total_paths"] == 1
        assert stats["unique_paths"] == 2
        assert stats["max_acceptable_ms"] == 100.0
