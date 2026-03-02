"""Tests for shieldops.topology.service_routing_optimizer — ServiceRoutingOptimizer."""

from __future__ import annotations

from shieldops.topology.service_routing_optimizer import (
    OptimizationAction,
    RouteHealth,
    RouteType,
    RoutingOptimization,
    RoutingRecord,
    ServiceRoutingOptimizer,
    ServiceRoutingReport,
)


def _engine(**kw) -> ServiceRoutingOptimizer:
    return ServiceRoutingOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_health_optimal(self):
        assert RouteHealth.OPTIMAL == "optimal"

    def test_health_degraded(self):
        assert RouteHealth.DEGRADED == "degraded"

    def test_health_congested(self):
        assert RouteHealth.CONGESTED == "congested"

    def test_health_failing(self):
        assert RouteHealth.FAILING == "failing"

    def test_health_unknown(self):
        assert RouteHealth.UNKNOWN == "unknown"

    def test_action_consolidate(self):
        assert OptimizationAction.CONSOLIDATE == "consolidate"

    def test_action_reroute(self):
        assert OptimizationAction.REROUTE == "reroute"

    def test_action_add_failover(self):
        assert OptimizationAction.ADD_FAILOVER == "add_failover"

    def test_action_remove_hop(self):
        assert OptimizationAction.REMOVE_HOP == "remove_hop"

    def test_action_cache_response(self):
        assert OptimizationAction.CACHE_RESPONSE == "cache_response"

    def test_type_synchronous(self):
        assert RouteType.SYNCHRONOUS == "synchronous"

    def test_type_asynchronous(self):
        assert RouteType.ASYNCHRONOUS == "asynchronous"

    def test_type_streaming(self):
        assert RouteType.STREAMING == "streaming"

    def test_type_batch(self):
        assert RouteType.BATCH == "batch"

    def test_type_event_driven(self):
        assert RouteType.EVENT_DRIVEN == "event_driven"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_routing_record_defaults(self):
        r = RoutingRecord()
        assert r.id
        assert r.route_name == ""
        assert r.route_health == RouteHealth.OPTIMAL
        assert r.optimization_action == OptimizationAction.CONSOLIDATE
        assert r.route_type == RouteType.SYNCHRONOUS
        assert r.latency_ms == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_routing_optimization_defaults(self):
        o = RoutingOptimization()
        assert o.id
        assert o.route_name == ""
        assert o.route_health == RouteHealth.OPTIMAL
        assert o.optimization_score == 0.0
        assert o.threshold == 0.0
        assert o.breached is False
        assert o.description == ""
        assert o.created_at > 0

    def test_service_routing_report_defaults(self):
        r = ServiceRoutingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_optimizations == 0
        assert r.high_latency_count == 0
        assert r.avg_latency_ms == 0.0
        assert r.by_health == {}
        assert r.by_action == {}
        assert r.by_type == {}
        assert r.top_high_latency == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_routing
# ---------------------------------------------------------------------------


