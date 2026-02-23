"""Request correlation: traces and spans for request tracing.

Enables tracing requests through internal calls, agents, and background
tasks with span tracking and trace reconstruction.
"""

from __future__ import annotations

import enum
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class SpanStatus(enum.StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"


# ── Models ───────────────────────────────────────────────────────────


class CorrelationSpan(BaseModel):
    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: str | None = None
    request_id: str = ""
    operation: str = ""
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None
    duration_ms: float | None = None
    status: SpanStatus = SpanStatus.IN_PROGRESS
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorrelationTrace(BaseModel):
    request_id: str
    spans: list[CorrelationSpan] = Field(default_factory=list)
    entry_point: str = ""
    total_duration_ms: float | None = None
    status: SpanStatus = SpanStatus.IN_PROGRESS
    started_at: float = Field(default_factory=time.time)
    ended_at: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Correlator ───────────────────────────────────────────────────────


class RequestCorrelator:
    """Trace and span manager for request correlation.

    Parameters
    ----------
    max_traces:
        Maximum number of traces to keep in memory.
    trace_ttl_minutes:
        Traces older than this are eligible for cleanup.
    """

    def __init__(
        self,
        max_traces: int = 10000,
        trace_ttl_minutes: int = 60,
    ) -> None:
        self._traces: OrderedDict[str, CorrelationTrace] = OrderedDict()
        self._max_traces = max_traces
        self._trace_ttl = trace_ttl_minutes * 60  # seconds

    # ── Trace lifecycle ──────────────────────────────────────────

    def start_trace(
        self,
        request_id: str,
        entry_point: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CorrelationTrace:
        """Begin a new trace for *request_id*."""
        trace = CorrelationTrace(
            request_id=request_id,
            entry_point=entry_point,
            metadata=metadata or {},
        )
        self._traces[request_id] = trace
        # Evict oldest if at capacity
        while len(self._traces) > self._max_traces:
            self._traces.popitem(last=False)
        return trace

    def end_trace(
        self,
        request_id: str,
        status: SpanStatus = SpanStatus.COMPLETED,
    ) -> CorrelationTrace | None:
        trace = self._traces.get(request_id)
        if trace is None:
            return None
        now = time.time()
        trace.ended_at = now
        trace.status = status
        trace.total_duration_ms = round((now - trace.started_at) * 1000, 2)
        return trace

    def get_trace(self, request_id: str) -> CorrelationTrace | None:
        return self._traces.get(request_id)

    # ── Span lifecycle ───────────────────────────────────────────

    def start_span(
        self,
        request_id: str,
        operation: str,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CorrelationSpan | None:
        trace = self._traces.get(request_id)
        if trace is None:
            return None
        span = CorrelationSpan(
            request_id=request_id,
            operation=operation,
            parent_span_id=parent_span_id,
            metadata=metadata or {},
        )
        trace.spans.append(span)
        return span

    def end_span(
        self,
        request_id: str,
        span_id: str,
        status: SpanStatus = SpanStatus.COMPLETED,
        metadata: dict[str, Any] | None = None,
    ) -> CorrelationSpan | None:
        trace = self._traces.get(request_id)
        if trace is None:
            return None
        for span in trace.spans:
            if span.span_id == span_id:
                now = time.time()
                span.end_time = now
                span.duration_ms = round((now - span.start_time) * 1000, 2)
                span.status = status
                if metadata:
                    span.metadata.update(metadata)
                return span
        return None

    # ── Context managers ─────────────────────────────────────────

    @contextmanager
    def correlation_span(
        self,
        request_id: str,
        operation: str,
        parent_span_id: str | None = None,
    ) -> Iterator[CorrelationSpan | None]:
        """Sync context manager for span creation."""
        span = self.start_span(request_id, operation, parent_span_id)
        try:
            yield span
        except Exception:
            if span:
                self.end_span(request_id, span.span_id, SpanStatus.ERROR)
            raise
        else:
            if span:
                self.end_span(request_id, span.span_id, SpanStatus.COMPLETED)

    @asynccontextmanager
    async def async_correlation_span(
        self,
        request_id: str,
        operation: str,
        parent_span_id: str | None = None,
    ) -> AsyncIterator[CorrelationSpan | None]:
        """Async context manager for span creation."""
        span = self.start_span(request_id, operation, parent_span_id)
        try:
            yield span
        except Exception:
            if span:
                self.end_span(request_id, span.span_id, SpanStatus.ERROR)
            raise
        else:
            if span:
                self.end_span(request_id, span.span_id, SpanStatus.COMPLETED)

    # ── Queries ──────────────────────────────────────────────────

    def search_traces(
        self,
        entry_point: str | None = None,
        status: SpanStatus | None = None,
        limit: int = 50,
    ) -> list[CorrelationTrace]:
        results: list[CorrelationTrace] = []
        for trace in reversed(self._traces.values()):
            if entry_point and entry_point not in trace.entry_point:
                continue
            if status and trace.status != status:
                continue
            results.append(trace)
            if len(results) >= limit:
                break
        return results

    def get_slow_traces(
        self,
        threshold_ms: float = 1000.0,
        limit: int = 50,
    ) -> list[CorrelationTrace]:
        slow: list[CorrelationTrace] = []
        for trace in reversed(self._traces.values()):
            if trace.total_duration_ms is not None and trace.total_duration_ms >= threshold_ms:
                slow.append(trace)
                if len(slow) >= limit:
                    break
        return slow

    def cleanup_old_traces(self) -> int:
        """Remove traces older than the configured TTL."""
        cutoff = time.time() - self._trace_ttl
        to_remove = [rid for rid, trace in self._traces.items() if trace.started_at < cutoff]
        for rid in to_remove:
            del self._traces[rid]
        if to_remove:
            logger.info("correlation_traces_cleaned", removed=len(to_remove))
        return len(to_remove)

    # ── Stats ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        total = len(self._traces)
        active = sum(1 for t in self._traces.values() if t.status == SpanStatus.IN_PROGRESS)
        completed = sum(1 for t in self._traces.values() if t.status == SpanStatus.COMPLETED)
        errored = sum(1 for t in self._traces.values() if t.status == SpanStatus.ERROR)
        durations = [
            t.total_duration_ms for t in self._traces.values() if t.total_duration_ms is not None
        ]
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
        return {
            "total_traces": total,
            "active": active,
            "completed": completed,
            "errored": errored,
            "avg_duration_ms": avg_duration,
            "max_traces": self._max_traces,
        }
