"""Tests for shieldops.topology.traffic_pattern — TrafficPatternAnalyzer."""

from __future__ import annotations

from shieldops.topology.traffic_pattern import (
    TrafficAnomaly,
    TrafficAnomalyRecord,
    TrafficDirection,
    TrafficHealth,
    TrafficPatternAnalyzer,
    TrafficPatternReport,
    TrafficRecord,
)


def _engine(**kw) -> TrafficPatternAnalyzer:
    return TrafficPatternAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # TrafficDirection (5)
    def test_direction_inbound(self):
        assert TrafficDirection.INBOUND == "inbound"

    def test_direction_outbound(self):
        assert TrafficDirection.OUTBOUND == "outbound"

    def test_direction_internal(self):
        assert TrafficDirection.INTERNAL == "internal"

    def test_direction_external(self):
        assert TrafficDirection.EXTERNAL == "external"

    def test_direction_cross_region(self):
        assert TrafficDirection.CROSS_REGION == "cross_region"

    # TrafficAnomaly (5)
    def test_anomaly_spike(self):
        assert TrafficAnomaly.SPIKE == "spike"

    def test_anomaly_drop(self):
        assert TrafficAnomaly.DROP == "drop"

    def test_anomaly_latency_increase(self):
        assert TrafficAnomaly.LATENCY_INCREASE == "latency_increase"

    def test_anomaly_error_burst(self):
        assert TrafficAnomaly.ERROR_BURST == "error_burst"

    def test_anomaly_pattern_shift(self):
        assert TrafficAnomaly.PATTERN_SHIFT == "pattern_shift"

    # TrafficHealth (5)
    def test_health_healthy(self):
        assert TrafficHealth.HEALTHY == "healthy"

    def test_health_elevated(self):
        assert TrafficHealth.ELEVATED == "elevated"

    def test_health_degraded(self):
        assert TrafficHealth.DEGRADED == "degraded"

    def test_health_critical(self):
        assert TrafficHealth.CRITICAL == "critical"

    def test_health_unknown(self):
        assert TrafficHealth.UNKNOWN == "unknown"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_traffic_record_defaults(self):
        r = TrafficRecord()
        assert r.id
        assert r.source_service == ""
        assert r.dest_service == ""
        assert r.direction == TrafficDirection.INTERNAL
        assert r.requests_per_second == 0.0
        assert r.error_rate_pct == 0.0
        assert r.p99_latency_ms == 0.0
        assert r.health == TrafficHealth.HEALTHY
        assert r.details == ""
        assert r.created_at > 0

    def test_traffic_anomaly_record_defaults(self):
        r = TrafficAnomalyRecord()
        assert r.id
        assert r.source_service == ""
        assert r.dest_service == ""
        assert r.anomaly_type == TrafficAnomaly.SPIKE
        assert r.severity == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_traffic_pattern_report_defaults(self):
        r = TrafficPatternReport()
        assert r.total_traffic_records == 0
        assert r.total_anomalies == 0
        assert r.avg_error_rate_pct == 0.0
        assert r.by_direction == {}
        assert r.by_health == {}
        assert r.hotspot_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_traffic
# -------------------------------------------------------------------


