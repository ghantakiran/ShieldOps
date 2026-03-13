"""Incident Knowledge Graph Engine — compute knowledge connections,
detect knowledge gaps, rank nodes by incident centrality."""

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
    INCIDENT = "incident"
    ROOT_CAUSE = "root_cause"
    SERVICE = "service"
    TEAM = "team"


class EdgeType(StrEnum):
    CAUSED_BY = "caused_by"
    AFFECTED = "affected"
    RESOLVED_BY = "resolved_by"
    PREVENTED = "prevented"


class GraphScope(StrEnum):
    SERVICE = "service"
    TEAM = "team"
    ORGANIZATION = "organization"
    CROSS_ORG = "cross_org"


# --- Models ---


class KnowledgeGraphRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_node: str = ""
    target_node: str = ""
    node_type: NodeType = NodeType.INCIDENT
    edge_type: EdgeType = EdgeType.CAUSED_BY
    graph_scope: GraphScope = GraphScope.SERVICE
    weight: float = 1.0
    service: str = ""
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeGraphAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_node: str = ""
    node_type: NodeType = NodeType.INCIDENT
    connection_count: int = 0
    centrality_score: float = 0.0
    has_gaps: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeGraphReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_weight: float = 0.0
    by_node_type: dict[str, int] = Field(default_factory=dict)
    by_edge_type: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentKnowledgeGraphEngine:
    """Compute knowledge connections, detect knowledge gaps,
    rank nodes by incident centrality."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[KnowledgeGraphRecord] = []
        self._analyses: dict[str, KnowledgeGraphAnalysis] = {}
        logger.info(
            "incident_knowledge_graph_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        source_node: str = "",
        target_node: str = "",
        node_type: NodeType = NodeType.INCIDENT,
        edge_type: EdgeType = EdgeType.CAUSED_BY,
        graph_scope: GraphScope = GraphScope.SERVICE,
        weight: float = 1.0,
        service: str = "",
        team: str = "",
        description: str = "",
    ) -> KnowledgeGraphRecord:
        record = KnowledgeGraphRecord(
            source_node=source_node,
            target_node=target_node,
            node_type=node_type,
            edge_type=edge_type,
            graph_scope=graph_scope,
            weight=weight,
            service=service,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_knowledge_graph.record_added",
            record_id=record.id,
            source_node=source_node,
        )
        return record

    def process(self, key: str) -> KnowledgeGraphAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        connections = sum(
            1
            for r in self._records
            if r.source_node == rec.source_node or r.target_node == rec.source_node
        )
        total_weight = sum(
            r.weight
            for r in self._records
            if r.source_node == rec.source_node or r.target_node == rec.source_node
        )
        centrality = round(total_weight / len(self._records), 4) if self._records else 0.0
        has_gaps = connections < 2
        analysis = KnowledgeGraphAnalysis(
            source_node=rec.source_node,
            node_type=rec.node_type,
            connection_count=connections,
            centrality_score=centrality,
            has_gaps=has_gaps,
            description=f"Node {rec.source_node} connections {connections}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> KnowledgeGraphReport:
        by_nt: dict[str, int] = {}
        by_et: dict[str, int] = {}
        by_sc: dict[str, int] = {}
        weights: list[float] = []
        for r in self._records:
            by_nt[r.node_type.value] = by_nt.get(r.node_type.value, 0) + 1
            by_et[r.edge_type.value] = by_et.get(r.edge_type.value, 0) + 1
            by_sc[r.graph_scope.value] = by_sc.get(r.graph_scope.value, 0) + 1
            weights.append(r.weight)
        avg = round(sum(weights) / len(weights), 2) if weights else 0.0
        recs: list[str] = []
        unique_nodes = len({r.source_node for r in self._records})
        if unique_nodes < 3 and self._records:
            recs.append("Knowledge graph has limited node diversity")
        if not recs:
            recs.append("Knowledge graph connectivity within acceptable range")
        return KnowledgeGraphReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_weight=avg,
            by_node_type=by_nt,
            by_edge_type=by_et,
            by_scope=by_sc,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        node_dist: dict[str, int] = {}
        for r in self._records:
            k = r.node_type.value
            node_dist[k] = node_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "node_type_distribution": node_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("incident_knowledge_graph_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_knowledge_connections(self) -> list[dict[str, Any]]:
        """Compute connection count and weight per node."""
        node_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            for node in (r.source_node, r.target_node):
                if node not in node_data:
                    node_data[node] = {"connections": 0, "total_weight": 0.0}
                node_data[node]["connections"] += 1
                node_data[node]["total_weight"] += r.weight
        results: list[dict[str, Any]] = []
        for node, data in node_data.items():
            results.append(
                {
                    "node": node,
                    "connection_count": data["connections"],
                    "total_weight": round(data["total_weight"], 2),
                    "avg_weight": round(data["total_weight"] / data["connections"], 2),
                }
            )
        results.sort(key=lambda x: x["connection_count"], reverse=True)
        return results

    def detect_knowledge_gaps(self) -> list[dict[str, Any]]:
        """Detect nodes with low connectivity (knowledge gaps)."""
        node_connections: dict[str, int] = {}
        for r in self._records:
            node_connections[r.source_node] = node_connections.get(r.source_node, 0) + 1
            node_connections[r.target_node] = node_connections.get(r.target_node, 0) + 1
        avg_conn = (
            sum(node_connections.values()) / len(node_connections) if node_connections else 0.0
        )
        results: list[dict[str, Any]] = []
        for node, count in node_connections.items():
            if count < avg_conn * 0.5:
                results.append(
                    {
                        "node": node,
                        "connection_count": count,
                        "avg_connections": round(avg_conn, 2),
                        "gap_severity": "high" if count == 1 else "medium",
                    }
                )
        results.sort(key=lambda x: x["connection_count"])
        return results

    def rank_nodes_by_incident_centrality(self) -> list[dict[str, Any]]:
        """Rank nodes by centrality in incident graph."""
        node_weights: dict[str, float] = {}
        node_types: dict[str, str] = {}
        for r in self._records:
            node_weights[r.source_node] = node_weights.get(r.source_node, 0.0) + r.weight
            node_types[r.source_node] = r.node_type.value
        total_weight = sum(node_weights.values()) if node_weights else 1.0
        results: list[dict[str, Any]] = []
        for node, weight in node_weights.items():
            centrality = round(weight / total_weight, 4)
            results.append(
                {
                    "node": node,
                    "node_type": node_types[node],
                    "centrality_score": centrality,
                    "total_weight": round(weight, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["centrality_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
