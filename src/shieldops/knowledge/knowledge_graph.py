"""Knowledge Graph Manager — manage knowledge graph relationships, detect orphan nodes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class NodeType(StrEnum):
    SERVICE = "service"
    RUNBOOK = "runbook"
    ALERT = "alert"
    TEAM = "team"
    INCIDENT = "incident"


class RelationshipType(StrEnum):
    DEPENDS_ON = "depends_on"
    OWNED_BY = "owned_by"
    TRIGGERS = "triggers"
    RESOLVES = "resolves"
    DOCUMENTS = "documents"


class GraphHealth(StrEnum):
    CONNECTED = "connected"
    SPARSE = "sparse"
    FRAGMENTED = "fragmented"
    ORPHANED = "orphaned"
    EMPTY = "empty"


# --- Models ---


class GraphRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = ""
    node_type: NodeType = NodeType.SERVICE
    relationship_type: RelationshipType = RelationshipType.DEPENDS_ON
    graph_health: GraphHealth = GraphHealth.EMPTY
    connectivity_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class GraphEdge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = ""
    node_type: NodeType = NodeType.SERVICE
    edge_weight: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeGraphReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_edges: int = 0
    orphan_nodes: int = 0
    avg_connectivity_score: float = 0.0
    by_node_type: dict[str, int] = Field(default_factory=dict)
    by_relationship: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    top_orphans: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeGraphManager:
    """Manage knowledge graph relationships, detect orphan nodes."""

    def __init__(
        self,
        max_records: int = 200000,
        max_orphan_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_orphan_pct = max_orphan_pct
        self._records: list[GraphRecord] = []
        self._edges: list[GraphEdge] = []
        logger.info(
            "knowledge_graph.initialized",
            max_records=max_records,
            max_orphan_pct=max_orphan_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_node(
        self,
        node_id: str,
        node_type: NodeType = NodeType.SERVICE,
        relationship_type: RelationshipType = RelationshipType.DEPENDS_ON,
        graph_health: GraphHealth = GraphHealth.EMPTY,
        connectivity_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> GraphRecord:
        record = GraphRecord(
            node_id=node_id,
            node_type=node_type,
            relationship_type=relationship_type,
            graph_health=graph_health,
            connectivity_score=connectivity_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_graph.node_recorded",
            record_id=record.id,
            node_id=node_id,
            node_type=node_type.value,
            graph_health=graph_health.value,
        )
        return record

    def get_node(self, record_id: str) -> GraphRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_nodes(
        self,
        node_type: NodeType | None = None,
        relationship: RelationshipType | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[GraphRecord]:
        results = list(self._records)
        if node_type is not None:
            results = [r for r in results if r.node_type == node_type]
        if relationship is not None:
            results = [r for r in results if r.relationship_type == relationship]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_edge(
        self,
        node_id: str,
        node_type: NodeType = NodeType.SERVICE,
        edge_weight: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> GraphEdge:
        edge = GraphEdge(
            node_id=node_id,
            node_type=node_type,
            edge_weight=edge_weight,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._edges.append(edge)
        if len(self._edges) > self._max_records:
            self._edges = self._edges[-self._max_records :]
        logger.info(
            "knowledge_graph.edge_added",
            node_id=node_id,
            node_type=node_type.value,
            edge_weight=edge_weight,
        )
        return edge

    # -- domain operations --------------------------------------------------

    def analyze_graph_connectivity(self) -> dict[str, Any]:
        """Group by node_type; return count and avg connectivity score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.node_type.value
            type_data.setdefault(key, []).append(r.connectivity_score)
        result: dict[str, Any] = {}
        for ntype, scores in type_data.items():
            result[ntype] = {
                "count": len(scores),
                "avg_connectivity": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_orphan_nodes(self) -> list[dict[str, Any]]:
        """Return records where graph_health is ORPHANED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.graph_health == GraphHealth.ORPHANED:
                results.append(
                    {
                        "record_id": r.id,
                        "node_id": r.node_id,
                        "node_type": r.node_type.value,
                        "connectivity_score": r.connectivity_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_connectivity(self) -> list[dict[str, Any]]:
        """Group by node_id, avg connectivity_score, sort ascending."""
        node_scores: dict[str, list[float]] = {}
        for r in self._records:
            node_scores.setdefault(r.node_id, []).append(r.connectivity_score)
        results: list[dict[str, Any]] = []
        for node_id, scores in node_scores.items():
            results.append(
                {
                    "node_id": node_id,
                    "avg_connectivity": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_connectivity"])
        return results

    def detect_graph_trends(self) -> dict[str, Any]:
        """Split-half comparison on edge_weight; delta threshold 5.0."""
        if len(self._edges) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [e.edge_weight for e in self._edges]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "growing"
        else:
            trend = "shrinking"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> KnowledgeGraphReport:
        by_node_type: dict[str, int] = {}
        by_relationship: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for r in self._records:
            by_node_type[r.node_type.value] = by_node_type.get(r.node_type.value, 0) + 1
            by_relationship[r.relationship_type.value] = (
                by_relationship.get(r.relationship_type.value, 0) + 1
            )
            by_health[r.graph_health.value] = by_health.get(r.graph_health.value, 0) + 1
        orphan_nodes = sum(1 for r in self._records if r.graph_health == GraphHealth.ORPHANED)
        scores = [r.connectivity_score for r in self._records]
        avg_connectivity_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        orphan_list = self.identify_orphan_nodes()
        top_orphans = [o["node_id"] for o in orphan_list[:5]]
        recs: list[str] = []
        if self._records:
            orphan_pct = round(orphan_nodes / len(self._records) * 100, 2)
            if orphan_pct > self._max_orphan_pct:
                recs.append(
                    f"Orphan rate {orphan_pct}% exceeds threshold ({self._max_orphan_pct}%)"
                )
        if orphan_nodes > 0:
            recs.append(f"{orphan_nodes} orphan node(s) — connect or remove from graph")
        if not recs:
            recs.append("Knowledge graph connectivity is healthy")
        return KnowledgeGraphReport(
            total_records=len(self._records),
            total_edges=len(self._edges),
            orphan_nodes=orphan_nodes,
            avg_connectivity_score=avg_connectivity_score,
            by_node_type=by_node_type,
            by_relationship=by_relationship,
            by_health=by_health,
            top_orphans=top_orphans,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._edges.clear()
        logger.info("knowledge_graph.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.node_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_edges": len(self._edges),
            "max_orphan_pct": self._max_orphan_pct,
            "node_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
