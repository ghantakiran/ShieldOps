"""Tests for the service dependency topology module.

Covers:
- ServiceNode / ServiceEdge Pydantic models
- ServiceGraphBuilder: add/remove nodes, add edges (dedup)
- get_map(), get_dependencies() (upstream, downstream, transitive)
- Cycle detection (DAG, single cycle, multiple, self-loop)
- Critical path (BFS shortest path)
- merge_from_traces (OTel span extraction)
- merge_from_k8s (K8s service discovery)
- merge_from_config (manual declarations)
- Topology API routes (GET /map, GET dependencies, POST traces, GET cycles, GET path)
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import topology as topology_routes
from shieldops.topology.graph import (
    DependencyView,
    ServiceEdge,
    ServiceGraphBuilder,
    ServiceMap,
    ServiceNode,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_builder() -> Any:
    """Reset the module-level builder singleton between tests."""
    topology_routes._builder = None
    yield
    topology_routes._builder = None


@pytest.fixture()
def builder() -> ServiceGraphBuilder:
    """Return a fresh ServiceGraphBuilder."""
    return ServiceGraphBuilder()


@pytest.fixture()
def populated_builder() -> ServiceGraphBuilder:
    """Return a builder with a small pre-built graph.

    Graph:
        api-gateway -> user-service -> postgres
        api-gateway -> order-service -> postgres
        order-service -> redis
    """
    b = ServiceGraphBuilder()
    b.add_node(ServiceNode(id="api-gateway", name="API Gateway", type="service"))
    b.add_node(ServiceNode(id="user-service", name="User Service", type="service"))
    b.add_node(ServiceNode(id="order-service", name="Order Service", type="service"))
    b.add_node(ServiceNode(id="postgres", name="PostgreSQL", type="database"))
    b.add_node(ServiceNode(id="redis", name="Redis", type="cache"))

    b.add_edge(ServiceEdge(source="api-gateway", target="user-service"))
    b.add_edge(ServiceEdge(source="api-gateway", target="order-service"))
    b.add_edge(ServiceEdge(source="user-service", target="postgres"))
    b.add_edge(ServiceEdge(source="order-service", target="postgres"))
    b.add_edge(ServiceEdge(source="order-service", target="redis"))
    return b


@pytest.fixture()
def api_client(populated_builder: ServiceGraphBuilder) -> TestClient:
    """TestClient with topology routes wired to the populated builder."""
    app = FastAPI()
    app.include_router(topology_routes.router)
    topology_routes.set_builder(populated_builder)
    return TestClient(app)


# =========================================================================
# ServiceNode model
# =========================================================================


class TestServiceNode:
    """Tests for the ServiceNode Pydantic model."""

    def test_defaults(self) -> None:
        node = ServiceNode(id="svc-1", name="My Service")
        assert node.id == "svc-1"
        assert node.name == "My Service"
        assert node.type == "service"
        assert node.metadata == {}
        assert node.health == "unknown"
        assert node.discovered_via == "manual"

    def test_custom_metadata(self) -> None:
        node = ServiceNode(
            id="db-1",
            name="PostgreSQL",
            type="database",
            metadata={"version": "16.2", "replicas": 3},
            health="healthy",
            discovered_via="k8s",
        )
        assert node.type == "database"
        assert node.metadata["version"] == "16.2"
        assert node.health == "healthy"
        assert node.discovered_via == "k8s"

    def test_serialization_round_trip(self) -> None:
        node = ServiceNode(id="ext-1", name="Stripe API", type="external")
        data = node.model_dump()
        restored = ServiceNode(**data)
        assert restored == node


# =========================================================================
# ServiceEdge model
# =========================================================================


class TestServiceEdge:
    """Tests for the ServiceEdge Pydantic model."""

    def test_defaults(self) -> None:
        edge = ServiceEdge(source="a", target="b")
        assert edge.source == "a"
        assert edge.target == "b"
        assert edge.edge_type == "calls"
        assert edge.latency_p50 is None
        assert edge.latency_p99 is None
        assert edge.request_rate is None
        assert edge.error_rate is None
        assert edge.metadata == {}

    def test_with_metrics(self) -> None:
        edge = ServiceEdge(
            source="api",
            target="db",
            edge_type="queries",
            latency_p50=5.2,
            latency_p99=42.0,
            request_rate=1200.0,
            error_rate=0.01,
        )
        assert edge.latency_p50 == 5.2
        assert edge.request_rate == 1200.0


# =========================================================================
# Add / Remove Nodes
# =========================================================================


class TestAddNode:
    """Tests for node add, update, and remove."""

    def test_add_node(self, builder: ServiceGraphBuilder) -> None:
        node = ServiceNode(id="svc-1", name="Service One")
        builder.add_node(node)
        assert builder.get_node("svc-1") is not None
        assert builder.get_node("svc-1").name == "Service One"

    def test_update_existing_node(self, builder: ServiceGraphBuilder) -> None:
        builder.add_node(ServiceNode(id="svc-1", name="Old Name"))
        builder.add_node(ServiceNode(id="svc-1", name="New Name"))
        assert builder.get_node("svc-1").name == "New Name"

    def test_get_nonexistent_node(self, builder: ServiceGraphBuilder) -> None:
        assert builder.get_node("does-not-exist") is None

    def test_remove_node(self, builder: ServiceGraphBuilder) -> None:
        builder.add_node(ServiceNode(id="svc-1", name="Service One"))
        assert builder.remove_node("svc-1") is True
        assert builder.get_node("svc-1") is None

    def test_remove_nonexistent_node(self, builder: ServiceGraphBuilder) -> None:
        assert builder.remove_node("ghost") is False

    def test_remove_node_cleans_edges(self, builder: ServiceGraphBuilder) -> None:
        builder.add_node(ServiceNode(id="a", name="A"))
        builder.add_node(ServiceNode(id="b", name="B"))
        builder.add_node(ServiceNode(id="c", name="C"))
        builder.add_edge(ServiceEdge(source="a", target="b"))
        builder.add_edge(ServiceEdge(source="b", target="c"))
        builder.add_edge(ServiceEdge(source="a", target="c"))

        builder.remove_node("b")

        smap = builder.get_map()
        assert len(smap.edges) == 1
        assert smap.edges[0].source == "a"
        assert smap.edges[0].target == "c"


# =========================================================================
# Add Edges (with deduplication)
# =========================================================================


class TestAddEdge:
    """Tests for edge add and deduplication."""

    def test_add_edge(self, builder: ServiceGraphBuilder) -> None:
        builder.add_edge(ServiceEdge(source="a", target="b"))
        smap = builder.get_map()
        assert len(smap.edges) == 1

    def test_dedup_by_source_target(self, builder: ServiceGraphBuilder) -> None:
        builder.add_edge(ServiceEdge(source="a", target="b", edge_type="calls"))
        builder.add_edge(ServiceEdge(source="a", target="b", edge_type="queries"))
        smap = builder.get_map()
        assert len(smap.edges) == 1
        # Second add should have updated the edge
        assert smap.edges[0].edge_type == "queries"

    def test_different_targets_not_deduped(self, builder: ServiceGraphBuilder) -> None:
        builder.add_edge(ServiceEdge(source="a", target="b"))
        builder.add_edge(ServiceEdge(source="a", target="c"))
        smap = builder.get_map()
        assert len(smap.edges) == 2


# =========================================================================
# get_map()
# =========================================================================


class TestGetMap:
    """Tests for the full map snapshot."""

    def test_empty_map(self, builder: ServiceGraphBuilder) -> None:
        smap = builder.get_map()
        assert isinstance(smap, ServiceMap)
        assert smap.nodes == []
        assert smap.edges == []
        assert smap.updated_at is not None

    def test_populated_map(self, populated_builder: ServiceGraphBuilder) -> None:
        smap = populated_builder.get_map()
        assert len(smap.nodes) == 5
        assert len(smap.edges) == 5
        node_ids = {n.id for n in smap.nodes}
        assert "api-gateway" in node_ids
        assert "postgres" in node_ids

    def test_sources_reflects_discovery(self, builder: ServiceGraphBuilder) -> None:
        builder.add_node(ServiceNode(id="a", name="A", discovered_via="trace"))
        builder.add_node(ServiceNode(id="b", name="B", discovered_via="k8s"))
        smap = builder.get_map()
        assert "trace" in smap.sources
        assert "k8s" in smap.sources


# =========================================================================
# get_dependencies()
# =========================================================================


class TestGetDependencies:
    """Tests for upstream/downstream/transitive dependency views."""

    def test_upstream_dependencies(self, populated_builder: ServiceGraphBuilder) -> None:
        view = populated_builder.get_dependencies("user-service")
        assert isinstance(view, DependencyView)
        upstream_ids = [u["service_id"] for u in view.upstream]
        assert "api-gateway" in upstream_ids

    def test_downstream_dependencies(self, populated_builder: ServiceGraphBuilder) -> None:
        view = populated_builder.get_dependencies("order-service")
        downstream_ids = [d["service_id"] for d in view.downstream]
        assert "postgres" in downstream_ids
        assert "redis" in downstream_ids

    def test_transitive_dependencies(self, populated_builder: ServiceGraphBuilder) -> None:
        view = populated_builder.get_dependencies("api-gateway", include_transitive=True)
        # api-gateway -> user-service -> postgres
        # api-gateway -> order-service -> postgres, redis
        assert "postgres" in view.transitive_dependencies
        assert "redis" in view.transitive_dependencies
        assert "user-service" in view.transitive_dependencies
        assert "order-service" in view.transitive_dependencies

    def test_unknown_service_returns_empty(self, populated_builder: ServiceGraphBuilder) -> None:
        view = populated_builder.get_dependencies("nonexistent")
        assert view.upstream == []
        assert view.downstream == []
        assert view.transitive_dependencies == []

    def test_leaf_node_has_no_downstream(self, populated_builder: ServiceGraphBuilder) -> None:
        view = populated_builder.get_dependencies("postgres")
        assert view.downstream == []
        assert len(view.upstream) == 2  # user-service and order-service


# =========================================================================
# Cycle Detection
# =========================================================================


class TestCycleDetection:
    """Tests for cycle detection in the service graph."""

    def test_no_cycles_in_dag(self, populated_builder: ServiceGraphBuilder) -> None:
        cycles = populated_builder.detect_cycles()
        assert cycles == []

    def test_single_cycle(self, builder: ServiceGraphBuilder) -> None:
        builder.add_edge(ServiceEdge(source="a", target="b"))
        builder.add_edge(ServiceEdge(source="b", target="c"))
        builder.add_edge(ServiceEdge(source="c", target="a"))

        cycles = builder.detect_cycles()
        assert len(cycles) == 1
        # The cycle should include a, b, c
        cycle_set = set(cycles[0][:-1])  # Exclude repeated start node
        assert cycle_set == {"a", "b", "c"}

    def test_multiple_cycles(self, builder: ServiceGraphBuilder) -> None:
        # Cycle 1: a -> b -> a
        builder.add_edge(ServiceEdge(source="a", target="b"))
        builder.add_edge(ServiceEdge(source="b", target="a"))
        # Cycle 2: c -> d -> c
        builder.add_edge(ServiceEdge(source="c", target="d"))
        builder.add_edge(ServiceEdge(source="d", target="c"))

        cycles = builder.detect_cycles()
        assert len(cycles) >= 2

    def test_self_loop(self, builder: ServiceGraphBuilder) -> None:
        builder.add_edge(ServiceEdge(source="a", target="a"))
        cycles = builder.detect_cycles()
        assert len(cycles) == 1
        assert cycles[0] == ["a", "a"]


# =========================================================================
# Critical Path (BFS shortest path)
# =========================================================================


class TestCriticalPath:
    """Tests for the BFS shortest path finder."""

    def test_direct_path(self, populated_builder: ServiceGraphBuilder) -> None:
        path = populated_builder.get_critical_path("api-gateway", "user-service")
        assert path == ["api-gateway", "user-service"]

    def test_multi_hop_path(self, populated_builder: ServiceGraphBuilder) -> None:
        path = populated_builder.get_critical_path("api-gateway", "postgres")
        assert path is not None
        assert path[0] == "api-gateway"
        assert path[-1] == "postgres"
        assert len(path) == 3  # api-gateway -> user-service -> postgres (or order-service)

    def test_no_path(self, populated_builder: ServiceGraphBuilder) -> None:
        path = populated_builder.get_critical_path("postgres", "api-gateway")
        assert path is None

    def test_same_source_and_target(self, populated_builder: ServiceGraphBuilder) -> None:
        path = populated_builder.get_critical_path("api-gateway", "api-gateway")
        assert path == ["api-gateway"]


# =========================================================================
# merge_from_traces()
# =========================================================================


class TestMergeFromTraces:
    """Tests for extracting edges from OpenTelemetry span data."""

    def test_extract_edges_from_spans(self, builder: ServiceGraphBuilder) -> None:
        traces = [
            {
                "trace_id": "trace-1",
                "spans": [
                    {
                        "span_id": "span-1",
                        "service.name": "frontend",
                    },
                    {
                        "span_id": "span-2",
                        "service.name": "backend",
                        "parent_span_id": "span-1",
                    },
                ],
            }
        ]
        new_edges = builder.merge_from_traces(traces)
        assert new_edges == 1
        smap = builder.get_map()
        assert len(smap.edges) == 1
        assert smap.edges[0].source == "frontend"
        assert smap.edges[0].target == "backend"

    def test_parent_service_field(self, builder: ServiceGraphBuilder) -> None:
        traces = [
            {
                "spans": [
                    {
                        "span_id": "s1",
                        "service_name": "checkout",
                        "parent_service": "cart",
                    },
                ]
            }
        ]
        new_edges = builder.merge_from_traces(traces)
        assert new_edges == 1
        smap = builder.get_map()
        assert smap.edges[0].source == "cart"
        assert smap.edges[0].target == "checkout"

    def test_missing_fields_gracefully_skipped(self, builder: ServiceGraphBuilder) -> None:
        traces = [
            {
                "spans": [
                    {"span_id": "s1"},  # No service name
                    {"service.name": "svc-a"},  # No span_id
                ]
            }
        ]
        new_edges = builder.merge_from_traces(traces)
        assert new_edges == 0

    def test_dedup_across_traces(self, builder: ServiceGraphBuilder) -> None:
        span_data = {
            "spans": [
                {"span_id": "s1", "service.name": "a"},
                {"span_id": "s2", "service.name": "b", "parent_span_id": "s1"},
            ]
        }
        builder.merge_from_traces([span_data])
        new_edges = builder.merge_from_traces([span_data])
        assert new_edges == 0  # Already exists
        assert len(builder.get_map().edges) == 1

    def test_auto_creates_nodes(self, builder: ServiceGraphBuilder) -> None:
        traces = [
            {
                "spans": [
                    {"span_id": "s1", "service.name": "alpha"},
                    {
                        "span_id": "s2",
                        "service.name": "beta",
                        "parent_span_id": "s1",
                    },
                ]
            }
        ]
        builder.merge_from_traces(traces)
        assert builder.get_node("alpha") is not None
        assert builder.get_node("beta") is not None
        assert builder.get_node("alpha").discovered_via == "trace"


# =========================================================================
# merge_from_k8s()
# =========================================================================


class TestMergeFromK8s:
    """Tests for extracting nodes from Kubernetes service data."""

    def test_extract_nodes(self, builder: ServiceGraphBuilder) -> None:
        services = [
            {"name": "frontend", "namespace": "prod", "type": "service"},
            {"name": "backend", "namespace": "prod", "type": "service"},
        ]
        new_nodes = builder.merge_from_k8s(services)
        assert new_nodes == 2
        assert builder.get_node("prod/frontend") is not None
        assert builder.get_node("prod/backend") is not None

    def test_default_namespace(self, builder: ServiceGraphBuilder) -> None:
        services = [{"name": "api"}]
        builder.merge_from_k8s(services)
        node = builder.get_node("default/api")
        assert node is not None
        assert node.metadata["namespace"] == "default"

    def test_missing_name_skipped(self, builder: ServiceGraphBuilder) -> None:
        services = [{"namespace": "prod"}, {"name": "valid"}]
        new_nodes = builder.merge_from_k8s(services)
        assert new_nodes == 1

    def test_idempotent_update(self, builder: ServiceGraphBuilder) -> None:
        services = [{"name": "api", "namespace": "prod"}]
        n1 = builder.merge_from_k8s(services)
        n2 = builder.merge_from_k8s(services)
        assert n1 == 1
        assert n2 == 0  # Already existed

    def test_metadata_captured(self, builder: ServiceGraphBuilder) -> None:
        services = [
            {
                "name": "web",
                "namespace": "staging",
                "labels": {"app": "web", "tier": "frontend"},
                "cluster_ip": "10.96.0.5",
                "ports": [{"port": 80, "protocol": "TCP"}],
            }
        ]
        builder.merge_from_k8s(services)
        node = builder.get_node("staging/web")
        assert node.metadata["labels"]["app"] == "web"
        assert node.metadata["cluster_ip"] == "10.96.0.5"
        assert node.discovered_via == "k8s"


# =========================================================================
# merge_from_config()
# =========================================================================


class TestMergeFromConfig:
    """Tests for manually declared dependencies."""

    def test_add_declared_edges(self, builder: ServiceGraphBuilder) -> None:
        decls = [
            {"source": "api", "target": "db", "edge_type": "queries"},
            {"source": "api", "target": "cache", "edge_type": "reads"},
        ]
        new_edges = builder.merge_from_config(decls)
        assert new_edges == 2
        smap = builder.get_map()
        assert len(smap.edges) == 2

    def test_missing_fields_skipped(self, builder: ServiceGraphBuilder) -> None:
        decls = [
            {"source": "api"},  # No target
            {"target": "db"},  # No source
            {},  # Empty
        ]
        new_edges = builder.merge_from_config(decls)
        assert new_edges == 0

    def test_auto_creates_nodes(self, builder: ServiceGraphBuilder) -> None:
        decls = [{"source": "frontend", "target": "backend"}]
        builder.merge_from_config(decls)
        assert builder.get_node("frontend") is not None
        assert builder.get_node("backend") is not None
        assert builder.get_node("frontend").discovered_via == "config"

    def test_dedup_declared_edges(self, builder: ServiceGraphBuilder) -> None:
        decls = [{"source": "a", "target": "b"}]
        builder.merge_from_config(decls)
        n2 = builder.merge_from_config(decls)
        assert n2 == 0
        assert len(builder.get_map().edges) == 1


# =========================================================================
# Clear
# =========================================================================


class TestClear:
    """Tests for graph reset."""

    def test_clear_empties_graph(self, populated_builder: ServiceGraphBuilder) -> None:
        populated_builder.clear()
        smap = populated_builder.get_map()
        assert smap.nodes == []
        assert smap.edges == []


# =========================================================================
# API Routes
# =========================================================================


class TestTopologyAPIRoutes:
    """Tests for the /topology FastAPI routes."""

    def test_get_map(self, api_client: TestClient) -> None:
        resp = api_client.get("/topology/map")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 5
        assert len(data["edges"]) == 5

    def test_get_dependencies(self, api_client: TestClient) -> None:
        resp = api_client.get("/topology/service/order-service/dependencies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service_id"] == "order-service"
        downstream_ids = [d["service_id"] for d in data["downstream"]]
        assert "postgres" in downstream_ids
        assert "redis" in downstream_ids

    def test_get_dependencies_transitive(self, api_client: TestClient) -> None:
        resp = api_client.get("/topology/service/api-gateway/dependencies?transitive=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "postgres" in data["transitive_dependencies"]
        assert "redis" in data["transitive_dependencies"]

    def test_post_traces(self, api_client: TestClient) -> None:
        payload = {
            "traces": [
                {
                    "spans": [
                        {"span_id": "s1", "service.name": "new-svc"},
                        {
                            "span_id": "s2",
                            "service.name": "new-dep",
                            "parent_span_id": "s1",
                        },
                    ]
                }
            ]
        }
        resp = api_client.post("/topology/traces", json=payload)
        assert resp.status_code == 200
        assert resp.json()["new_edges"] == 1

    def test_post_k8s(self, api_client: TestClient) -> None:
        payload = {
            "services": [
                {"name": "k8s-svc", "namespace": "test"},
            ]
        }
        resp = api_client.post("/topology/k8s", json=payload)
        assert resp.status_code == 200
        assert resp.json()["new_nodes"] == 1

    def test_post_declare(self, api_client: TestClient) -> None:
        payload = {
            "declarations": [
                {"source": "svc-x", "target": "svc-y", "edge_type": "calls"},
            ]
        }
        resp = api_client.post("/topology/declare", json=payload)
        assert resp.status_code == 200
        assert resp.json()["new_edges"] == 1

    def test_get_cycles(self, api_client: TestClient) -> None:
        resp = api_client.get("/topology/cycles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cycles"] == []
        assert data["count"] == 0

    def test_get_path(self, api_client: TestClient) -> None:
        resp = api_client.get("/topology/path?source=api-gateway&target=postgres")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["path"][0] == "api-gateway"
        assert data["path"][-1] == "postgres"

    def test_get_path_no_route(self, api_client: TestClient) -> None:
        resp = api_client.get("/topology/path?source=postgres&target=api-gateway")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is False
        assert data["path"] is None

    def test_503_without_builder(self) -> None:
        """Routes return 503 when no builder is wired."""
        app = FastAPI()
        app.include_router(topology_routes.router)
        topology_routes._builder = None
        client = TestClient(app)

        resp = client.get("/topology/map")
        assert resp.status_code == 503
