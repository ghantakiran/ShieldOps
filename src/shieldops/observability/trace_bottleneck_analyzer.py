"""Trace Bottleneck Analyzer

Critical path analysis, bottleneck identification, latency attribution,
and optimization recommendations for distributed tracing.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SpanKind(StrEnum):
    CLIENT = "client"
    SERVER = "server"
    PRODUCER = "producer"
    CONSUMER = "consumer"
    INTERNAL = "internal"


class BottleneckType(StrEnum):
    SLOW_QUERY = "slow_query"
    NETWORK_LATENCY = "network_latency"
    SERIALIZATION = "serialization"
    LOCK_CONTENTION = "lock_contention"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    EXTERNAL_DEPENDENCY = "external_dependency"
    CPU_BOUND = "cpu_bound"
    IO_WAIT = "io_wait"


class OptimizationPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class TraceSpanRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str = ""
    operation_name: str = ""
    span_kind: SpanKind = SpanKind.SERVER
    service: str = ""
    duration_ms: float = 0.0
    self_time_ms: float = 0.0
    child_count: int = 0
    is_critical_path: bool = False
    is_bottleneck: bool = False
    bottleneck_type: BottleneckType | None = None
    error: bool = False
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BottleneckAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    bottleneck_span: str = ""
    bottleneck_type: BottleneckType = BottleneckType.SLOW_QUERY
    priority: OptimizationPriority = OptimizationPriority.MEDIUM
    latency_contribution_pct: float = 0.0
    estimated_savings_ms: float = 0.0
    recommendation: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceBottleneckReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_traces: int = 0
    avg_trace_duration_ms: float = 0.0
    bottleneck_count: int = 0
    avg_self_time_ratio: float = 0.0
    by_span_kind: dict[str, int] = Field(default_factory=dict)
    by_bottleneck_type: dict[str, int] = Field(default_factory=dict)
    by_optimization_priority: dict[str, int] = Field(default_factory=dict)
    top_bottleneck_operations: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TraceBottleneckAnalyzer:
    """Trace Bottleneck Analyzer

    Critical path analysis, bottleneck identification, latency attribution,
    and optimization recommendations.
    """

    def __init__(
        self,
        max_records: int = 200000,
        bottleneck_self_time_pct: float = 40.0,
        slow_span_threshold_ms: float = 500.0,
    ) -> None:
        self._max_records = max_records
        self._bottleneck_pct = bottleneck_self_time_pct
        self._slow_threshold_ms = slow_span_threshold_ms
        self._records: list[TraceSpanRecord] = []
        self._analyses: list[BottleneckAnalysis] = []
        logger.info(
            "trace_bottleneck_analyzer.initialized",
            max_records=max_records,
            bottleneck_self_time_pct=bottleneck_self_time_pct,
            slow_span_threshold_ms=slow_span_threshold_ms,
        )

    def add_record(
        self,
        trace_id: str,
        span_id: str,
        operation_name: str,
        service: str,
        duration_ms: float,
        self_time_ms: float = 0.0,
        parent_span_id: str = "",
        span_kind: SpanKind = SpanKind.SERVER,
        child_count: int = 0,
        is_critical_path: bool = False,
        bottleneck_type: BottleneckType | None = None,
        error: bool = False,
        team: str = "",
    ) -> TraceSpanRecord:
        actual_self_time = self_time_ms if self_time_ms > 0 else duration_ms
        is_bottleneck = False
        if duration_ms > 0:
            self_ratio = actual_self_time / duration_ms * 100
            if self_ratio > self._bottleneck_pct and duration_ms > self._slow_threshold_ms:
                is_bottleneck = True
        if duration_ms > self._slow_threshold_ms and not parent_span_id:
            is_critical_path = True
        record = TraceSpanRecord(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            span_kind=span_kind,
            service=service,
            duration_ms=duration_ms,
            self_time_ms=actual_self_time,
            child_count=child_count,
            is_critical_path=is_critical_path,
            is_bottleneck=is_bottleneck,
            bottleneck_type=bottleneck_type,
            error=error,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "trace_bottleneck_analyzer.record_added",
            record_id=record.id,
            trace_id=trace_id,
            operation_name=operation_name,
            is_bottleneck=is_bottleneck,
        )
        return record

    def get_record(self, record_id: str) -> TraceSpanRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        span_kind: SpanKind | None = None,
        service: str | None = None,
        bottlenecks_only: bool = False,
        limit: int = 50,
    ) -> list[TraceSpanRecord]:
        results = list(self._records)
        if span_kind is not None:
            results = [r for r in results if r.span_kind == span_kind]
        if service is not None:
            results = [r for r in results if r.service == service]
        if bottlenecks_only:
            results = [r for r in results if r.is_bottleneck]
        return results[-limit:]

    def analyze_critical_path(self, trace_id: str) -> dict[str, Any]:
        spans = [r for r in self._records if r.trace_id == trace_id]
        if not spans:
            return {"trace_id": trace_id, "status": "no_data"}
        root_spans = [s for s in spans if not s.parent_span_id]
        total_duration = max(s.duration_ms for s in spans) if spans else 0.0
        critical_spans = sorted(spans, key=lambda s: s.self_time_ms, reverse=True)
        path: list[dict[str, Any]] = []
        for s in critical_spans[:10]:
            contribution = round(s.self_time_ms / max(1.0, total_duration) * 100, 2)
            path.append(
                {
                    "span_id": s.span_id,
                    "operation": s.operation_name,
                    "service": s.service,
                    "self_time_ms": s.self_time_ms,
                    "duration_ms": s.duration_ms,
                    "contribution_pct": contribution,
                    "is_bottleneck": s.is_bottleneck,
                }
            )
        return {
            "trace_id": trace_id,
            "total_duration_ms": total_duration,
            "span_count": len(spans),
            "root_spans": len(root_spans),
            "bottleneck_count": sum(1 for s in spans if s.is_bottleneck),
            "critical_path": path,
        }

    def compute_latency_attribution(self, service: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {"service": service, "status": "no_data"}
        op_stats: dict[str, dict[str, float]] = {}
        for r in matching:
            if r.operation_name not in op_stats:
                op_stats[r.operation_name] = {
                    "total_self_time": 0.0,
                    "total_duration": 0.0,
                    "count": 0,
                }
            op_stats[r.operation_name]["total_self_time"] += r.self_time_ms
            op_stats[r.operation_name]["total_duration"] += r.duration_ms
            op_stats[r.operation_name]["count"] += 1
        total_self = sum(v["total_self_time"] for v in op_stats.values())
        attribution: list[dict[str, Any]] = []
        for op, stats in op_stats.items():
            pct = round(stats["total_self_time"] / max(1.0, total_self) * 100, 2)
            avg_dur = round(stats["total_duration"] / stats["count"], 2)
            attribution.append(
                {
                    "operation": op,
                    "contribution_pct": pct,
                    "avg_duration_ms": avg_dur,
                    "invocation_count": int(stats["count"]),
                }
            )
        return {
            "service": service,
            "total_self_time_ms": round(total_self, 2),
            "attribution": sorted(attribution, key=lambda x: x["contribution_pct"], reverse=True),
        }

    def identify_optimization_targets(self) -> list[BottleneckAnalysis]:
        bottlenecks = [r for r in self._records if r.is_bottleneck]
        op_bottlenecks: dict[str, list[TraceSpanRecord]] = {}
        for b in bottlenecks:
            op_bottlenecks.setdefault(b.operation_name, []).append(b)
        targets: list[BottleneckAnalysis] = []
        for op, spans in sorted(
            op_bottlenecks.items(),
            key=lambda x: sum(s.self_time_ms for s in x[1]),
            reverse=True,
        )[:10]:
            avg_self = sum(s.self_time_ms for s in spans) / len(spans)
            avg_dur = sum(s.duration_ms for s in spans) / len(spans)
            contribution = round(avg_self / max(1.0, avg_dur) * 100, 2)
            if contribution > 80:
                priority = OptimizationPriority.CRITICAL
            elif contribution > 60:
                priority = OptimizationPriority.HIGH
            elif contribution > 40:
                priority = OptimizationPriority.MEDIUM
            else:
                priority = OptimizationPriority.LOW
            bt = spans[0].bottleneck_type or BottleneckType.SLOW_QUERY
            savings = round(avg_self * 0.5, 2)
            analysis = BottleneckAnalysis(
                trace_id=spans[0].trace_id,
                bottleneck_span=op,
                bottleneck_type=bt,
                priority=priority,
                latency_contribution_pct=contribution,
                estimated_savings_ms=savings,
                recommendation=f"Optimize '{op}' — {contribution}% of trace time, "
                f"est. {savings}ms savings",
            )
            targets.append(analysis)
        self._analyses.extend(targets)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return targets

    def process(self, service: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {"service": service, "status": "no_data"}
        durations = [r.duration_ms for r in matching]
        self_times = [r.self_time_ms for r in matching]
        bottleneck_count = sum(1 for r in matching if r.is_bottleneck)
        total_dur = sum(durations)
        total_self = sum(self_times)
        return {
            "service": service,
            "span_count": len(matching),
            "avg_duration_ms": round(total_dur / len(matching), 2),
            "avg_self_time_ms": round(total_self / len(matching), 2),
            "self_time_ratio": round(total_self / max(1.0, total_dur), 4),
            "bottleneck_count": bottleneck_count,
            "bottleneck_rate": round(bottleneck_count / len(matching), 4),
            "error_rate": round(sum(1 for r in matching if r.error) / len(matching), 4),
        }

    def generate_report(self) -> TraceBottleneckReport:
        by_kind: dict[str, int] = {}
        by_bt: dict[str, int] = {}
        for r in self._records:
            by_kind[r.span_kind.value] = by_kind.get(r.span_kind.value, 0) + 1
            if r.bottleneck_type:
                by_bt[r.bottleneck_type.value] = by_bt.get(r.bottleneck_type.value, 0) + 1
        by_pri: dict[str, int] = {}
        for a in self._analyses:
            by_pri[a.priority.value] = by_pri.get(a.priority.value, 0) + 1
        traces = {r.trace_id for r in self._records}
        durations = [r.duration_ms for r in self._records]
        self_times = [r.self_time_ms for r in self._records]
        total_dur = sum(durations)
        total_self = sum(self_times)
        bottleneck_count = sum(1 for r in self._records if r.is_bottleneck)
        op_bottleneck: dict[str, int] = {}
        for r in self._records:
            if r.is_bottleneck:
                op_bottleneck[r.operation_name] = op_bottleneck.get(r.operation_name, 0) + 1
        top_ops = sorted(op_bottleneck.items(), key=lambda x: x[1], reverse=True)[:5]
        recs: list[str] = []
        if bottleneck_count > 0:
            recs.append(
                f"{bottleneck_count} bottleneck span(s) identified across {len(traces)} trace(s)"
            )
        if top_ops:
            recs.append(f"Top bottleneck: '{top_ops[0][0]}' ({top_ops[0][1]} occurrences)")
        if total_dur > 0 and total_self / total_dur > 0.6:
            recs.append("High self-time ratio — services spending too much time in own code")
        if not recs:
            recs.append("Trace performance is healthy — no significant bottlenecks")
        return TraceBottleneckReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_traces=len(traces),
            avg_trace_duration_ms=round(total_dur / max(1, len(durations)), 2),
            bottleneck_count=bottleneck_count,
            avg_self_time_ratio=round(total_self / max(1.0, total_dur), 4),
            by_span_kind=by_kind,
            by_bottleneck_type=by_bt,
            by_optimization_priority=by_pri,
            top_bottleneck_operations=[{"operation": op, "count": cnt} for op, cnt in top_ops],
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        kind_dist: dict[str, int] = {}
        for r in self._records:
            kind_dist[r.span_kind.value] = kind_dist.get(r.span_kind.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "bottleneck_self_time_pct": self._bottleneck_pct,
            "slow_span_threshold_ms": self._slow_threshold_ms,
            "span_kind_distribution": kind_dist,
            "unique_traces": len({r.trace_id for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("trace_bottleneck_analyzer.cleared")
        return {"status": "cleared"}
