"""Tests for shieldops.observability.metric_federation_engine — MetricFederationEngine."""

from __future__ import annotations

from shieldops.observability.metric_federation_engine import (
    ConflictStrategy,
    FederatedResult,
    FederationEndpoint,
    FederationReport,
    FederationSource,
    FederationStatus,
    MetricFederationEngine,
)


def _engine(**kw) -> MetricFederationEngine:
    return MetricFederationEngine(**kw)


class TestEnums:
    def test_source_prometheus(self):
        assert FederationSource.PROMETHEUS == "prometheus"

    def test_source_thanos(self):
        assert FederationSource.THANOS == "thanos"

    def test_source_mimir(self):
        assert FederationSource.MIMIR == "mimir"

    def test_source_victoria(self):
        assert FederationSource.VICTORIA_METRICS == "victoria_metrics"

    def test_strategy_latest(self):
        assert ConflictStrategy.LATEST_WINS == "latest_wins"

    def test_strategy_average(self):
        assert ConflictStrategy.AVERAGE == "average"

    def test_strategy_max(self):
        assert ConflictStrategy.MAX == "max"

    def test_strategy_min(self):
        assert ConflictStrategy.MIN == "min"

    def test_status_healthy(self):
        assert FederationStatus.HEALTHY == "healthy"

    def test_status_degraded(self):
        assert FederationStatus.DEGRADED == "degraded"

    def test_status_unreachable(self):
        assert FederationStatus.UNREACHABLE == "unreachable"


class TestModels:
    def test_endpoint_defaults(self):
        e = FederationEndpoint()
        assert e.id
        assert e.source_type == FederationSource.PROMETHEUS
        assert e.status == FederationStatus.HEALTHY

    def test_result_defaults(self):
        r = FederatedResult()
        assert r.id
        assert r.sources_queried == 0

    def test_report_defaults(self):
        r = FederationReport()
        assert r.total_endpoints == 0
        assert r.recommendations == []


class TestAddEndpoint:
    def test_basic(self):
        eng = _engine()
        e = eng.add_endpoint("prom-1", source_type=FederationSource.PROMETHEUS)
        assert e.name == "prom-1"

    def test_with_priority(self):
        eng = _engine()
        e = eng.add_endpoint("prom-1", priority=10)
        assert e.priority == 10

    def test_eviction(self):
        eng = _engine(max_endpoints=3)
        for i in range(5):
            eng.add_endpoint(f"e-{i}")
        assert len(eng._endpoints) == 3


class TestFederateQuery:
    def test_basic(self):
        eng = _engine()
        eng.add_endpoint("prom-1")
        result = eng.federate_query("up{job='api'}")
        assert result.query == "up{job='api'}"
        assert result.sources_queried == 1

    def test_no_endpoints(self):
        eng = _engine()
        result = eng.federate_query("up")
        assert result.sources_queried == 0

    def test_excludes_unhealthy(self):
        eng = _engine()
        e = eng.add_endpoint("prom-1")
        e.status = FederationStatus.UNREACHABLE
        result = eng.federate_query("up")
        assert result.sources_queried == 0


class TestMergeResults:
    def test_empty(self):
        eng = _engine()
        result = eng.merge_results([])
        assert result["conflicts"] == 0

    def test_no_conflicts(self):
        eng = _engine()
        result = eng.merge_results(
            [
                {"metric": "cpu", "value": 50.0},
            ]
        )
        assert result["conflicts"] == 0

    def test_with_conflicts(self):
        eng = _engine()
        result = eng.merge_results(
            [
                {"metric": "cpu", "value": 50.0},
                {"metric": "cpu", "value": 60.0},
            ]
        )
        assert result["conflicts"] == 1


class TestResolveConflicts:
    def test_latest_wins(self):
        eng = _engine(conflict_strategy=ConflictStrategy.LATEST_WINS)
        result = eng.resolve_conflicts([10.0, 20.0, 30.0])
        assert result["resolved_value"] == 30.0

    def test_average(self):
        eng = _engine(conflict_strategy=ConflictStrategy.AVERAGE)
        result = eng.resolve_conflicts([10.0, 20.0, 30.0])
        assert result["resolved_value"] == 20.0

    def test_max(self):
        eng = _engine(conflict_strategy=ConflictStrategy.MAX)
        result = eng.resolve_conflicts([10.0, 20.0, 30.0])
        assert result["resolved_value"] == 30.0

    def test_min(self):
        eng = _engine(conflict_strategy=ConflictStrategy.MIN)
        result = eng.resolve_conflicts([10.0, 20.0, 30.0])
        assert result["resolved_value"] == 10.0

    def test_empty(self):
        eng = _engine()
        result = eng.resolve_conflicts([])
        assert result["resolved_value"] == 0.0


class TestOptimizeFederation:
    def test_healthy(self):
        eng = _engine()
        eng.add_endpoint("prom-1")
        result = eng.optimize_federation()
        assert result[0]["type"] == "none"

    def test_unreachable(self):
        eng = _engine()
        e = eng.add_endpoint("prom-1")
        e.status = FederationStatus.UNREACHABLE
        result = eng.optimize_federation()
        assert result[0]["type"] == "connectivity"

    def test_high_latency(self):
        eng = _engine()
        e = eng.add_endpoint("prom-1")
        e.latency_ms = 600.0
        result = eng.optimize_federation()
        assert any(s["type"] == "latency" for s in result)


class TestGetFederationTopology:
    def test_empty(self):
        eng = _engine()
        topo = eng.get_federation_topology()
        assert topo["total_endpoints"] == 0

    def test_populated(self):
        eng = _engine()
        eng.add_endpoint("prom-1")
        topo = eng.get_federation_topology()
        assert topo["total_endpoints"] == 1
        assert topo["healthy"] == 1


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_endpoints == 0

    def test_populated(self):
        eng = _engine()
        eng.add_endpoint("prom-1")
        report = eng.generate_report()
        assert report.total_endpoints == 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_endpoint("prom-1")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._endpoints) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_endpoints"] == 0

    def test_populated(self):
        eng = _engine()
        eng.add_endpoint("prom-1")
        eng.federate_query("up")
        stats = eng.get_stats()
        assert stats["total_queries"] == 1