class TestRecordTraffic:
    def test_basic(self):
        eng = _engine()
        r = eng.record_traffic("svc-a", dest_service="svc-b", requests_per_second=100.0)
        assert r.source_service == "svc-a"
        assert r.dest_service == "svc-b"
        assert r.requests_per_second == 100.0

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_traffic(
            "svc-a",
            dest_service="svc-b",
            direction=TrafficDirection.CROSS_REGION,
            requests_per_second=500.0,
            error_rate_pct=8.5,
            p99_latency_ms=250.0,
            health=TrafficHealth.DEGRADED,
            details="High error rate",
        )
        assert r.direction == TrafficDirection.CROSS_REGION
        assert r.error_rate_pct == 8.5
        assert r.health == TrafficHealth.DEGRADED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_traffic(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_traffic
# -------------------------------------------------------------------


class TestGetTraffic:
    def test_found(self):
        eng = _engine()
        r = eng.record_traffic("svc-a")
        assert eng.get_traffic(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_traffic("nonexistent") is None


# -------------------------------------------------------------------
# list_traffic
# -------------------------------------------------------------------


class TestListTraffic:
    def test_list_all(self):
        eng = _engine()
        eng.record_traffic("svc-a")
        eng.record_traffic("svc-b")
        assert len(eng.list_traffic()) == 2

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_traffic("svc-a")
        eng.record_traffic("svc-b")
        results = eng.list_traffic(source_service="svc-a")
        assert len(results) == 1
        assert results[0].source_service == "svc-a"

    def test_filter_by_direction(self):
        eng = _engine()
        eng.record_traffic("svc-a", direction=TrafficDirection.INBOUND)
        eng.record_traffic("svc-b", direction=TrafficDirection.OUTBOUND)
        results = eng.list_traffic(direction=TrafficDirection.INBOUND)
        assert len(results) == 1
        assert results[0].source_service == "svc-a"


# -------------------------------------------------------------------
# record_anomaly
# -------------------------------------------------------------------


class TestRecordAnomaly:
    def test_basic(self):
        eng = _engine()
        a = eng.record_anomaly(
            "svc-a",
            dest_service="svc-b",
            anomaly_type=TrafficAnomaly.ERROR_BURST,
            severity=0.9,
            details="Sudden error spike",
        )
        assert a.source_service == "svc-a"
        assert a.anomaly_type == TrafficAnomaly.ERROR_BURST
        assert a.severity == 0.9

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_anomaly(f"svc-{i}")
        assert len(eng._anomalies) == 2


# -------------------------------------------------------------------
# analyze_service_pair
# -------------------------------------------------------------------


class TestAnalyzeServicePair:
    def test_with_data(self):
        eng = _engine()
        eng.record_traffic(
            "svc-a",
            dest_service="svc-b",
            requests_per_second=100.0,
            error_rate_pct=2.0,
            p99_latency_ms=50.0,
        )
        eng.record_traffic(
            "svc-a",
            dest_service="svc-b",
            requests_per_second=200.0,
            error_rate_pct=4.0,
            p99_latency_ms=100.0,
        )
        result = eng.analyze_service_pair("svc-a", "svc-b")
        assert result["source_service"] == "svc-a"
        assert result["dest_service"] == "svc-b"
        assert result["total_records"] == 2
        assert result["avg_requests_per_second"] == 150.0
        assert result["avg_error_rate_pct"] == 3.0
        assert result["avg_p99_latency_ms"] == 75.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_service_pair("ghost-a", "ghost-b")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_hotspots
# -------------------------------------------------------------------


class TestIdentifyHotspots:
    def test_with_hotspots(self):
        eng = _engine(error_threshold_pct=5.0)
        eng.record_traffic("svc-a", dest_service="svc-b", error_rate_pct=10.0)
        eng.record_traffic("svc-c", dest_service="svc-d", error_rate_pct=2.0)
        results = eng.identify_hotspots()
        assert len(results) == 1
        assert results[0]["source_service"] == "svc-a"
        assert results[0]["error_rate_pct"] == 10.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_hotspots() == []


# -------------------------------------------------------------------
# detect_error_prone_routes
# -------------------------------------------------------------------


class TestDetectErrorProneRoutes:
    def test_with_data(self):
        eng = _engine(error_threshold_pct=5.0)
        eng.record_traffic("svc-a", dest_service="svc-b", error_rate_pct=10.0)
        eng.record_traffic("svc-a", dest_service="svc-b", error_rate_pct=8.0)
        eng.record_traffic("svc-c", dest_service="svc-d", error_rate_pct=1.0)
        results = eng.detect_error_prone_routes()
        assert len(results) == 1
        assert results[0]["source_service"] == "svc-a"
        assert results[0]["avg_error_rate_pct"] == 9.0

    def test_empty(self):
        eng = _engine()
        assert eng.detect_error_prone_routes() == []


# -------------------------------------------------------------------
# rank_by_latency
# -------------------------------------------------------------------


class TestRankByLatency:
    def test_with_data(self):
        eng = _engine()
        eng.record_traffic("svc-a", dest_service="svc-b", p99_latency_ms=50.0)
        eng.record_traffic("svc-c", dest_service="svc-d", p99_latency_ms=200.0)
        eng.record_traffic("svc-e", dest_service="svc-f", p99_latency_ms=100.0)
        results = eng.rank_by_latency()
        assert len(results) == 3
        assert results[0]["source_service"] == "svc-c"
        assert results[0]["avg_p99_latency_ms"] == 200.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_latency() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(error_threshold_pct=5.0)
        eng.record_traffic(
            "svc-a",
            dest_service="svc-b",
            error_rate_pct=10.0,
            direction=TrafficDirection.INBOUND,
            health=TrafficHealth.DEGRADED,
        )
        eng.record_traffic(
            "svc-c",
            dest_service="svc-d",
            error_rate_pct=1.0,
            direction=TrafficDirection.INTERNAL,
            health=TrafficHealth.HEALTHY,
        )
        eng.record_anomaly("svc-a", anomaly_type=TrafficAnomaly.SPIKE)
        report = eng.generate_report()
        assert report.total_traffic_records == 2
        assert report.total_anomalies == 1
        assert report.by_direction != {}
        assert report.by_health != {}
        assert report.hotspot_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_traffic_records == 0
        assert report.avg_error_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_traffic("svc-a")
        eng.record_anomaly("svc-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._anomalies) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_traffic_records"] == 0
        assert stats["total_anomalies"] == 0
        assert stats["direction_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_traffic("svc-a", direction=TrafficDirection.INBOUND)
        eng.record_traffic("svc-b", direction=TrafficDirection.OUTBOUND)
        eng.record_anomaly("svc-a")
        stats = eng.get_stats()
        assert stats["total_traffic_records"] == 2
        assert stats["total_anomalies"] == 1
        assert stats["unique_sources"] == 2
        assert stats["error_threshold_pct"] == 5.0
