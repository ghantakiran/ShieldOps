"""ObservabilityDependencyMapper — signal deps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SignalType(StrEnum):
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"


class DependencyDirection(StrEnum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    BIDIRECTIONAL = "bidirectional"


class HealthImpact(StrEnum):
    BLOCKING = "blocking"
    DEGRADING = "degrading"
    INFORMATIONAL = "informational"


# --- Models ---


class DependencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    signal_type: SignalType = SignalType.METRIC
    direction: DependencyDirection = DependencyDirection.DOWNSTREAM
    health_impact: HealthImpact = HealthImpact.INFORMATIONAL
    score: float = 0.0
    source_service: str = ""
    target_service: str = ""
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    signal_type: SignalType = SignalType.METRIC
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    by_signal_type: dict[str, int] = Field(default_factory=dict)
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_health_impact: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ObservabilityDependencyMapper:
    """Observability Dependency Mapper.

    Maps dependencies between observability
    signals to understand impact chains.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[DependencyRecord] = []
        self._analyses: list[DependencyAnalysis] = []
        logger.info(
            "observability_dependency_mapper.init",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        signal_type: SignalType = SignalType.METRIC,
        direction: DependencyDirection = (DependencyDirection.DOWNSTREAM),
        health_impact: HealthImpact = (HealthImpact.INFORMATIONAL),
        score: float = 0.0,
        source_service: str = "",
        target_service: str = "",
        service: str = "",
        team: str = "",
    ) -> DependencyRecord:
        record = DependencyRecord(
            name=name,
            signal_type=signal_type,
            direction=direction,
            health_impact=health_impact,
            score=score,
            source_service=source_service,
            target_service=target_service,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "observability_dep_mapper.added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.name == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        scores = [r.score for r in matching]
        avg = round(sum(scores) / len(scores), 2)
        blocking = sum(1 for r in matching if r.health_impact == HealthImpact.BLOCKING)
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "blocking_deps": blocking,
        }

    def generate_report(self) -> DependencyReport:
        by_st: dict[str, int] = {}
        by_d: dict[str, int] = {}
        by_hi: dict[str, int] = {}
        for r in self._records:
            v1 = r.signal_type.value
            by_st[v1] = by_st.get(v1, 0) + 1
            v2 = r.direction.value
            by_d[v2] = by_d.get(v2, 0) + 1
            v3 = r.health_impact.value
            by_hi[v3] = by_hi.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        blocking = by_hi.get("blocking", 0)
        if blocking > 0:
            recs.append(f"{blocking} blocking dependency(ies)")
        if avg_s < self._threshold and self._records:
            recs.append(f"Avg score {avg_s} below threshold {self._threshold}")
        if not recs:
            recs.append("Dependency map is healthy")
        return DependencyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            by_signal_type=by_st,
            by_direction=by_d,
            by_health_impact=by_hi,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        st_dist: dict[str, int] = {}
        for r in self._records:
            k = r.signal_type.value
            st_dist[k] = st_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "signal_type_distribution": st_dist,
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("observability_dep_mapper.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def map_signal_dependencies(
        self,
    ) -> dict[str, Any]:
        """Map dependencies between signals."""
        if not self._records:
            return {"status": "no_data"}
        graph: dict[str, list[str]] = {}
        for r in self._records:
            src = r.source_service or r.service
            tgt = r.target_service
            if not tgt:
                continue
            graph.setdefault(src, [])
            if tgt not in graph[src]:
                graph[src].append(tgt)
            if r.direction == DependencyDirection.BIDIRECTIONAL:
                graph.setdefault(tgt, [])
                if src not in graph[tgt]:
                    graph[tgt].append(src)
        total_edges = sum(len(v) for v in graph.values())
        return {
            "nodes": len(graph),
            "edges": total_edges,
            "graph": {k: sorted(v) for k, v in graph.items()},
        }

    def detect_orphaned_signals(
        self,
    ) -> list[dict[str, Any]]:
        """Detect signals with no dependencies."""
        connected: set[str] = set()
        for r in self._records:
            if r.source_service:
                connected.add(r.source_service)
            if r.target_service:
                connected.add(r.target_service)
        all_services = {r.service for r in self._records}
        orphaned = all_services - connected
        results: list[dict[str, Any]] = []
        for svc in sorted(orphaned):
            svc_records = [r for r in self._records if r.service == svc]
            results.append(
                {
                    "service": svc,
                    "record_count": len(svc_records),
                    "signal_types": sorted({r.signal_type.value for r in svc_records}),
                }
            )
        return results

    def compute_dependency_risk(
        self,
    ) -> dict[str, Any]:
        """Compute risk score per dependency."""
        if not self._records:
            return {"status": "no_data"}
        impact_weights = {
            HealthImpact.BLOCKING: 3.0,
            HealthImpact.DEGRADING: 2.0,
            HealthImpact.INFORMATIONAL: 1.0,
        }
        svc_risk: dict[str, dict[str, float]] = {}
        for r in self._records:
            svc = r.service
            if svc not in svc_risk:
                svc_risk[svc] = {
                    "total_weight": 0.0,
                    "count": 0,
                }
            weight = impact_weights.get(r.health_impact, 1.0)
            svc_risk[svc]["total_weight"] += weight
            svc_risk[svc]["count"] += 1
        results: dict[str, Any] = {}
        for svc, data in svc_risk.items():
            risk = round(
                data["total_weight"] / data["count"],
                2,
            )
            results[svc] = {
                "risk_score": risk,
                "dependency_count": int(data["count"]),
                "high_risk": risk >= 2.5,
            }
        return results
