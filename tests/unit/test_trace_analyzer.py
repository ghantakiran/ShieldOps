"""Tests for shieldops.analytics.trace_analyzer — DistributedTraceAnalyzer."""

from __future__ import annotations

from shieldops.analytics.trace_analyzer import (
    AnalysisWindow,
    BottleneckReport,
    BottleneckSeverity,
    DistributedTraceAnalyzer,
    LatencyAttribution,
    TraceRecord,
    TraceSegmentType,
)


def _engine(**kw) -> DistributedTraceAnalyzer:
    return DistributedTraceAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_segment_http(self):
        assert TraceSegmentType.HTTP == "http"

    def test_segment_grpc(self):
        assert TraceSegmentType.GRPC == "grpc"

    def test_segment_database(self):
        assert TraceSegmentType.DATABASE == "database"

    def test_segment_cache(self):
        assert TraceSegmentType.CACHE == "cache"

    def test_segment_queue(self):
        assert TraceSegmentType.QUEUE == "queue"

    def test_segment_internal(self):
        assert TraceSegmentType.INTERNAL == "internal"

    def test_severity_none(self):
        assert BottleneckSeverity.NONE == "none"

    def test_severity_minor(self):
        assert BottleneckSeverity.MINOR == "minor"

    def test_severity_moderate(self):
        assert BottleneckSeverity.MODERATE == "moderate"

    def test_severity_major(self):
        assert BottleneckSeverity.MAJOR == "major"

    def test_severity_critical(self):
        assert BottleneckSeverity.CRITICAL == "critical"

    def test_window_last_hour(self):
        assert AnalysisWindow.LAST_HOUR == "last_hour"

    def test_window_last_day(self):
        assert AnalysisWindow.LAST_DAY == "last_day"

    def test_window_last_week(self):
        assert AnalysisWindow.LAST_WEEK == "last_week"

    def test_window_last_month(self):
        assert AnalysisWindow.LAST_MONTH == "last_month"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_trace_record_defaults(self):
        r = TraceRecord()
        assert r.id
        assert r.segment_type == TraceSegmentType.HTTP
        assert r.duration_ms == 0.0
        assert r.error is False

    def test_bottleneck_report_defaults(self):
        b = BottleneckReport()
        assert b.severity == BottleneckSeverity.NONE
        assert b.sample_count == 0

    def test_latency_attribution_defaults(self):
        a = LatencyAttribution()
        assert a.pct_of_trace == 0.0
        assert a.call_count == 0


# ---------------------------------------------------------------------------
# ingest_trace
# ---------------------------------------------------------------------------


class TestIngestTrace:
    def test_basic_ingest(self):
        eng = _engine()
        rec = eng.ingest_trace("t1", "svc-a", operation="GET /api")
        assert rec.trace_id == "t1"
        assert rec.service == "svc-a"

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.ingest_trace("t1", "svc-a")
        r2 = eng.ingest_trace("t2", "svc-b")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_traces=3)
        for i in range(5):
            eng.ingest_trace(f"t{i}", "svc")
        assert len(eng._traces) == 3

    def test_with_error(self):
        eng = _engine()
        rec = eng.ingest_trace("t1", "svc-a", error=True, status_code=500)
        assert rec.error is True
        assert rec.status_code == 500

    def test_with_tags(self):
        eng = _engine()
        rec = eng.ingest_trace("t1", "svc-a", tags={"env": "prod"})
        assert rec.tags == {"env": "prod"}


# ---------------------------------------------------------------------------
# get_trace / list_traces
# ---------------------------------------------------------------------------


