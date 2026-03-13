"""OtelServiceGraphEngine — OTel service graph engine."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GraphSource(StrEnum):
    TRACE_SPANS = "trace_spans"
    METRICS = "metrics"
    LOGS = "logs"
    MANUAL = "manual"


class EdgeType(StrEnum):
    HTTP = "http"
    GRPC = "grpc"
    KAFKA = "kafka"
    DATABASE = "database"


class GraphFreshness(StrEnum):
    REALTIME = "realtime"
    RECENT = "recent"
    STALE = "stale"
    UNKNOWN = "unknown"


# --- Models ---


class OtelServiceGraphEngineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    graph_source: GraphSource = GraphSource.TRACE_SPANS
    edge_type: EdgeType = EdgeType.HTTP
    graph_freshness: GraphFreshness = GraphFreshness.REALTIME
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class OtelServiceGraphEngineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    graph_source: GraphSource = GraphSource.TRACE_SPANS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OtelServiceGraphEngineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_graph_source: dict[str, int] = Field(default_factory=dict)
    by_edge_type: dict[str, int] = Field(default_factory=dict)
    by_graph_freshness: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class OtelServiceGraphEngine:
    """OTel service graph engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[OtelServiceGraphEngineRecord] = []
        self._analyses: list[OtelServiceGraphEngineAnalysis] = []
        logger.info(
            "otel.service.graph.engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def record_item(
        self,
        name: str,
        graph_source: GraphSource = (GraphSource.TRACE_SPANS),
        edge_type: EdgeType = EdgeType.HTTP,
        graph_freshness: GraphFreshness = (GraphFreshness.REALTIME),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> OtelServiceGraphEngineRecord:
        record = OtelServiceGraphEngineRecord(
            name=name,
            graph_source=graph_source,
            edge_type=edge_type,
            graph_freshness=graph_freshness,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "otel.service.graph.engine.item_recorded",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = OtelServiceGraphEngineAnalysis(
                    name=r.name,
                    graph_source=r.graph_source,
                    analysis_score=r.score,
                    threshold=self._threshold,
                    breached=(r.score < self._threshold),
                    description=(f"Processed {r.name}"),
                )
                self._analyses.append(analysis)
                return {
                    "status": "processed",
                    "analysis_id": analysis.id,
                    "breached": analysis.breached,
                }
        return {"status": "not_found", "key": key}

    # -- domain methods ---

    def build_service_graph(self) -> dict[str, Any]:
        """Build service graph from records."""
        source_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.graph_source.value
            source_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in source_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def detect_undiscovered_edges(
        self,
    ) -> list[dict[str, Any]]:
        """Detect undiscovered service edges."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "graph_source": (r.graph_source.value),
                        "edge_type": r.edge_type.value,
                        "score": r.score,
                        "service": r.service,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def compute_graph_completeness(
        self,
    ) -> list[dict[str, Any]]:
        """Compute graph completeness per service."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_completeness": avg,
                }
            )
        results.sort(key=lambda x: x["avg_completeness"])
        return results

    # -- report / stats ---

    def generate_report(
        self,
    ) -> OtelServiceGraphEngineReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.graph_source.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.edge_type.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.graph_freshness.value
            by_e3[v3] = by_e3.get(v3, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg < self._threshold:
            recs.append(f"Avg score {avg} below threshold ({self._threshold})")
        if not recs:
            recs.append("OTel Service Graph Engine is healthy")
        return OtelServiceGraphEngineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_graph_source=by_e1,
            by_edge_type=by_e2,
            by_graph_freshness=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("otel.service.graph.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.graph_source.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "graph_source_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
