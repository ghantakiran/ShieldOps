"""Service Dependency Mapper — map and analyze service dependencies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DependencyType(StrEnum):
    SYNC_HTTP = "sync_http"
    ASYNC_MESSAGE = "async_message"
    DATABASE = "database"
    CACHE = "cache"
    SHARED_STORAGE = "shared_storage"


class DependencyCriticality(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


class GraphHealth(StrEnum):
    HEALTHY = "healthy"
    HAS_CYCLES = "has_cycles"
    SINGLE_POINTS = "single_points"
    DEEP_CHAINS = "deep_chains"
    FRAGILE = "fragile"


# --- Models ---


class DependencyEdge(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    source_service: str = ""
    target_service: str = ""
    dependency_type: DependencyType = DependencyType.SYNC_HTTP
    criticality: DependencyCriticality = DependencyCriticality.MEDIUM
    latency_ms: float = 0.0
    failure_rate_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class DependencyGraph(BaseModel):
    total_services: int = 0
    total_edges: int = 0
    depth: int = 0
    cycles: list[list[str]] = Field(
        default_factory=list,
    )
    single_points: list[str] = Field(
        default_factory=list,
    )
    critical_paths: list[list[str]] = Field(
        default_factory=list,
    )
    health: GraphHealth = GraphHealth.HEALTHY
    created_at: float = Field(default_factory=time.time)


class DependencyMapReport(BaseModel):
    total_services: int = 0
    total_edges: int = 0
    graph_health: GraphHealth = GraphHealth.HEALTHY
    avg_depth: float = 0.0
    by_type: dict[str, int] = Field(
        default_factory=dict,
    )
    by_criticality: dict[str, int] = Field(
        default_factory=dict,
    )
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Mapper ---


class ServiceDependencyMapper:
    """Map and analyze service-to-service dependencies."""

    def __init__(
        self,
        max_edges: int = 200000,
        max_chain_depth: int = 10,
    ) -> None:
        self._max_edges = max_edges
        self._max_chain_depth = max_chain_depth
        self._edges: list[DependencyEdge] = []
        self._graphs: list[DependencyGraph] = []
        logger.info(
            "dependency_mapper.initialized",
            max_edges=max_edges,
            max_chain_depth=max_chain_depth,
        )

    # -- CRUD --

    def register_dependency(
        self,
        source_service: str,
        target_service: str,
        dependency_type: DependencyType = (DependencyType.SYNC_HTTP),
        criticality: DependencyCriticality = (DependencyCriticality.MEDIUM),
        latency_ms: float = 0.0,
        failure_rate_pct: float = 0.0,
    ) -> DependencyEdge:
        edge = DependencyEdge(
            source_service=source_service,
            target_service=target_service,
            dependency_type=dependency_type,
            criticality=criticality,
            latency_ms=latency_ms,
            failure_rate_pct=failure_rate_pct,
        )
        self._edges.append(edge)
        if len(self._edges) > self._max_edges:
            self._edges = self._edges[-self._max_edges :]
        logger.info(
            "dependency_mapper.registered",
            edge_id=edge.id,
            source=source_service,
            target=target_service,
        )
        return edge

    def get_dependency(self, edge_id: str) -> DependencyEdge | None:
        for e in self._edges:
            if e.id == edge_id:
                return e
        return None

    def list_dependencies(
        self,
        source: str | None = None,
        target: str | None = None,
        limit: int = 50,
    ) -> list[DependencyEdge]:
        results = list(self._edges)
        if source is not None:
            results = [e for e in results if e.source_service == source]
        if target is not None:
            results = [e for e in results if e.target_service == target]
        return results[-limit:]

    # -- Domain operations --

    def build_graph(self) -> DependencyGraph:
        adjacency = self._build_adjacency()
        services = self._all_services()
        cycles = self._find_cycles(adjacency)
        single_pts = self._find_single_points(adjacency)
        depth = self._compute_max_depth(adjacency)
        critical = self._find_critical_paths(adjacency)
        health = self._assess_health(cycles, single_pts, depth)
        graph = DependencyGraph(
            total_services=len(services),
            total_edges=len(self._edges),
            depth=depth,
            cycles=cycles,
            single_points=single_pts,
            critical_paths=critical,
            health=health,
        )
        self._graphs.append(graph)
        logger.info(
            "dependency_mapper.graph_built",
            services=len(services),
            edges=len(self._edges),
            health=health.value,
        )
        return graph

    def detect_cycles(self) -> list[list[str]]:
        adjacency = self._build_adjacency()
        return self._find_cycles(adjacency)

    def find_critical_path(self, service_name: str) -> list[str]:
        adjacency = self._build_adjacency()
        path: list[str] = [service_name]
        visited: set[str] = {service_name}
        current = service_name
        for _ in range(self._max_chain_depth):
            neighbors = adjacency.get(current, [])
            critical = [n for n in neighbors if n not in visited]
            if not critical:
                break
            nxt = critical[0]
            for edge in self._edges:
                if (
                    edge.source_service == current
                    and edge.target_service in critical
                    and edge.criticality
                    in (
                        DependencyCriticality.CRITICAL,
                        DependencyCriticality.HIGH,
                    )
                ):
                    nxt = edge.target_service
                    break
            path.append(nxt)
            visited.add(nxt)
            current = nxt
        return path

    def identify_single_points(self) -> list[str]:
        adjacency = self._build_adjacency()
        return self._find_single_points(adjacency)

    def calculate_blast_radius(self, service_name: str) -> dict[str, Any]:
        adjacency = self._build_adjacency()
        affected: set[str] = set()
        queue = [service_name]
        visited: set[str] = {service_name}
        while queue:
            current = queue.pop(0)
            for edge in self._edges:
                if edge.target_service == current:
                    src = edge.source_service
                    if src not in visited:
                        visited.add(src)
                        affected.add(src)
                        queue.append(src)
        downstream: set[str] = set()
        queue2 = [service_name]
        visited2: set[str] = {service_name}
        while queue2:
            current = queue2.pop(0)
            for tgt in adjacency.get(current, []):
                if tgt not in visited2:
                    visited2.add(tgt)
                    downstream.add(tgt)
                    queue2.append(tgt)
        return {
            "service": service_name,
            "upstream_affected": sorted(affected),
            "downstream_affected": sorted(downstream),
            "total_affected": len(affected) + len(downstream),
        }

    # -- Reports --

    def generate_map_report(self) -> DependencyMapReport:
        graph = self.build_graph()
        by_type: dict[str, int] = {}
        by_crit: dict[str, int] = {}
        for e in self._edges:
            by_type[e.dependency_type.value] = by_type.get(e.dependency_type.value, 0) + 1
            by_crit[e.criticality.value] = by_crit.get(e.criticality.value, 0) + 1
        issues: list[str] = []
        recs: list[str] = []
        if graph.cycles:
            issues.append(f"{len(graph.cycles)} circular dependencies")
            recs.append("Break circular dependencies")
        if graph.single_points:
            ct = len(graph.single_points)
            issues.append(f"{ct} single points of failure")
            recs.append("Add redundancy for SPOFs")
        if graph.depth > self._max_chain_depth:
            issues.append(f"Chain depth {graph.depth} exceeds limit {self._max_chain_depth}")
            recs.append("Reduce dependency chain depth")
        return DependencyMapReport(
            total_services=graph.total_services,
            total_edges=graph.total_edges,
            graph_health=graph.health,
            avg_depth=float(graph.depth),
            by_type=by_type,
            by_criticality=by_crit,
            issues=issues,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._edges.clear()
        self._graphs.clear()
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        services = self._all_services()
        return {
            "total_edges": len(self._edges),
            "total_services": len(services),
            "total_graphs_built": len(self._graphs),
            "services": sorted(services),
        }

    # -- Internal helpers --

    def _all_services(self) -> set[str]:
        services: set[str] = set()
        for e in self._edges:
            services.add(e.source_service)
            services.add(e.target_service)
        return services

    def _build_adjacency(
        self,
    ) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = {}
        for e in self._edges:
            adj.setdefault(e.source_service, []).append(e.target_service)
        return adj

    def _find_cycles(self, adj: dict[str, list[str]]) -> list[list[str]]:
        visited: set[str] = set()
        in_stack: set[str] = set()
        cycles: list[list[str]] = []
        path: list[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            in_stack.add(node)
            path.append(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in in_stack:
                    idx = path.index(neighbor)
                    cycle = path[idx:] + [neighbor]
                    cycles.append(cycle)
            path.pop()
            in_stack.discard(node)

        all_nodes = set(adj.keys())
        for e in self._edges:
            all_nodes.add(e.target_service)
        for node in all_nodes:
            if node not in visited:
                dfs(node)
        return cycles

    def _find_single_points(self, adj: dict[str, list[str]]) -> list[str]:
        incoming: dict[str, int] = {}
        for targets in adj.values():
            for t in targets:
                incoming[t] = incoming.get(t, 0) + 1
        singles: list[str] = []
        for svc, count in incoming.items():
            dependents = sum(1 for targets in adj.values() if svc in targets)
            outgoing = len(adj.get(svc, []))
            if (dependents >= 2 and outgoing == 0) or count >= 3:
                singles.append(svc)
        return sorted(set(singles))

    def _compute_max_depth(self, adj: dict[str, list[str]]) -> int:
        memo: dict[str, int] = {}

        def depth(node: str, visited: set[str]) -> int:
            if node in memo:
                return memo[node]
            if node in visited:
                return 0
            visited.add(node)
            neighbors = adj.get(node, [])
            if not neighbors:
                memo[node] = 0
                return 0
            max_d = 0
            for n in neighbors:
                d = depth(n, visited)
                if d + 1 > max_d:
                    max_d = d + 1
            memo[node] = max_d
            visited.discard(node)
            return max_d

        all_nodes = set(adj.keys())
        for e in self._edges:
            all_nodes.add(e.target_service)
        best = 0
        for node in all_nodes:
            d = depth(node, set())
            if d > best:
                best = d
        return best

    def _find_critical_paths(self, adj: dict[str, list[str]]) -> list[list[str]]:
        paths: list[list[str]] = []
        crit_edges = [
            e
            for e in self._edges
            if e.criticality
            in (
                DependencyCriticality.CRITICAL,
                DependencyCriticality.HIGH,
            )
        ]
        visited_paths: set[str] = set()
        for edge in crit_edges:
            path = self.find_critical_path(edge.source_service)
            key = "->".join(path)
            if key not in visited_paths and len(path) > 1:
                visited_paths.add(key)
                paths.append(path)
        return paths

    def _assess_health(
        self,
        cycles: list[list[str]],
        single_points: list[str],
        depth: int,
    ) -> GraphHealth:
        issues = 0
        if cycles:
            issues += 2
        if single_points:
            issues += 1
        if depth > self._max_chain_depth:
            issues += 1
        if issues >= 3:
            return GraphHealth.FRAGILE
        if cycles:
            return GraphHealth.HAS_CYCLES
        if single_points:
            return GraphHealth.SINGLE_POINTS
        if depth > self._max_chain_depth:
            return GraphHealth.DEEP_CHAINS
        return GraphHealth.HEALTHY