class TestGetTrace:
    def test_found(self):
        eng = _engine()
        rec = eng.ingest_trace("t1", "svc-a")
        assert eng.get_trace(rec.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_trace("nonexistent") is None


class TestListTraces:
    def test_list_all(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a")
        eng.ingest_trace("t2", "svc-b")
        assert len(eng.list_traces()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a")
        eng.ingest_trace("t2", "svc-b")
        results = eng.list_traces(service="svc-a")
        assert len(results) == 1

    def test_filter_by_segment_type(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a", segment_type=TraceSegmentType.HTTP)
        eng.ingest_trace("t2", "svc-a", segment_type=TraceSegmentType.DATABASE)
        results = eng.list_traces(segment_type=TraceSegmentType.DATABASE)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# detect_bottlenecks
# ---------------------------------------------------------------------------


class TestDetectBottlenecks:
    def test_no_bottlenecks(self):
        eng = _engine()
        for _ in range(10):
            eng.ingest_trace("t1", "svc-a", operation="GET /api", duration_ms=100.0)
        reports = eng.detect_bottlenecks()
        assert len(reports) == 0

    def test_bottleneck_detected(self):
        eng = _engine()
        # Use enough samples so p99 captures the outlier tail
        for _ in range(50):
            eng.ingest_trace("t1", "svc-a", operation="GET /api", duration_ms=10.0)
        for _ in range(10):
            eng.ingest_trace("t1", "svc-a", operation="GET /api", duration_ms=5000.0)
        reports = eng.detect_bottlenecks()
        assert len(reports) >= 1

    def test_filter_by_service(self):
        eng = _engine()
        for _ in range(9):
            eng.ingest_trace("t1", "svc-a", operation="op", duration_ms=10.0)
        eng.ingest_trace("t1", "svc-a", operation="op", duration_ms=5000.0)
        eng.ingest_trace("t2", "svc-b", operation="op2", duration_ms=10.0)
        reports = eng.detect_bottlenecks(service="svc-b")
        bottleneck_svcs = [r.service for r in reports]
        assert "svc-a" not in bottleneck_svcs


# ---------------------------------------------------------------------------
# compute_latency_attribution
# ---------------------------------------------------------------------------


class TestLatencyAttribution:
    def test_empty_trace(self):
        eng = _engine()
        attrs = eng.compute_latency_attribution("nonexistent")
        assert attrs == []

    def test_single_span(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a", operation="op", duration_ms=100.0)
        attrs = eng.compute_latency_attribution("t1")
        assert len(attrs) == 1
        assert attrs[0].pct_of_trace == 100.0

    def test_multi_span_attribution(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a", operation="op1", duration_ms=60.0)
        eng.ingest_trace("t1", "svc-b", operation="op2", duration_ms=40.0)
        attrs = eng.compute_latency_attribution("t1")
        assert len(attrs) == 2
        assert attrs[0].total_duration_ms == 60.0


# ---------------------------------------------------------------------------
# slow endpoints / compare baseline / service flow
# ---------------------------------------------------------------------------


class TestSlowEndpoints:
    def test_no_slow(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a", operation="op", duration_ms=10.0)
        slow = eng.get_slow_endpoints(threshold_ms=1000.0)
        assert len(slow) == 0

    def test_slow_found(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a", operation="op", duration_ms=2000.0)
        slow = eng.get_slow_endpoints(threshold_ms=1000.0)
        assert len(slow) == 1


class TestCompareBaseline:
    def test_no_data(self):
        eng = _engine()
        result = eng.compare_baseline("svc-a", "op", 100.0)
        assert result["status"] == "no_data"

    def test_normal(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a", operation="op", duration_ms=100.0)
        result = eng.compare_baseline("svc-a", "op", 100.0)
        assert result["status"] == "normal"

    def test_degraded(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a", operation="op", duration_ms=200.0)
        result = eng.compare_baseline("svc-a", "op", 100.0)
        assert result["status"] in ("warning", "degraded")


class TestServiceFlow:
    def test_empty(self):
        eng = _engine()
        flow = eng.get_service_flow("nonexistent")
        assert flow == []

    def test_flow_returned(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a", operation="op1", duration_ms=50.0)
        eng.ingest_trace("t1", "svc-b", operation="op2", duration_ms=30.0)
        flow = eng.get_service_flow("t1")
        assert len(flow) == 2


# ---------------------------------------------------------------------------
# clear_traces / get_stats
# ---------------------------------------------------------------------------


class TestClearTraces:
    def test_clear(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a")
        count = eng.clear_traces()
        assert count == 1
        assert len(eng._traces) == 0


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_traces"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.ingest_trace("t1", "svc-a", error=True)
        eng.ingest_trace("t2", "svc-b")
        stats = eng.get_stats()
        assert stats["total_traces"] == 2
        assert stats["unique_services"] == 2
        assert stats["error_count"] == 1
