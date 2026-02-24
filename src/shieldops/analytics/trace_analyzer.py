"""Distributed Trace Analyzer — trace segment analysis, bottleneck detection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TraceSegmentType(StrEnum):
    HTTP = "http"
    GRPC = "grpc"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    INTERNAL = "internal"


class BottleneckSeverity(StrEnum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class AnalysisWindow(StrEnum):
    LAST_HOUR = "last_hour"
    LAST_DAY = "last_day"
    LAST_WEEK = "last_week"
    LAST_MONTH = "last_month"


# --- Models ---


class TraceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    service: str = ""
    operation: str = ""
    segment_type: TraceSegmentType = TraceSegmentType.HTTP
    duration_ms: float = 0.0
    parent_span_id: str | None = None
    status_code: int = 200
    error: bool = False
    tags: dict[str, str] = Field(default_factory=dict)
    recorded_at: float = Field(default_factory=time.time)


class BottleneckReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    operation: str = ""
    severity: BottleneckSeverity = BottleneckSeverity.NONE
    avg_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    sample_count: int = 0
    recommendation: str = ""
    detected_at: float = Field(default_factory=time.time)


class LatencyAttribution(BaseModel):
    service: str = ""
    operation: str = ""
    segment_type: TraceSegmentType = TraceSegmentType.HTTP
    total_duration_ms: float = 0.0
    pct_of_trace: float = 0.0
    call_count: int = 0


# --- Engine ---


class DistributedTraceAnalyzer:
    """Trace segment analysis, bottleneck detection, latency attribution."""

    def __init__(
        self,
        max_traces: int = 500000,
        bottleneck_threshold: float = 0.2,
    ) -> None:
        self._max_traces = max_traces
        self._bottleneck_threshold = bottleneck_threshold
        self._traces: list[TraceRecord] = []
        self._bottleneck_reports: list[BottleneckReport] = []
        logger.info(
            "trace_analyzer.initialized",
            max_traces=max_traces,
            bottleneck_threshold=bottleneck_threshold,
        )

    def ingest_trace(
        self,
        trace_id: str,
        service: str,
        operation: str = "",
        segment_type: TraceSegmentType = TraceSegmentType.HTTP,
        duration_ms: float = 0.0,
        parent_span_id: str | None = None,
        status_code: int = 200,
        error: bool = False,
        tags: dict[str, str] | None = None,
    ) -> TraceRecord:
        record = TraceRecord(
            trace_id=trace_id,
            service=service,
            operation=operation,
            segment_type=segment_type,
            duration_ms=duration_ms,
            parent_span_id=parent_span_id,
            status_code=status_code,
            error=error,
            tags=tags or {},
        )
        self._traces.append(record)
        if len(self._traces) > self._max_traces:
            self._traces = self._traces[-self._max_traces :]
        logger.info(
            "trace_analyzer.trace_ingested",
            record_id=record.id,
            trace_id=trace_id,
            service=service,
        )
        return record

    def get_trace(self, record_id: str) -> TraceRecord | None:
        for t in self._traces:
            if t.id == record_id:
                return t
        return None

    def list_traces(
        self,
        service: str | None = None,
        segment_type: TraceSegmentType | None = None,
        limit: int = 100,
    ) -> list[TraceRecord]:
        results = list(self._traces)
        if service is not None:
            results = [t for t in results if t.service == service]
        if segment_type is not None:
            results = [t for t in results if t.segment_type == segment_type]
        return results[-limit:]

    def detect_bottlenecks(self, service: str | None = None) -> list[BottleneckReport]:
        targets = self._traces
        if service is not None:
            targets = [t for t in targets if t.service == service]
        # Group by service+operation
        groups: dict[tuple[str, str], list[TraceRecord]] = {}
        for t in targets:
            key = (t.service, t.operation)
            groups.setdefault(key, []).append(t)
        reports: list[BottleneckReport] = []
        for (svc, op), records in groups.items():
            durations = sorted(r.duration_ms for r in records)
            avg = sum(durations) / len(durations) if durations else 0.0
            p99_idx = max(0, int(len(durations) * 0.99) - 1)
            p99 = durations[p99_idx] if durations else 0.0
            # Determine severity based on p99/avg ratio
            ratio = p99 / avg if avg > 0 else 0.0
            if ratio > 5.0:
                severity = BottleneckSeverity.CRITICAL
                rec = "Critical latency variance — investigate immediately"
            elif ratio > 3.0:
                severity = BottleneckSeverity.MAJOR
                rec = "High latency variance — review slow requests"
            elif ratio > 2.0:
                severity = BottleneckSeverity.MODERATE
                rec = "Moderate variance — consider optimization"
            elif ratio > 1.5:
                severity = BottleneckSeverity.MINOR
                rec = "Minor variance — monitor trend"
            else:
                severity = BottleneckSeverity.NONE
                rec = "No bottleneck detected"
            if severity != BottleneckSeverity.NONE:
                report = BottleneckReport(
                    service=svc,
                    operation=op,
                    severity=severity,
                    avg_duration_ms=round(avg, 2),
                    p99_duration_ms=round(p99, 2),
                    sample_count=len(records),
                    recommendation=rec,
                )
                reports.append(report)
                self._bottleneck_reports.append(report)
        reports.sort(key=lambda r: r.p99_duration_ms, reverse=True)
        return reports

    def compute_latency_attribution(self, trace_id: str) -> list[LatencyAttribution]:
        spans = [t for t in self._traces if t.trace_id == trace_id]
        if not spans:
            return []
        total_duration = sum(s.duration_ms for s in spans)
        groups: dict[tuple[str, str, TraceSegmentType], list[TraceRecord]] = {}
        for s in spans:
            key = (s.service, s.operation, s.segment_type)
            groups.setdefault(key, []).append(s)
        attributions: list[LatencyAttribution] = []
        for (svc, op, seg), records in groups.items():
            dur = sum(r.duration_ms for r in records)
            pct = round((dur / total_duration * 100) if total_duration > 0 else 0.0, 1)
            attributions.append(
                LatencyAttribution(
                    service=svc,
                    operation=op,
                    segment_type=seg,
                    total_duration_ms=round(dur, 2),
                    pct_of_trace=pct,
                    call_count=len(records),
                )
            )
        attributions.sort(key=lambda a: a.total_duration_ms, reverse=True)
        return attributions

    def get_slow_endpoints(
        self, threshold_ms: float = 1000.0, limit: int = 20
    ) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str], list[float]] = {}
        for t in self._traces:
            key = (t.service, t.operation)
            groups.setdefault(key, []).append(t.duration_ms)
        slow: list[dict[str, Any]] = []
        for (svc, op), durations in groups.items():
            avg = sum(durations) / len(durations)
            if avg >= threshold_ms:
                slow.append(
                    {
                        "service": svc,
                        "operation": op,
                        "avg_duration_ms": round(avg, 2),
                        "sample_count": len(durations),
                    }
                )
        slow.sort(key=lambda s: s["avg_duration_ms"], reverse=True)
        return slow[:limit]

    def compare_baseline(
        self, service: str, operation: str, baseline_avg_ms: float
    ) -> dict[str, Any]:
        matching = [t for t in self._traces if t.service == service and t.operation == operation]
        if not matching:
            return {
                "service": service,
                "operation": operation,
                "current_avg_ms": 0.0,
                "baseline_avg_ms": baseline_avg_ms,
                "deviation_pct": 0.0,
                "status": "no_data",
            }
        current_avg = sum(m.duration_ms for m in matching) / len(matching)
        deviation = (
            (current_avg - baseline_avg_ms) / baseline_avg_ms * 100 if baseline_avg_ms > 0 else 0.0
        )
        if deviation > 50:
            status = "degraded"
        elif deviation > 20:
            status = "warning"
        elif deviation < -20:
            status = "improved"
        else:
            status = "normal"
        return {
            "service": service,
            "operation": operation,
            "current_avg_ms": round(current_avg, 2),
            "baseline_avg_ms": baseline_avg_ms,
            "deviation_pct": round(deviation, 1),
            "status": status,
        }

    def get_service_flow(self, trace_id: str) -> list[dict[str, Any]]:
        spans = [t for t in self._traces if t.trace_id == trace_id]
        spans.sort(key=lambda s: s.recorded_at)
        return [
            {
                "service": s.service,
                "operation": s.operation,
                "segment_type": s.segment_type.value,
                "duration_ms": s.duration_ms,
                "error": s.error,
                "parent_span_id": s.parent_span_id,
            }
            for s in spans
        ]

    def clear_traces(self) -> int:
        count = len(self._traces)
        self._traces.clear()
        self._bottleneck_reports.clear()
        logger.info("trace_analyzer.traces_cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        service_counts: dict[str, int] = {}
        segment_counts: dict[str, int] = {}
        error_count = 0
        for t in self._traces:
            service_counts[t.service] = service_counts.get(t.service, 0) + 1
            segment_counts[t.segment_type] = segment_counts.get(t.segment_type, 0) + 1
            if t.error:
                error_count += 1
        return {
            "total_traces": len(self._traces),
            "unique_services": len(service_counts),
            "error_count": error_count,
            "bottleneck_reports": len(self._bottleneck_reports),
            "service_distribution": service_counts,
            "segment_distribution": segment_counts,
        }
