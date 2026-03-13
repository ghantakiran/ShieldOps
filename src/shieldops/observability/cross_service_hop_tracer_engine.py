"""Cross-Service Hop Tracer Engine —
trace investigation hops across service boundaries,
identify hop blockers, compute cross-service latency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HopType(StrEnum):
    DEPENDENCY = "dependency"
    SHARED_RESOURCE = "shared_resource"
    CASCADE = "cascade"
    CONFIGURATION = "configuration"


class ServiceBoundary(StrEnum):
    SAME_SERVICE = "same_service"
    SAME_TEAM = "same_team"
    CROSS_TEAM = "cross_team"
    CROSS_ORG = "cross_org"


class TracingCompleteness(StrEnum):
    FULL_TRACE = "full_trace"
    PARTIAL_TRACE = "partial_trace"
    BLOCKED_TRACE = "blocked_trace"
    ESTIMATED_TRACE = "estimated_trace"


# --- Models ---


class CrossServiceHopRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    hop_type: HopType = HopType.DEPENDENCY
    service_boundary: ServiceBoundary = ServiceBoundary.SAME_SERVICE
    tracing_completeness: TracingCompleteness = TracingCompleteness.FULL_TRACE
    latency_ms: float = 0.0
    hop_index: int = 0
    source_service: str = ""
    target_service: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CrossServiceHopAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    hop_type: HopType = HopType.DEPENDENCY
    service_boundary: ServiceBoundary = ServiceBoundary.SAME_SERVICE
    tracing_completeness: TracingCompleteness = TracingCompleteness.FULL_TRACE
    is_blocked: bool = False
    latency_ms: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CrossServiceHopReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_latency_ms: float = 0.0
    by_hop_type: dict[str, int] = Field(default_factory=dict)
    by_service_boundary: dict[str, int] = Field(default_factory=dict)
    by_tracing_completeness: dict[str, int] = Field(default_factory=dict)
    blocked_traces: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CrossServiceHopTracerEngine:
    """Trace investigation hops across service boundaries,
    identify hop blockers, compute cross-service latency."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CrossServiceHopRecord] = []
        self._analyses: dict[str, CrossServiceHopAnalysis] = {}
        logger.info("cross_service_hop_tracer_engine.init", max_records=max_records)

    def add_record(
        self,
        trace_id: str = "",
        hop_type: HopType = HopType.DEPENDENCY,
        service_boundary: ServiceBoundary = ServiceBoundary.SAME_SERVICE,
        tracing_completeness: TracingCompleteness = TracingCompleteness.FULL_TRACE,
        latency_ms: float = 0.0,
        hop_index: int = 0,
        source_service: str = "",
        target_service: str = "",
        description: str = "",
    ) -> CrossServiceHopRecord:
        record = CrossServiceHopRecord(
            trace_id=trace_id,
            hop_type=hop_type,
            service_boundary=service_boundary,
            tracing_completeness=tracing_completeness,
            latency_ms=latency_ms,
            hop_index=hop_index,
            source_service=source_service,
            target_service=target_service,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cross_service_hop_tracer.record_added",
            record_id=record.id,
            trace_id=trace_id,
        )
        return record

    def process(self, key: str) -> CrossServiceHopAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_blocked = rec.tracing_completeness == TracingCompleteness.BLOCKED_TRACE
        analysis = CrossServiceHopAnalysis(
            trace_id=rec.trace_id,
            hop_type=rec.hop_type,
            service_boundary=rec.service_boundary,
            tracing_completeness=rec.tracing_completeness,
            is_blocked=is_blocked,
            latency_ms=round(rec.latency_ms, 4),
            description=(
                f"Trace {rec.trace_id} hop={rec.hop_index} boundary={rec.service_boundary.value}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CrossServiceHopReport:
        by_ht: dict[str, int] = {}
        by_sb: dict[str, int] = {}
        by_tc: dict[str, int] = {}
        latencies: list[float] = []
        for r in self._records:
            k = r.hop_type.value
            by_ht[k] = by_ht.get(k, 0) + 1
            k2 = r.service_boundary.value
            by_sb[k2] = by_sb.get(k2, 0) + 1
            k3 = r.tracing_completeness.value
            by_tc[k3] = by_tc.get(k3, 0) + 1
            latencies.append(r.latency_ms)
        avg_lat = round(sum(latencies) / len(latencies), 4) if latencies else 0.0
        blocked: list[str] = list(
            {
                r.trace_id
                for r in self._records
                if r.tracing_completeness == TracingCompleteness.BLOCKED_TRACE
            }
        )[:10]
        recs: list[str] = []
        if blocked:
            recs.append(f"{len(blocked)} traces blocked at service boundaries")
        cross_org = by_sb.get("cross_org", 0)
        if cross_org:
            recs.append(f"{cross_org} cross-org hops require coordination")
        if not recs:
            recs.append("Cross-service hop tracing is complete")
        return CrossServiceHopReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_latency_ms=avg_lat,
            by_hop_type=by_ht,
            by_service_boundary=by_sb,
            by_tracing_completeness=by_tc,
            blocked_traces=blocked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.hop_type.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "hop_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("cross_service_hop_tracer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def trace_cross_service_hops(self) -> list[dict[str, Any]]:
        """Trace all cross-service hops grouped by trace_id."""
        trace_map: dict[str, list[CrossServiceHopRecord]] = {}
        for r in self._records:
            trace_map.setdefault(r.trace_id, []).append(r)
        results: list[dict[str, Any]] = []
        for tid, trace_recs in trace_map.items():
            sorted_recs = sorted(trace_recs, key=lambda r: r.hop_index)
            path = [f"{r.source_service}->{r.target_service}" for r in sorted_recs]
            total_lat = sum(r.latency_ms for r in sorted_recs)
            boundaries = list({r.service_boundary.value for r in sorted_recs})
            results.append(
                {
                    "trace_id": tid,
                    "hop_count": len(sorted_recs),
                    "total_latency_ms": round(total_lat, 4),
                    "path": path,
                    "boundaries": boundaries,
                }
            )
        results.sort(key=lambda x: x["total_latency_ms"], reverse=True)
        return results

    def identify_hop_blockers(self) -> list[dict[str, Any]]:
        """Identify hops that block trace completion."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.tracing_completeness == TracingCompleteness.BLOCKED_TRACE:
                key = f"{r.trace_id}:{r.hop_index}"
                if key not in seen:
                    seen.add(key)
                    results.append(
                        {
                            "trace_id": r.trace_id,
                            "hop_index": r.hop_index,
                            "source_service": r.source_service,
                            "target_service": r.target_service,
                            "boundary": r.service_boundary.value,
                            "hop_type": r.hop_type.value,
                        }
                    )
        results.sort(key=lambda x: x["hop_index"])
        return results

    def compute_cross_service_latency(self) -> list[dict[str, Any]]:
        """Compute average latency per service boundary crossing."""
        boundary_data: dict[str, list[float]] = {}
        for r in self._records:
            bv = r.service_boundary.value
            boundary_data.setdefault(bv, []).append(r.latency_ms)
        results: list[dict[str, Any]] = []
        for bv, lats in boundary_data.items():
            avg_lat = sum(lats) / len(lats)
            results.append(
                {
                    "service_boundary": bv,
                    "avg_latency_ms": round(avg_lat, 4),
                    "max_latency_ms": round(max(lats), 4),
                    "hop_count": len(lats),
                }
            )
        results.sort(key=lambda x: x["avg_latency_ms"], reverse=True)
        return results
