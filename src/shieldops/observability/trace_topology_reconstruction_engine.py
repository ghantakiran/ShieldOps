"""Trace Topology Reconstruction Engine —
reconstruct service topology from traces,
detect topology changes, validate topology accuracy."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TopologyType(StrEnum):
    STATIC = "static"
    DYNAMIC = "dynamic"
    HYBRID = "hybrid"
    INFERRED = "inferred"


class ReconstructionAccuracy(StrEnum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    PARTIAL = "partial"
    OUTDATED = "outdated"


class ChangeType(StrEnum):
    NEW_EDGE = "new_edge"
    REMOVED_EDGE = "removed_edge"
    WEIGHT_CHANGE = "weight_change"
    NODE_CHANGE = "node_change"


# --- Models ---


class TraceTopologyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    source_service: str = ""
    target_service: str = ""
    topology_type: TopologyType = TopologyType.DYNAMIC
    reconstruction_accuracy: ReconstructionAccuracy = ReconstructionAccuracy.APPROXIMATE
    change_type: ChangeType = ChangeType.WEIGHT_CHANGE
    edge_weight: float = 0.0
    call_count: int = 0
    error_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceTopologyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service: str = ""
    target_service: str = ""
    topology_type: TopologyType = TopologyType.DYNAMIC
    accuracy_score: float = 0.0
    change_detected: bool = False
    change_type: ChangeType = ChangeType.WEIGHT_CHANGE
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceTopologyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_edges: int = 0
    by_topology_type: dict[str, int] = Field(default_factory=dict)
    by_reconstruction_accuracy: dict[str, int] = Field(default_factory=dict)
    by_change_type: dict[str, int] = Field(default_factory=dict)
    changed_edges: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TraceTopologyReconstructionEngine:
    """Reconstruct service topology from traces,
    detect topology changes, validate topology accuracy."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TraceTopologyRecord] = []
        self._analyses: dict[str, TraceTopologyAnalysis] = {}
        logger.info("trace_topology_reconstruction_engine.init", max_records=max_records)

    def add_record(
        self,
        trace_id: str = "",
        source_service: str = "",
        target_service: str = "",
        topology_type: TopologyType = TopologyType.DYNAMIC,
        reconstruction_accuracy: ReconstructionAccuracy = ReconstructionAccuracy.APPROXIMATE,
        change_type: ChangeType = ChangeType.WEIGHT_CHANGE,
        edge_weight: float = 0.0,
        call_count: int = 0,
        error_count: int = 0,
        description: str = "",
    ) -> TraceTopologyRecord:
        record = TraceTopologyRecord(
            trace_id=trace_id,
            source_service=source_service,
            target_service=target_service,
            topology_type=topology_type,
            reconstruction_accuracy=reconstruction_accuracy,
            change_type=change_type,
            edge_weight=edge_weight,
            call_count=call_count,
            error_count=error_count,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "trace_topology.record_added",
            record_id=record.id,
            source_service=source_service,
        )
        return record

    def process(self, key: str) -> TraceTopologyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        acc_weights = {"exact": 1.0, "approximate": 0.75, "partial": 0.5, "outdated": 0.25}
        acc_score = round(acc_weights.get(rec.reconstruction_accuracy.value, 0.5) * 100, 2)
        changed = rec.change_type in (ChangeType.NEW_EDGE, ChangeType.REMOVED_EDGE)
        analysis = TraceTopologyAnalysis(
            source_service=rec.source_service,
            target_service=rec.target_service,
            topology_type=rec.topology_type,
            accuracy_score=acc_score,
            change_detected=changed,
            change_type=rec.change_type,
            description=(f"Edge {rec.source_service}->{rec.target_service} accuracy={acc_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TraceTopologyReport:
        by_topo: dict[str, int] = {}
        by_acc: dict[str, int] = {}
        by_change: dict[str, int] = {}
        edges: set[str] = set()
        for r in self._records:
            t = r.topology_type.value
            by_topo[t] = by_topo.get(t, 0) + 1
            a = r.reconstruction_accuracy.value
            by_acc[a] = by_acc.get(a, 0) + 1
            c = r.change_type.value
            by_change[c] = by_change.get(c, 0) + 1
            edges.add(f"{r.source_service}->{r.target_service}")
        changed_edges = list(
            {
                f"{r.source_service}->{r.target_service}"
                for r in self._records
                if r.change_type in (ChangeType.NEW_EDGE, ChangeType.REMOVED_EDGE)
            }
        )[:10]
        recs: list[str] = []
        if changed_edges:
            recs.append(f"{len(changed_edges)} topology edges changed")
        if not recs:
            recs.append("Topology stable — no structural changes detected")
        return TraceTopologyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_edges=len(edges),
            by_topology_type=by_topo,
            by_reconstruction_accuracy=by_acc,
            by_change_type=by_change,
            changed_edges=changed_edges,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        topo_dist: dict[str, int] = {}
        for r in self._records:
            k = r.topology_type.value
            topo_dist[k] = topo_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "topology_type_distribution": topo_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("trace_topology_reconstruction_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def reconstruct_service_topology(self) -> list[dict[str, Any]]:
        """Reconstruct service dependency graph from trace records."""
        edge_map: dict[str, dict[str, Any]] = {}
        for r in self._records:
            ekey = f"{r.source_service}->{r.target_service}"
            if ekey not in edge_map:
                edge_map[ekey] = {
                    "source": r.source_service,
                    "target": r.target_service,
                    "call_count": 0,
                    "error_count": 0,
                    "total_weight": 0.0,
                }
            edge_map[ekey]["call_count"] += r.call_count
            edge_map[ekey]["error_count"] += r.error_count
            edge_map[ekey]["total_weight"] += r.edge_weight
        results: list[dict[str, Any]] = []
        for edata in edge_map.values():
            calls = edata["call_count"]
            err_rate = round(edata["error_count"] / calls * 100, 2) if calls > 0 else 0.0
            results.append(
                {
                    "source_service": edata["source"],
                    "target_service": edata["target"],
                    "total_calls": calls,
                    "error_rate_pct": err_rate,
                    "avg_weight": round(edata["total_weight"] / max(calls, 1), 2),
                }
            )
        results.sort(key=lambda x: x["total_calls"], reverse=True)
        return results

    def detect_topology_changes(self) -> list[dict[str, Any]]:
        """Detect structural changes in the service topology."""
        change_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            if r.change_type in (
                ChangeType.NEW_EDGE,
                ChangeType.REMOVED_EDGE,
                ChangeType.NODE_CHANGE,
            ):
                ekey = f"{r.source_service}->{r.target_service}"
                change_data.setdefault(ekey, []).append(
                    {
                        "change_type": r.change_type.value,
                        "trace_id": r.trace_id,
                        "created_at": r.created_at,
                    }
                )
        results: list[dict[str, Any]] = []
        for ekey, changes in change_data.items():
            latest = max(changes, key=lambda x: x["created_at"])
            results.append(
                {
                    "edge": ekey,
                    "change_count": len(changes),
                    "latest_change_type": latest["change_type"],
                    "latest_trace_id": latest["trace_id"],
                }
            )
        results.sort(key=lambda x: x["change_count"], reverse=True)
        return results

    def validate_topology_accuracy(self) -> list[dict[str, Any]]:
        """Validate topology reconstruction accuracy per service pair."""
        acc_weights = {"exact": 1.0, "approximate": 0.75, "partial": 0.5, "outdated": 0.25}
        edge_acc: dict[str, list[float]] = {}
        for r in self._records:
            ekey = f"{r.source_service}->{r.target_service}"
            w = acc_weights.get(r.reconstruction_accuracy.value, 0.5)
            edge_acc.setdefault(ekey, []).append(w)
        results: list[dict[str, Any]] = []
        for ekey, acc_vals in edge_acc.items():
            avg_acc = round(sum(acc_vals) / len(acc_vals) * 100, 2)
            results.append(
                {
                    "edge": ekey,
                    "avg_accuracy_pct": avg_acc,
                    "sample_count": len(acc_vals),
                    "accuracy_ok": avg_acc >= 75.0,
                }
            )
        results.sort(key=lambda x: x["avg_accuracy_pct"])
        return results
