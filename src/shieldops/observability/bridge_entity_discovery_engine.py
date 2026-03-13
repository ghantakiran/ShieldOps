"""Bridge Entity Discovery Engine —
find linking entities across disparate alerts/signals,
score bridge significance, reconstruct entity graph."""

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
    SERVICE = "service"
    HOST = "host"
    DEPLOYMENT = "deployment"
    CONFIGURATION = "configuration"


class BridgeStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    SPECULATIVE = "speculative"


class DiscoveryMethod(StrEnum):
    CORRELATION = "correlation"
    TOPOLOGY = "topology"
    TEMPORAL = "temporal"
    SEMANTIC = "semantic"


# --- Models ---


class BridgeEntityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    entity_type: EntityType = EntityType.SERVICE
    bridge_strength: BridgeStrength = BridgeStrength.WEAK
    discovery_method: DiscoveryMethod = DiscoveryMethod.CORRELATION
    significance_score: float = 0.0
    connected_alerts: int = 0
    source_signal: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BridgeEntityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    entity_type: EntityType = EntityType.SERVICE
    bridge_strength: BridgeStrength = BridgeStrength.WEAK
    is_significant: bool = False
    significance_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BridgeEntityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_significance_score: float = 0.0
    by_entity_type: dict[str, int] = Field(default_factory=dict)
    by_bridge_strength: dict[str, int] = Field(default_factory=dict)
    by_discovery_method: dict[str, int] = Field(default_factory=dict)
    top_bridge_entities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class BridgeEntityDiscoveryEngine:
    """Find linking entities across disparate alerts/signals,
    score bridge significance, reconstruct entity graph."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[BridgeEntityRecord] = []
        self._analyses: dict[str, BridgeEntityAnalysis] = {}
        logger.info("bridge_entity_discovery_engine.init", max_records=max_records)

    def add_record(
        self,
        entity_id: str = "",
        entity_type: EntityType = EntityType.SERVICE,
        bridge_strength: BridgeStrength = BridgeStrength.WEAK,
        discovery_method: DiscoveryMethod = DiscoveryMethod.CORRELATION,
        significance_score: float = 0.0,
        connected_alerts: int = 0,
        source_signal: str = "",
        description: str = "",
    ) -> BridgeEntityRecord:
        record = BridgeEntityRecord(
            entity_id=entity_id,
            entity_type=entity_type,
            bridge_strength=bridge_strength,
            discovery_method=discovery_method,
            significance_score=significance_score,
            connected_alerts=connected_alerts,
            source_signal=source_signal,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "bridge_entity_discovery.record_added",
            record_id=record.id,
            entity_id=entity_id,
        )
        return record

    def process(self, key: str) -> BridgeEntityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_sig = rec.bridge_strength in (BridgeStrength.STRONG, BridgeStrength.MODERATE)
        analysis = BridgeEntityAnalysis(
            entity_id=rec.entity_id,
            entity_type=rec.entity_type,
            bridge_strength=rec.bridge_strength,
            is_significant=is_sig,
            significance_score=round(rec.significance_score, 4),
            description=(
                f"Entity {rec.entity_id} type={rec.entity_type.value} "
                f"strength={rec.bridge_strength.value}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> BridgeEntityReport:
        by_et: dict[str, int] = {}
        by_bs: dict[str, int] = {}
        by_dm: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.entity_type.value
            by_et[k] = by_et.get(k, 0) + 1
            k2 = r.bridge_strength.value
            by_bs[k2] = by_bs.get(k2, 0) + 1
            k3 = r.discovery_method.value
            by_dm[k3] = by_dm.get(k3, 0) + 1
            scores.append(r.significance_score)
        avg_sig = round(sum(scores) / len(scores), 4) if scores else 0.0
        top: list[str] = list(
            {r.entity_id for r in self._records if r.bridge_strength == BridgeStrength.STRONG}
        )[:10]
        recs: list[str] = []
        spec = by_bs.get("speculative", 0)
        if spec:
            recs.append(f"{spec} speculative bridges need verification")
        if not recs:
            recs.append("Bridge entity discovery is operating normally")
        return BridgeEntityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_significance_score=avg_sig,
            by_entity_type=by_et,
            by_bridge_strength=by_bs,
            by_discovery_method=by_dm,
            top_bridge_entities=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.entity_type.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "entity_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("bridge_entity_discovery_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def discover_bridge_entities(self) -> list[dict[str, Any]]:
        """Discover and return bridge entities sorted by significance."""
        entity_map: dict[str, list[BridgeEntityRecord]] = {}
        for r in self._records:
            entity_map.setdefault(r.entity_id, []).append(r)
        results: list[dict[str, Any]] = []
        for eid, ent_recs in entity_map.items():
            avg_sig = sum(r.significance_score for r in ent_recs) / len(ent_recs)
            total_alerts = sum(r.connected_alerts for r in ent_recs)
            methods = list({r.discovery_method.value for r in ent_recs})
            results.append(
                {
                    "entity_id": eid,
                    "avg_significance": round(avg_sig, 4),
                    "total_connected_alerts": total_alerts,
                    "discovery_methods": methods,
                    "record_count": len(ent_recs),
                }
            )
        results.sort(key=lambda x: x["avg_significance"], reverse=True)
        return results

    def score_bridge_significance(self) -> list[dict[str, Any]]:
        """Score each entity's bridge significance with weighted metrics."""
        strength_weights = {
            "strong": 4,
            "moderate": 3,
            "weak": 2,
            "speculative": 1,
        }
        entity_scores: dict[str, float] = {}
        entity_alerts: dict[str, int] = {}
        for r in self._records:
            w = strength_weights.get(r.bridge_strength.value, 1)
            entity_scores[r.entity_id] = (
                entity_scores.get(r.entity_id, 0.0) + r.significance_score * w
            )
            entity_alerts[r.entity_id] = entity_alerts.get(r.entity_id, 0) + r.connected_alerts
        results: list[dict[str, Any]] = []
        for eid, score in entity_scores.items():
            results.append(
                {
                    "entity_id": eid,
                    "weighted_score": round(score, 4),
                    "connected_alerts": entity_alerts[eid],
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["weighted_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results

    def reconstruct_entity_graph(self) -> dict[str, Any]:
        """Reconstruct entity connection graph from bridge records."""
        nodes: set[str] = set()
        edges: list[dict[str, Any]] = []
        seen_edges: set[tuple[str, str]] = set()
        for r in self._records:
            nodes.add(r.entity_id)
            if r.source_signal:
                nodes.add(r.source_signal)
                edge_key = (r.entity_id, r.source_signal)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append(
                        {
                            "from": r.entity_id,
                            "to": r.source_signal,
                            "strength": r.bridge_strength.value,
                            "method": r.discovery_method.value,
                        }
                    )
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": list(nodes),
            "edges": edges,
        }