class TestRecordRouting:
    def test_basic(self):
        eng = _engine()
        r = eng.record_routing(
            route_name="api-to-db",
            route_health=RouteHealth.DEGRADED,
            optimization_action=OptimizationAction.REROUTE,
            route_type=RouteType.ASYNCHRONOUS,
            latency_ms=350.0,
            service="api-gateway",
            team="sre",
        )
        assert r.route_name == "api-to-db"
        assert r.route_health == RouteHealth.DEGRADED
        assert r.optimization_action == OptimizationAction.REROUTE
        assert r.route_type == RouteType.ASYNCHRONOUS
        assert r.latency_ms == 350.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_routing(route_name=f"route-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_routing
# ---------------------------------------------------------------------------


class TestGetRouting:
    def test_found(self):
        eng = _engine()
        r = eng.record_routing(
            route_name="api-to-db",
            route_health=RouteHealth.CONGESTED,
        )
        result = eng.get_routing(r.id)
        assert result is not None
        assert result.route_health == RouteHealth.CONGESTED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_routing("nonexistent") is None


# ---------------------------------------------------------------------------
# list_routings
# ---------------------------------------------------------------------------


class TestListRoutings:
    def test_list_all(self):
        eng = _engine()
        eng.record_routing(route_name="route-1")
        eng.record_routing(route_name="route-2")
        assert len(eng.list_routings()) == 2

    def test_filter_by_health(self):
        eng = _engine()
        eng.record_routing(
            route_name="route-1",
            route_health=RouteHealth.DEGRADED,
        )
        eng.record_routing(
            route_name="route-2",
            route_health=RouteHealth.OPTIMAL,
        )
        results = eng.list_routings(
            route_health=RouteHealth.DEGRADED,
        )
        assert len(results) == 1

    def test_filter_by_action(self):
        eng = _engine()
        eng.record_routing(
            route_name="route-1",
            optimization_action=OptimizationAction.REROUTE,
        )
        eng.record_routing(
            route_name="route-2",
            optimization_action=OptimizationAction.ADD_FAILOVER,
        )
        results = eng.list_routings(
            optimization_action=OptimizationAction.REROUTE,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_routing(route_name="route-1", team="sre")
        eng.record_routing(route_name="route-2", team="platform")
        results = eng.list_routings(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_routing(route_name=f"route-{i}")
        assert len(eng.list_routings(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_optimization
# ---------------------------------------------------------------------------


class TestAddOptimization:
    def test_basic(self):
        eng = _engine()
        o = eng.add_optimization(
            route_name="api-to-db",
            route_health=RouteHealth.DEGRADED,
            optimization_score=65.0,
            threshold=80.0,
            breached=True,
            description="High latency on route",
        )
        assert o.route_name == "api-to-db"
        assert o.route_health == RouteHealth.DEGRADED
        assert o.optimization_score == 65.0
        assert o.threshold == 80.0
        assert o.breached is True
        assert o.description == "High latency on route"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_optimization(route_name=f"route-{i}")
        assert len(eng._optimizations) == 2


# ---------------------------------------------------------------------------
# analyze_routing_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeRoutingDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_routing(
            route_name="route-1",
            route_health=RouteHealth.DEGRADED,
            latency_ms=300.0,
        )
        eng.record_routing(
            route_name="route-2",
            route_health=RouteHealth.DEGRADED,
            latency_ms=400.0,
        )
        result = eng.analyze_routing_distribution()
        assert "degraded" in result
        assert result["degraded"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_routing_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_latency_routes
# ---------------------------------------------------------------------------


class TestIdentifyHighLatencyRoutes:
    def test_detects(self):
        eng = _engine(latency_threshold_ms=200.0)
        eng.record_routing(
            route_name="route-slow",
            latency_ms=350.0,
        )
        eng.record_routing(
            route_name="route-fast",
            latency_ms=50.0,
        )
        results = eng.identify_high_latency_routes()
        assert len(results) == 1
        assert results[0]["route_name"] == "route-slow"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_latency_routes() == []


# ---------------------------------------------------------------------------
# rank_by_latency
# ---------------------------------------------------------------------------


class TestRankByLatency:
    def test_ranked(self):
        eng = _engine()
        eng.record_routing(
            route_name="route-1",
            service="api-gateway",
            latency_ms=50.0,
        )
        eng.record_routing(
            route_name="route-2",
            service="payments",
            latency_ms=400.0,
        )
        results = eng.rank_by_latency()
        assert len(results) == 2
        assert results[0]["service"] == "payments"
        assert results[0]["avg_latency_ms"] == 400.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_latency() == []


# ---------------------------------------------------------------------------
# detect_routing_trends
# ---------------------------------------------------------------------------


class TestDetectRoutingTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_optimization(
                route_name="route-1",
                optimization_score=50.0,
            )
        result = eng.detect_routing_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_optimization(route_name="route-1", optimization_score=30.0)
        eng.add_optimization(route_name="route-2", optimization_score=30.0)
        eng.add_optimization(route_name="route-3", optimization_score=80.0)
        eng.add_optimization(route_name="route-4", optimization_score=80.0)
        result = eng.detect_routing_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_routing_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(latency_threshold_ms=200.0)
        eng.record_routing(
            route_name="api-to-db",
            route_health=RouteHealth.DEGRADED,
            optimization_action=OptimizationAction.REROUTE,
            route_type=RouteType.SYNCHRONOUS,
            latency_ms=350.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ServiceRoutingReport)
        assert report.total_records == 1
        assert report.high_latency_count == 1
        assert len(report.top_high_latency) == 1
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
        eng.record_routing(route_name="route-1")
        eng.add_optimization(route_name="route-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._optimizations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_optimizations"] == 0
        assert stats["health_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_routing(
            route_name="route-1",
            route_health=RouteHealth.DEGRADED,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "degraded" in stats["health_distribution"]
