"""EdgeTelemetryProcessor — edge telemetry processing engine."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EdgeNodeType(StrEnum):
    GATEWAY = "gateway"
    SENSOR = "sensor"
    PROXY = "proxy"
    COLLECTOR = "collector"


class TelemetryProtocol(StrEnum):
    OTLP = "otlp"
    PROMETHEUS = "prometheus"
    STATSD = "statsd"
    SYSLOG = "syslog"


class ProcessingMode(StrEnum):
    STREAMING = "streaming"
    BATCH = "batch"
    HYBRID = "hybrid"


# --- Models ---


class EdgeTelemetryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    edge_node_type: EdgeNodeType = EdgeNodeType.GATEWAY
    protocol: TelemetryProtocol = TelemetryProtocol.OTLP
    processing_mode: ProcessingMode = ProcessingMode.STREAMING
    score: float = 0.0
    latency_ms: float = 0.0
    throughput_eps: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EdgeTelemetryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    edge_node_type: EdgeNodeType = EdgeNodeType.GATEWAY
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EdgeTelemetryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    avg_latency_ms: float = 0.0
    by_node_type: dict[str, int] = Field(default_factory=dict)
    by_protocol: dict[str, int] = Field(default_factory=dict)
    by_processing_mode: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EdgeTelemetryProcessor:
    """Edge Telemetry Processor.

    Processes and optimizes telemetry data from
    edge nodes including gateways, sensors,
    proxies, and collectors.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[EdgeTelemetryRecord] = []
        self._analyses: list[EdgeTelemetryAnalysis] = []
        logger.info(
            "edge_telemetry_processor.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        edge_node_type: EdgeNodeType = (EdgeNodeType.GATEWAY),
        protocol: TelemetryProtocol = (TelemetryProtocol.OTLP),
        processing_mode: ProcessingMode = (ProcessingMode.STREAMING),
        score: float = 0.0,
        latency_ms: float = 0.0,
        throughput_eps: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EdgeTelemetryRecord:
        record = EdgeTelemetryRecord(
            name=name,
            edge_node_type=edge_node_type,
            protocol=protocol,
            processing_mode=processing_mode,
            score=score,
            latency_ms=latency_ms,
            throughput_eps=throughput_eps,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "edge_telemetry_processor.record_added",
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
        lats = [r.latency_ms for r in matching]
        avg_lat = round(sum(lats) / len(lats), 2)
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "avg_latency_ms": avg_lat,
        }

    def generate_report(self) -> EdgeTelemetryReport:
        by_nt: dict[str, int] = {}
        by_pr: dict[str, int] = {}
        by_pm: dict[str, int] = {}
        for r in self._records:
            v1 = r.edge_node_type.value
            by_nt[v1] = by_nt.get(v1, 0) + 1
            v2 = r.protocol.value
            by_pr[v2] = by_pr.get(v2, 0) + 1
            v3 = r.processing_mode.value
            by_pm[v3] = by_pm.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        lats = [r.latency_ms for r in self._records]
        avg_l = round(sum(lats) / len(lats), 2) if lats else 0.0
        recs: list[str] = []
        high_lat = sum(1 for r in self._records if r.latency_ms > 100.0)
        if high_lat > 0:
            recs.append(f"{high_lat} edge node(s) with high latency (>100ms)")
        if avg_s < self._threshold and self._records:
            recs.append(f"Avg score {avg_s} below threshold {self._threshold}")
        if not recs:
            recs.append("Edge telemetry processing healthy")
        return EdgeTelemetryReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            avg_latency_ms=avg_l,
            by_node_type=by_nt,
            by_protocol=by_pr,
            by_processing_mode=by_pm,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        nt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.edge_node_type.value
            nt_dist[k] = nt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "node_type_distribution": nt_dist,
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("edge_telemetry_processor.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def classify_edge_sources(
        self,
    ) -> dict[str, Any]:
        """Classify edge sources by type and protocol."""
        groups: dict[str, list[float]] = {}
        for r in self._records:
            key = f"{r.edge_node_type.value}:{r.protocol.value}"
            groups.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in groups.items():
            avg = round(sum(scores) / len(scores), 2)
            result[k] = {
                "count": len(scores),
                "avg_score": avg,
                "healthy": avg >= self._threshold,
            }
        return result

    def compute_latency_overhead(
        self,
    ) -> dict[str, Any]:
        """Compute latency overhead per edge node."""
        if not self._records:
            return {"status": "no_data"}
        node_lats: dict[str, list[float]] = {}
        for r in self._records:
            key = r.edge_node_type.value
            node_lats.setdefault(key, []).append(r.latency_ms)
        overhead: dict[str, Any] = {}
        for k, lats in node_lats.items():
            avg = round(sum(lats) / len(lats), 2)
            mx = round(max(lats), 2)
            overhead[k] = {
                "avg_latency_ms": avg,
                "max_latency_ms": mx,
                "sample_count": len(lats),
            }
        total_avg = round(
            sum(r.latency_ms for r in self._records) / len(self._records),
            2,
        )
        return {
            "total_avg_latency_ms": total_avg,
            "by_node_type": overhead,
        }

    def optimize_edge_routing(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend routing optimizations."""
        svc_data: dict[str, list[EdgeTelemetryRecord]] = {}
        for r in self._records:
            svc_data.setdefault(r.service, []).append(r)
        recommendations: list[dict[str, Any]] = []
        for svc, recs in svc_data.items():
            lats = [r.latency_ms for r in recs]
            avg_lat = round(sum(lats) / len(lats), 2)
            modes = {r.processing_mode.value for r in recs}
            rec: dict[str, Any] = {
                "service": svc,
                "avg_latency_ms": avg_lat,
                "current_modes": sorted(modes),
            }
            if avg_lat > 100.0:
                rec["suggestion"] = "Switch to streaming mode"
            elif avg_lat > 50.0:
                rec["suggestion"] = "Consider hybrid processing"
            else:
                rec["suggestion"] = "Routing optimal"
            recommendations.append(rec)
        recommendations.sort(
            key=lambda x: x["avg_latency_ms"],
            reverse=True,
        )
        return recommendations
