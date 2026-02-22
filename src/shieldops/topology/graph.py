"""Service dependency graph builder.

Constructs and queries a directed graph of service dependencies
from multiple discovery sources: OpenTelemetry traces, Kubernetes
service discovery, and manual configuration declarations.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Pydantic Models ─────────────────────────────────────────────


class ServiceNode(BaseModel):
    """A node in the service dependency graph."""

    id: str
    name: str
    type: str = "service"  # service, database, cache, queue, external
    metadata: dict[str, Any] = Field(default_factory=dict)
    health: str = "unknown"
    discovered_via: str = "manual"


class ServiceEdge(BaseModel):
    """A directed edge representing a dependency between two services."""

    source: str
    target: str
    edge_type: str = "calls"
    latency_p50: float | None = None
    latency_p99: float | None = None
    request_rate: float | None = None
    error_rate: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServiceMap(BaseModel):
    """Complete snapshot of the service topology."""

    nodes: list[ServiceNode]
    edges: list[ServiceEdge]
    updated_at: datetime
    sources: list[str]


class DependencyView(BaseModel):
    """Dependency view for a single service."""

    service_id: str
    upstream: list[dict[str, Any]]
    downstream: list[dict[str, Any]]
    transitive_dependencies: list[str]


# ── Graph Builder ────────────────────────────────────────────────


class ServiceGraphBuilder:
    """Builds and queries a directed service dependency graph.

    Supports multiple ingestion sources (traces, K8s, config) and
    provides graph analysis operations: cycle detection, shortest
    path, and transitive dependency resolution.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, ServiceNode] = {}
        self._edges: list[ServiceEdge] = []
        self._edge_index: dict[tuple[str, str], int] = {}

    # ── Node Operations ──────────────────────────────────────────

    def add_node(self, node: ServiceNode) -> None:
        """Add or update a service node."""
        self._nodes[node.id] = node
        logger.debug("node_added", node_id=node.id, name=node.name)

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all edges referencing it.

        Returns True if the node existed, False otherwise.
        """
        if node_id not in self._nodes:
            return False

        del self._nodes[node_id]

        # Remove edges that reference this node and rebuild index
        self._edges = [e for e in self._edges if e.source != node_id and e.target != node_id]
        self._rebuild_edge_index()
        logger.debug("node_removed", node_id=node_id)
        return True

    def get_node(self, node_id: str) -> ServiceNode | None:
        """Retrieve a node by ID, or None if not found."""
        return self._nodes.get(node_id)

    # ── Edge Operations ──────────────────────────────────────────

    def add_edge(self, edge: ServiceEdge) -> None:
        """Add or update an edge (deduplicated by source+target)."""
        key = (edge.source, edge.target)
        if key in self._edge_index:
            self._edges[self._edge_index[key]] = edge
        else:
            self._edge_index[key] = len(self._edges)
            self._edges.append(edge)
        logger.debug(
            "edge_added",
            source=edge.source,
            target=edge.target,
            edge_type=edge.edge_type,
        )

    # ── Map & Dependency Queries ─────────────────────────────────

    def get_map(self) -> ServiceMap:
        """Return the full service map snapshot."""
        sources: list[str] = []
        for node in self._nodes.values():
            if node.discovered_via not in sources:
                sources.append(node.discovered_via)
        return ServiceMap(
            nodes=list(self._nodes.values()),
            edges=list(self._edges),
            updated_at=datetime.now(UTC),
            sources=sources,
        )

    def get_dependencies(
        self,
        service_id: str,
        include_transitive: bool = False,
    ) -> DependencyView:
        """Get upstream and downstream dependencies for a service.

        Upstream: services that call *this* service (edges where target == service_id).
        Downstream: services that *this* service calls (edges where source == service_id).
        Transitive: BFS walk of all downstream dependencies.
        """
        upstream: list[dict[str, Any]] = []
        downstream: list[dict[str, Any]] = []

        for edge in self._edges:
            if edge.target == service_id:
                upstream.append(
                    {
                        "service_id": edge.source,
                        "edge_type": edge.edge_type,
                        "latency_p50": edge.latency_p50,
                        "error_rate": edge.error_rate,
                    }
                )
            if edge.source == service_id:
                downstream.append(
                    {
                        "service_id": edge.target,
                        "edge_type": edge.edge_type,
                        "latency_p50": edge.latency_p50,
                        "error_rate": edge.error_rate,
                    }
                )

        transitive: list[str] = []
        if include_transitive:
            transitive = self._bfs_downstream(service_id)

        return DependencyView(
            service_id=service_id,
            upstream=upstream,
            downstream=downstream,
            transitive_dependencies=transitive,
        )

    # ── Graph Analysis ───────────────────────────────────────────

    def detect_cycles(self) -> list[list[str]]:
        """Detect all cycles in the service graph using DFS.

        Returns a list of cycles, where each cycle is a list of
        node IDs forming the cycle path.
        """
        adjacency: dict[str, list[str]] = defaultdict(list)
        for edge in self._edges:
            adjacency[edge.source].append(edge.target)

        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: list[list[str]] = []
        path: list[str] = []

        def _dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    _dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found a cycle: extract from path
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.discard(node)

        all_nodes = set(self._nodes.keys())
        for edge in self._edges:
            all_nodes.add(edge.source)
            all_nodes.add(edge.target)

        for node in sorted(all_nodes):
            if node not in visited:
                _dfs(node)

        return cycles

    def get_critical_path(
        self,
        source: str,
        target: str,
    ) -> list[str] | None:
        """Find shortest path between two services using BFS.

        Returns the path as a list of node IDs, or None if no path exists.
        """
        if source == target:
            return [source]

        adjacency: dict[str, list[str]] = defaultdict(list)
        for edge in self._edges:
            adjacency[edge.source].append(edge.target)

        visited: set[str] = {source}
        queue: deque[list[str]] = deque([[source]])

        while queue:
            current_path = queue.popleft()
            current_node = current_path[-1]

            for neighbor in adjacency.get(current_node, []):
                if neighbor == target:
                    return current_path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(current_path + [neighbor])

        return None

    # ── Source Ingestion ─────────────────────────────────────────

    def merge_from_traces(self, traces: list[dict[str, Any]]) -> int:
        """Extract service dependencies from OpenTelemetry span data.

        Each trace dict is expected to contain a ``spans`` list.
        Each span should have ``service.name`` (or ``service_name``)
        and optionally a ``parent_service`` field for inter-service
        calls.

        Returns the count of *new* edges added.
        """
        new_edges = 0

        for trace in traces:
            spans = trace.get("spans", [])
            service_spans: dict[str, str] = {}

            # Index span_id -> service_name
            for span in spans:
                service_name = span.get("service.name") or span.get("service_name") or ""
                span_id = span.get("span_id", "")
                if service_name and span_id:
                    service_spans[span_id] = service_name

            # Build edges from parent relationships
            for span in spans:
                child_service = span.get("service.name") or span.get("service_name") or ""
                parent_service = span.get("parent_service", "")

                # If parent_service is not directly given, resolve via parent_span_id
                if not parent_service:
                    parent_span_id = span.get("parent_span_id", "")
                    if parent_span_id:
                        parent_service = service_spans.get(parent_span_id, "")

                if parent_service and child_service and parent_service != child_service:
                    key = (parent_service, child_service)
                    if key not in self._edge_index:
                        # Auto-create nodes
                        if parent_service not in self._nodes:
                            self.add_node(
                                ServiceNode(
                                    id=parent_service,
                                    name=parent_service,
                                    discovered_via="trace",
                                )
                            )
                        if child_service not in self._nodes:
                            self.add_node(
                                ServiceNode(
                                    id=child_service,
                                    name=child_service,
                                    discovered_via="trace",
                                )
                            )

                        self.add_edge(
                            ServiceEdge(
                                source=parent_service,
                                target=child_service,
                                edge_type="calls",
                                metadata={"discovered_via": "trace"},
                            )
                        )
                        new_edges += 1

        logger.info("traces_merged", new_edges=new_edges)
        return new_edges

    def merge_from_k8s(self, services: list[dict[str, Any]]) -> int:
        """Extract nodes from Kubernetes service discovery data.

        Each dict should have at minimum a ``name`` field.
        Optional fields: ``namespace``, ``type``, ``labels``,
        ``cluster_ip``, ``ports``.

        Returns the count of *new* nodes added.
        """
        new_nodes = 0

        for svc in services:
            name = svc.get("name", "")
            if not name:
                logger.warning("k8s_service_missing_name", service=svc)
                continue

            namespace = svc.get("namespace", "default")
            node_id = f"{namespace}/{name}"

            if node_id not in self._nodes:
                new_nodes += 1

            self.add_node(
                ServiceNode(
                    id=node_id,
                    name=name,
                    type=svc.get("type", "service"),
                    metadata={
                        "namespace": namespace,
                        "labels": svc.get("labels", {}),
                        "cluster_ip": svc.get("cluster_ip"),
                        "ports": svc.get("ports", []),
                    },
                    discovered_via="k8s",
                )
            )

        logger.info("k8s_services_merged", new_nodes=new_nodes)
        return new_nodes

    def merge_from_config(self, declarations: list[dict[str, Any]]) -> int:
        """Ingest manually declared service dependencies.

        Each declaration dict should have ``source`` and ``target``
        fields (service IDs), and optionally ``edge_type``.

        Returns the count of *new* edges added.
        """
        new_edges = 0

        for decl in declarations:
            source = decl.get("source", "")
            target = decl.get("target", "")

            if not source or not target:
                logger.warning("config_declaration_missing_fields", declaration=decl)
                continue

            key = (source, target)
            if key not in self._edge_index:
                new_edges += 1

            # Auto-create nodes if they don't exist
            if source not in self._nodes:
                self.add_node(
                    ServiceNode(
                        id=source,
                        name=source,
                        discovered_via="config",
                    )
                )
            if target not in self._nodes:
                self.add_node(
                    ServiceNode(
                        id=target,
                        name=target,
                        discovered_via="config",
                    )
                )

            self.add_edge(
                ServiceEdge(
                    source=source,
                    target=target,
                    edge_type=decl.get("edge_type", "calls"),
                    metadata={"discovered_via": "config"},
                )
            )

        logger.info("config_declarations_merged", new_edges=new_edges)
        return new_edges

    # ── Lifecycle ────────────────────────────────────────────────

    def clear(self) -> None:
        """Reset the graph, removing all nodes and edges."""
        self._nodes.clear()
        self._edges.clear()
        self._edge_index.clear()
        logger.info("graph_cleared")

    # ── Private Helpers ──────────────────────────────────────────

    def _bfs_downstream(self, start: str) -> list[str]:
        """BFS walk of all transitive downstream dependencies."""
        adjacency: dict[str, list[str]] = defaultdict(list)
        for edge in self._edges:
            adjacency[edge.source].append(edge.target)

        visited: set[str] = set()
        queue: deque[str] = deque()

        # Seed with direct downstream neighbors
        for neighbor in adjacency.get(start, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

        while queue:
            current = queue.popleft()
            for neighbor in adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return sorted(visited)

    def _rebuild_edge_index(self) -> None:
        """Rebuild the edge dedup index after mutation."""
        self._edge_index = {(e.source, e.target): i for i, e in enumerate(self._edges)}
