"""Infrastructure topology mapping with relationship tracking.

Maps infrastructure nodes (services, databases, caches, queues, etc.) and their
relationships (dependencies, data flows, load balancing) to provide visibility
into topology, critical paths, and blast-radius analysis.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class NodeType(enum.StrEnum):
    SERVICE = "service"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    LOAD_BALANCER = "load_balancer"
    CDN = "cdn"
    STORAGE = "storage"
    EXTERNAL_API = "external_api"


class RelationshipType(enum.StrEnum):
    DEPENDS_ON = "depends_on"
    PROVIDES_DATA = "provides_data"
    COMMUNICATES_WITH = "communicates_with"
    LOAD_BALANCES = "load_balances"
    CACHES_FOR = "caches_for"


# -- Models --------------------------------------------------------------------


class TopologyNode(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    node_type: NodeType
    environment: str = "production"
    provider: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    health_status: str = "unknown"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class TopologyRelationship(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class TopologyView(BaseModel):
    total_nodes: int = 0
    total_relationships: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_environment: dict[str, int] = Field(default_factory=dict)
    critical_paths: list[list[str]] = Field(default_factory=list)


# -- Engine --------------------------------------------------------------------


class InfrastructureTopologyMapper:
    """Map infrastructure topology with nodes and relationships.

    Parameters
    ----------
    max_nodes:
        Maximum topology nodes to store.
    max_relationships:
        Maximum relationships to store.
    """

    def __init__(
        self,
        max_nodes: int = 5000,
        max_relationships: int = 20000,
    ) -> None:
        self._nodes: dict[str, TopologyNode] = {}
        self._relationships: dict[str, TopologyRelationship] = {}
        self._max_nodes = max_nodes
        self._max_relationships = max_relationships

    def add_node(
        self,
        name: str,
        node_type: NodeType,
        environment: str = "production",
        provider: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TopologyNode:
        if len(self._nodes) >= self._max_nodes:
            raise ValueError(f"Maximum nodes limit reached: {self._max_nodes}")
        node = TopologyNode(
            name=name,
            node_type=node_type,
            environment=environment,
            provider=provider,
            metadata=metadata or {},
        )
        self._nodes[node.id] = node
        logger.info("topology_node_added", node_id=node.id, name=name, node_type=node_type)
        return node

    def update_node_health(self, node_id: str, health_status: str) -> TopologyNode | None:
        node = self._nodes.get(node_id)
        if node is None:
            return None
        node.health_status = health_status
        node.updated_at = time.time()
        logger.info(
            "topology_node_health_updated",
            node_id=node_id,
            health_status=health_status,
        )
        return node

    def remove_node(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        # Remove all relationships involving this node
        to_remove = [
            rid
            for rid, rel in self._relationships.items()
            if rel.source_id == node_id or rel.target_id == node_id
        ]
        for rid in to_remove:
            del self._relationships[rid]
        logger.info(
            "topology_node_removed",
            node_id=node_id,
            relationships_removed=len(to_remove),
        )
        return True

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: RelationshipType,
        latency_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> TopologyRelationship:
        if source_id not in self._nodes:
            raise ValueError(f"Source node not found: {source_id}")
        if target_id not in self._nodes:
            raise ValueError(f"Target node not found: {target_id}")
        if len(self._relationships) >= self._max_relationships:
            raise ValueError(f"Maximum relationships limit reached: {self._max_relationships}")
        relationship = TopologyRelationship(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )
        self._relationships[relationship.id] = relationship
        logger.info(
            "topology_relationship_added",
            relationship_id=relationship.id,
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
        )
        return relationship

    def remove_relationship(self, relationship_id: str) -> bool:
        return self._relationships.pop(relationship_id, None) is not None

    def get_node(self, node_id: str) -> TopologyNode | None:
        return self._nodes.get(node_id)

    def list_nodes(
        self,
        node_type: NodeType | None = None,
        environment: str | None = None,
    ) -> list[TopologyNode]:
        nodes = list(self._nodes.values())
        if node_type:
            nodes = [n for n in nodes if n.node_type == node_type]
        if environment:
            nodes = [n for n in nodes if n.environment == environment]
        return nodes

    def get_node_dependencies(self, node_id: str) -> list[TopologyNode]:
        """Return nodes that this node depends on (outgoing DEPENDS_ON)."""
        targets: list[TopologyNode] = []
        for rel in self._relationships.values():
            if rel.source_id == node_id and rel.relationship_type == RelationshipType.DEPENDS_ON:
                target = self._nodes.get(rel.target_id)
                if target:
                    targets.append(target)
        return targets

    def get_node_dependents(self, node_id: str) -> list[TopologyNode]:
        """Return nodes that depend on this node (incoming DEPENDS_ON)."""
        sources: list[TopologyNode] = []
        for rel in self._relationships.values():
            if rel.target_id == node_id and rel.relationship_type == RelationshipType.DEPENDS_ON:
                source = self._nodes.get(rel.source_id)
                if source:
                    sources.append(source)
        return sources

    def get_topology_view(self, environment: str | None = None) -> TopologyView:
        nodes = list(self._nodes.values())
        rels = list(self._relationships.values())

        if environment:
            env_node_ids = {n.id for n in nodes if n.environment == environment}
            nodes = [n for n in nodes if n.id in env_node_ids]
            rels = [r for r in rels if r.source_id in env_node_ids and r.target_id in env_node_ids]

        by_type: dict[str, int] = {}
        for node in nodes:
            by_type[node.node_type] = by_type.get(node.node_type, 0) + 1

        by_env: dict[str, int] = {}
        for node in nodes:
            by_env[node.environment] = by_env.get(node.environment, 0) + 1

        # Identify critical paths: chains of DEPENDS_ON starting from nodes with
        # no incoming dependencies (simple linear traversal, not full DAG)
        depends_on = [r for r in rels if r.relationship_type == RelationshipType.DEPENDS_ON]
        outgoing: dict[str, list[str]] = {}
        has_incoming: set[str] = set()
        node_ids = {n.id for n in nodes}
        for rel in depends_on:
            if rel.source_id in node_ids and rel.target_id in node_ids:
                outgoing.setdefault(rel.source_id, []).append(rel.target_id)
                has_incoming.add(rel.target_id)

        roots = [nid for nid in node_ids if nid not in has_incoming and nid in outgoing]
        critical_paths: list[list[str]] = []
        for root in roots:
            path = [root]
            current = root
            visited: set[str] = {current}
            while current in outgoing:
                nexts = [n for n in outgoing[current] if n not in visited]
                if not nexts:
                    break
                current = nexts[0]
                visited.add(current)
                path.append(current)
            if len(path) > 1:
                critical_paths.append(path)

        return TopologyView(
            total_nodes=len(nodes),
            total_relationships=len(rels),
            by_type=by_type,
            by_environment=by_env,
            critical_paths=critical_paths,
        )

    def get_stats(self) -> dict[str, Any]:
        healthy = sum(1 for n in self._nodes.values() if n.health_status == "healthy")
        unhealthy = sum(1 for n in self._nodes.values() if n.health_status == "unhealthy")
        environments = sorted({n.environment for n in self._nodes.values()})
        return {
            "total_nodes": len(self._nodes),
            "total_relationships": len(self._relationships),
            "healthy_nodes": healthy,
            "unhealthy_nodes": unhealthy,
            "environments": environments,
            "node_types": sorted({n.node_type for n in self._nodes.values()}),
        }
