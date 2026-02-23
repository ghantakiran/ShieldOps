"""Tests for request correlation: traces, spans, and context managers."""

from __future__ import annotations

import time

import pytest

from shieldops.observability.request_correlation import (
    CorrelationSpan,
    CorrelationTrace,
    RequestCorrelator,
    SpanStatus,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _make_correlator(**kwargs: object) -> RequestCorrelator:
    return RequestCorrelator(**kwargs)


# =========================================================================
# start_trace / end_trace lifecycle
# =========================================================================


class TestTraceLifecycle:
    def test_start_trace_returns_trace(self):
        cor = _make_correlator()
        trace = cor.start_trace("req-1")
        assert isinstance(trace, CorrelationTrace)
        assert trace.request_id == "req-1"

    def test_start_trace_sets_in_progress(self):
        cor = _make_correlator()
        trace = cor.start_trace("req-1")
        assert trace.status == SpanStatus.IN_PROGRESS

    def test_start_trace_with_entry_point(self):
        cor = _make_correlator()
        trace = cor.start_trace("req-1", entry_point="/api/v1/agents")
        assert trace.entry_point == "/api/v1/agents"

    def test_start_trace_with_metadata(self):
        cor = _make_correlator()
        trace = cor.start_trace("req-1", metadata={"user": "admin"})
        assert trace.metadata["user"] == "admin"

    def test_end_trace_sets_completed(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        ended = cor.end_trace("req-1")
        assert ended is not None
        assert ended.status == SpanStatus.COMPLETED
        assert ended.ended_at is not None

    def test_end_trace_calculates_duration(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        ended = cor.end_trace("req-1")
        assert ended.total_duration_ms is not None
        assert ended.total_duration_ms >= 0

    def test_end_trace_with_error_status(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        ended = cor.end_trace("req-1", status=SpanStatus.ERROR)
        assert ended.status == SpanStatus.ERROR

    def test_end_nonexistent_trace_returns_none(self):
        cor = _make_correlator()
        assert cor.end_trace("nope") is None

    def test_get_trace(self):
        cor = _make_correlator()
        cor.start_trace("req-1", entry_point="test")
        trace = cor.get_trace("req-1")
        assert trace is not None
        assert trace.entry_point == "test"

    def test_get_nonexistent_trace_returns_none(self):
        cor = _make_correlator()
        assert cor.get_trace("nope") is None


# =========================================================================
# start_span / end_span lifecycle
# =========================================================================


class TestSpanLifecycle:
    def test_start_span_returns_span(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        span = cor.start_span("req-1", "db_query")
        assert isinstance(span, CorrelationSpan)
        assert span.operation == "db_query"

    def test_start_span_adds_to_trace(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        cor.start_span("req-1", "op1")
        trace = cor.get_trace("req-1")
        assert len(trace.spans) == 1

    def test_start_span_no_trace_returns_none(self):
        cor = _make_correlator()
        assert cor.start_span("nope", "op") is None

    def test_end_span_sets_completed(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        span = cor.start_span("req-1", "op")
        ended = cor.end_span("req-1", span.span_id)
        assert ended is not None
        assert ended.status == SpanStatus.COMPLETED

    def test_end_span_calculates_duration(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        span = cor.start_span("req-1", "op")
        ended = cor.end_span("req-1", span.span_id)
        assert ended.duration_ms is not None
        assert ended.duration_ms >= 0

    def test_end_span_with_metadata(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        span = cor.start_span("req-1", "op")
        ended = cor.end_span("req-1", span.span_id, metadata={"rows": 42})
        assert ended.metadata["rows"] == 42

    def test_end_span_no_trace_returns_none(self):
        cor = _make_correlator()
        assert cor.end_span("nope", "span-id") is None

    def test_end_span_wrong_id_returns_none(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        cor.start_span("req-1", "op")
        assert cor.end_span("req-1", "wrong-span-id") is None

    def test_span_has_request_id(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        span = cor.start_span("req-1", "op")
        assert span.request_id == "req-1"


# =========================================================================
# Nested spans (parent_span_id)
# =========================================================================


class TestNestedSpans:
    def test_child_span_has_parent_id(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        parent = cor.start_span("req-1", "parent_op")
        child = cor.start_span("req-1", "child_op", parent_span_id=parent.span_id)
        assert child.parent_span_id == parent.span_id

    def test_parent_span_has_no_parent(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        parent = cor.start_span("req-1", "parent_op")
        assert parent.parent_span_id is None

    def test_multiple_children(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        parent = cor.start_span("req-1", "parent")
        child1 = cor.start_span("req-1", "child1", parent_span_id=parent.span_id)
        child2 = cor.start_span("req-1", "child2", parent_span_id=parent.span_id)
        assert child1.parent_span_id == parent.span_id
        assert child2.parent_span_id == parent.span_id
        trace = cor.get_trace("req-1")
        assert len(trace.spans) == 3


# =========================================================================
# correlation_span context manager (sync)
# =========================================================================


class TestCorrelationSpanSync:
    def test_span_created_and_completed(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        with cor.correlation_span("req-1", "sync_op") as span:
            assert span is not None
            assert span.status == SpanStatus.IN_PROGRESS

        trace = cor.get_trace("req-1")
        assert trace.spans[0].status == SpanStatus.COMPLETED

    def test_span_with_parent(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        parent = cor.start_span("req-1", "parent")
        with cor.correlation_span("req-1", "child", parent_span_id=parent.span_id) as span:
            assert span.parent_span_id == parent.span_id

    def test_span_none_when_no_trace(self):
        cor = _make_correlator()
        with cor.correlation_span("nope", "op") as span:
            assert span is None

    def test_error_sets_error_status(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        with pytest.raises(ValueError), cor.correlation_span("req-1", "failing_op") as _span:
            raise ValueError("boom")

        trace = cor.get_trace("req-1")
        assert trace.spans[0].status == SpanStatus.ERROR


# =========================================================================
# async_correlation_span context manager
# =========================================================================


class TestAsyncCorrelationSpan:
    @pytest.mark.asyncio
    async def test_async_span_created_and_completed(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        async with cor.async_correlation_span("req-1", "async_op") as span:
            assert span is not None
            assert span.status == SpanStatus.IN_PROGRESS

        trace = cor.get_trace("req-1")
        assert trace.spans[0].status == SpanStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_async_span_error_handling(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        with pytest.raises(RuntimeError):
            async with cor.async_correlation_span("req-1", "failing") as _span:
                raise RuntimeError("async boom")

        trace = cor.get_trace("req-1")
        assert trace.spans[0].status == SpanStatus.ERROR

    @pytest.mark.asyncio
    async def test_async_span_none_when_no_trace(self):
        cor = _make_correlator()
        async with cor.async_correlation_span("nope", "op") as span:
            assert span is None

    @pytest.mark.asyncio
    async def test_async_span_with_parent(self):
        cor = _make_correlator()
        cor.start_trace("req-1")
        parent = cor.start_span("req-1", "parent")
        async with cor.async_correlation_span(
            "req-1", "child", parent_span_id=parent.span_id
        ) as span:
            assert span.parent_span_id == parent.span_id


# =========================================================================
# search_traces
# =========================================================================


class TestSearchTraces:
    def test_search_by_entry_point(self):
        cor = _make_correlator()
        cor.start_trace("r1", entry_point="/api/v1/agents")
        cor.start_trace("r2", entry_point="/api/v1/incidents")
        cor.start_trace("r3", entry_point="/api/v1/agents/123")

        results = cor.search_traces(entry_point="agents")
        assert len(results) == 2

    def test_search_by_status(self):
        cor = _make_correlator()
        cor.start_trace("r1")
        cor.start_trace("r2")
        cor.end_trace("r1", SpanStatus.COMPLETED)

        results = cor.search_traces(status=SpanStatus.COMPLETED)
        assert len(results) == 1
        assert results[0].request_id == "r1"

    def test_search_with_limit(self):
        cor = _make_correlator()
        for i in range(10):
            cor.start_trace(f"r{i}", entry_point="test")

        results = cor.search_traces(entry_point="test", limit=3)
        assert len(results) == 3

    def test_search_no_filters(self):
        cor = _make_correlator()
        cor.start_trace("r1")
        cor.start_trace("r2")

        results = cor.search_traces()
        assert len(results) == 2

    def test_search_no_results(self):
        cor = _make_correlator()
        cor.start_trace("r1", entry_point="agents")

        results = cor.search_traces(entry_point="nonexistent")
        assert results == []


# =========================================================================
# get_slow_traces
# =========================================================================


class TestGetSlowTraces:
    def test_returns_slow_traces(self):
        cor = _make_correlator()
        cor.start_trace("r1")
        trace = cor.get_trace("r1")
        # Manually set duration
        trace.total_duration_ms = 2000.0
        trace.status = SpanStatus.COMPLETED

        results = cor.get_slow_traces(threshold_ms=1000.0)
        assert len(results) == 1

    def test_excludes_fast_traces(self):
        cor = _make_correlator()
        cor.start_trace("r1")
        trace = cor.get_trace("r1")
        trace.total_duration_ms = 500.0

        results = cor.get_slow_traces(threshold_ms=1000.0)
        assert results == []

    def test_excludes_traces_without_duration(self):
        cor = _make_correlator()
        cor.start_trace("r1")  # no duration set

        results = cor.get_slow_traces(threshold_ms=100.0)
        assert results == []

    def test_slow_traces_limit(self):
        cor = _make_correlator()
        for i in range(5):
            cor.start_trace(f"r{i}")
            trace = cor.get_trace(f"r{i}")
            trace.total_duration_ms = 5000.0

        results = cor.get_slow_traces(threshold_ms=1000.0, limit=2)
        assert len(results) == 2


# =========================================================================
# cleanup_old_traces
# =========================================================================


class TestCleanupOldTraces:
    def test_removes_old_traces(self):
        cor = _make_correlator(trace_ttl_minutes=60)
        cor.start_trace("r1")
        # Backdate the trace
        cor.get_trace("r1").started_at = time.time() - 7200  # 2 hours ago

        removed = cor.cleanup_old_traces()
        assert removed == 1
        assert cor.get_trace("r1") is None

    def test_keeps_recent_traces(self):
        cor = _make_correlator(trace_ttl_minutes=60)
        cor.start_trace("r1")

        removed = cor.cleanup_old_traces()
        assert removed == 0
        assert cor.get_trace("r1") is not None

    def test_mixed_cleanup(self):
        cor = _make_correlator(trace_ttl_minutes=60)
        cor.start_trace("old")
        cor.get_trace("old").started_at = time.time() - 7200
        cor.start_trace("new")

        removed = cor.cleanup_old_traces()
        assert removed == 1
        assert cor.get_trace("old") is None
        assert cor.get_trace("new") is not None


# =========================================================================
# Max traces eviction
# =========================================================================


class TestMaxTracesEviction:
    def test_evicts_oldest_when_at_capacity(self):
        cor = _make_correlator(max_traces=3)
        cor.start_trace("r1")
        cor.start_trace("r2")
        cor.start_trace("r3")
        cor.start_trace("r4")  # should evict r1

        assert cor.get_trace("r1") is None
        assert cor.get_trace("r4") is not None

    def test_total_never_exceeds_max(self):
        cor = _make_correlator(max_traces=5)
        for i in range(20):
            cor.start_trace(f"r{i}")

        stats = cor.get_stats()
        assert stats["total_traces"] <= 5


# =========================================================================
# Duration calculation
# =========================================================================


class TestDuration:
    def test_trace_duration_in_ms(self):
        cor = _make_correlator()
        cor.start_trace("r1")
        # Sleep briefly to ensure measurable duration
        ended = cor.end_trace("r1")
        assert ended.total_duration_ms >= 0

    def test_span_duration_in_ms(self):
        cor = _make_correlator()
        cor.start_trace("r1")
        span = cor.start_span("r1", "op")
        ended = cor.end_span("r1", span.span_id)
        assert ended.duration_ms >= 0
        assert ended.end_time is not None


# =========================================================================
# Stats
# =========================================================================


class TestStats:
    def test_empty_stats(self):
        cor = _make_correlator()
        stats = cor.get_stats()
        assert stats["total_traces"] == 0
        assert stats["active"] == 0
        assert stats["completed"] == 0
        assert stats["errored"] == 0
        assert stats["avg_duration_ms"] == 0.0

    def test_active_count(self):
        cor = _make_correlator()
        cor.start_trace("r1")
        cor.start_trace("r2")
        stats = cor.get_stats()
        assert stats["active"] == 2

    def test_completed_count(self):
        cor = _make_correlator()
        cor.start_trace("r1")
        cor.start_trace("r2")
        cor.end_trace("r1", SpanStatus.COMPLETED)
        stats = cor.get_stats()
        assert stats["completed"] == 1
        assert stats["active"] == 1

    def test_errored_count(self):
        cor = _make_correlator()
        cor.start_trace("r1")
        cor.end_trace("r1", SpanStatus.ERROR)
        stats = cor.get_stats()
        assert stats["errored"] == 1

    def test_avg_duration(self):
        cor = _make_correlator()
        cor.start_trace("r1")
        cor.start_trace("r2")
        trace1 = cor.get_trace("r1")
        trace1.total_duration_ms = 100.0
        trace1.status = SpanStatus.COMPLETED
        trace2 = cor.get_trace("r2")
        trace2.total_duration_ms = 200.0
        trace2.status = SpanStatus.COMPLETED

        stats = cor.get_stats()
        assert stats["avg_duration_ms"] == 150.0

    def test_max_traces_in_stats(self):
        cor = _make_correlator(max_traces=500)
        stats = cor.get_stats()
        assert stats["max_traces"] == 500


# =========================================================================
# Model tests
# =========================================================================


class TestModels:
    def test_span_status_values(self):
        assert SpanStatus.IN_PROGRESS == "in_progress"
        assert SpanStatus.COMPLETED == "completed"
        assert SpanStatus.ERROR == "error"

    def test_correlation_span_defaults(self):
        span = CorrelationSpan()
        assert span.span_id  # should have auto-generated id
        assert span.parent_span_id is None
        assert span.status == SpanStatus.IN_PROGRESS
        assert span.end_time is None
        assert span.duration_ms is None

    def test_correlation_trace_defaults(self):
        trace = CorrelationTrace(request_id="req-1")
        assert trace.request_id == "req-1"
        assert trace.spans == []
        assert trace.entry_point == ""
        assert trace.total_duration_ms is None
        assert trace.status == SpanStatus.IN_PROGRESS

    def test_span_id_uniqueness(self):
        s1 = CorrelationSpan()
        s2 = CorrelationSpan()
        assert s1.span_id != s2.span_id
