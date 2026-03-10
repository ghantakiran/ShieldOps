"""Security Knowledge Graph Engine
build threat subgraphs, detect hidden relationships,
compute entity centrality."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EntityType(StrEnum):
    ASSET = "asset"
    VULNERABILITY = "vulnerability"
    THREAT_ACTOR = "threat_actor"
    INDICATOR = "indicator"


class RelationType(StrEnum):
    EXPLOITS = "exploits"
    TARGETS = "targets"
    INDICATES = "indicates"
    MITIGATES = "mitigates"


class GraphDepth(StrEnum):
    SHALLOW = "shallow"
    MODERATE = "moderate"
    DEEP = "deep"
    EXHAUSTIVE = "exhaustive"


# --- Models ---


class KnowledgeGraphRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    entity_type: EntityType = EntityType.ASSET
    relation_type: RelationType = RelationType.TARGETS
    graph_depth: GraphDepth = GraphDepth.SHALLOW
    centrality_score: float = 0.0
    connection_count: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeGraphAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    entity_type: EntityType = EntityType.ASSET
    analysis_score: float = 0.0
    hidden_relations: int = 0
    subgraph_size: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeGraphReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_centrality: float = 0.0
    avg_connections: float = 0.0
    by_entity_type: dict[str, int] = Field(default_factory=dict)
    by_relation_type: dict[str, int] = Field(default_factory=dict)
    by_graph_depth: dict[str, int] = Field(default_factory=dict)
    high_centrality_entities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityKnowledgeGraphEngine:
    """Build threat subgraphs, detect hidden
    relationships, compute entity centrality."""

    def __init__(
        self,
        max_records: int = 200000,
        centrality_threshold: float = 0.7,
    ) -> None:
        self._max_records = max_records
        self._centrality_threshold = centrality_threshold
        self._records: list[KnowledgeGraphRecord] = []
        self._analyses: list[KnowledgeGraphAnalysis] = []
        logger.info(
            "security_knowledge_graph_engine.init",
            max_records=max_records,
            centrality_threshold=centrality_threshold,
        )

    def add_record(
        self,
        entity_id: str,
        entity_type: EntityType = EntityType.ASSET,
        relation_type: RelationType = (RelationType.TARGETS),
        graph_depth: GraphDepth = GraphDepth.SHALLOW,
        centrality_score: float = 0.0,
        connection_count: int = 0,
        service: str = "",
        team: str = "",
    ) -> KnowledgeGraphRecord:
        record = KnowledgeGraphRecord(
            entity_id=entity_id,
            entity_type=entity_type,
            relation_type=relation_type,
            graph_depth=graph_depth,
            centrality_score=centrality_score,
            connection_count=connection_count,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_knowledge_graph.record_added",
            record_id=record.id,
            entity_id=entity_id,
        )
        return record

    def process(self, key: str) -> KnowledgeGraphAnalysis | None:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return None
        score = rec.centrality_score * 100.0
        hidden = max(0, rec.connection_count - 2)
        analysis = KnowledgeGraphAnalysis(
            entity_id=rec.entity_id,
            entity_type=rec.entity_type,
            analysis_score=round(score, 2),
            hidden_relations=hidden,
            subgraph_size=rec.connection_count + 1,
            description=(f"Entity {rec.entity_id} centrality score {score:.1f}"),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return analysis

    def generate_report(self) -> KnowledgeGraphReport:
        by_et: dict[str, int] = {}
        by_rt: dict[str, int] = {}
        by_gd: dict[str, int] = {}
        cents: list[float] = []
        conns: list[int] = []
        for r in self._records:
            e = r.entity_type.value
            by_et[e] = by_et.get(e, 0) + 1
            t = r.relation_type.value
            by_rt[t] = by_rt.get(t, 0) + 1
            d = r.graph_depth.value
            by_gd[d] = by_gd.get(d, 0) + 1
            cents.append(r.centrality_score)
            conns.append(r.connection_count)
        avg_c = round(sum(cents) / len(cents), 4) if cents else 0.0
        avg_cn = round(sum(conns) / len(conns), 2) if conns else 0.0
        high = [
            r.entity_id for r in self._records if r.centrality_score >= self._centrality_threshold
        ][:5]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} entities with high centrality")
        if not recs:
            recs.append("Knowledge graph is balanced")
        return KnowledgeGraphReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_centrality=avg_c,
            avg_connections=avg_cn,
            by_entity_type=by_et,
            by_relation_type=by_rt,
            by_graph_depth=by_gd,
            high_centrality_entities=high,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        et_dist: dict[str, int] = {}
        for r in self._records:
            k = r.entity_type.value
            et_dist[k] = et_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "centrality_threshold": (self._centrality_threshold),
            "entity_type_distribution": et_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_knowledge_graph_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def build_threat_subgraph(
        self,
    ) -> list[dict[str, Any]]:
        """Build subgraphs grouped by entity type."""
        type_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            k = r.entity_type.value
            type_data.setdefault(k, []).append(
                {
                    "entity_id": r.entity_id,
                    "relation": r.relation_type.value,
                    "centrality": r.centrality_score,
                    "connections": r.connection_count,
                }
            )
        results: list[dict[str, Any]] = []
        for etype, nodes in type_data.items():
            results.append(
                {
                    "entity_type": etype,
                    "node_count": len(nodes),
                    "nodes": nodes[:10],
                }
            )
        return results

    def detect_hidden_relationships(
        self,
    ) -> list[dict[str, Any]]:
        """Find entities with high connections but
        low centrality (hidden influencers)."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.connection_count > 2 and r.centrality_score < self._centrality_threshold:
                gap = round(
                    r.connection_count * (1.0 - r.centrality_score),
                    4,
                )
                results.append(
                    {
                        "entity_id": r.entity_id,
                        "entity_type": r.entity_type.value,
                        "connections": r.connection_count,
                        "centrality": r.centrality_score,
                        "hidden_influence_score": gap,
                    }
                )
        results.sort(
            key=lambda x: x["hidden_influence_score"],
            reverse=True,
        )
        return results

    def compute_entity_centrality(
        self,
    ) -> dict[str, Any]:
        """Compute centrality statistics per type."""
        if not self._records:
            return {
                "avg_centrality": 0.0,
                "max_centrality": 0.0,
                "by_type": {},
            }
        type_cents: dict[str, list[float]] = {}
        for r in self._records:
            k = r.entity_type.value
            type_cents.setdefault(k, []).append(r.centrality_score)
        by_type: dict[str, float] = {}
        for t, vals in type_cents.items():
            by_type[t] = round(sum(vals) / len(vals), 4)
        all_c = [r.centrality_score for r in self._records]
        return {
            "avg_centrality": round(sum(all_c) / len(all_c), 4),
            "max_centrality": round(max(all_c), 4),
            "by_type": by_type,
        }
