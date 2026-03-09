"""Tests for shieldops.observability.trace_bottleneck_analyzer — TraceBottleneckAnalyzer."""

from __future__ import annotations

from shieldops.observability.trace_bottleneck_analyzer import (
    BottleneckType,
    OptimizationPriority,
    SpanKind,
    TraceBottleneckAnalyzer,
    TraceSpanRecord,
)


def _engine(**kw) -> TraceBottleneckAnalyzer:
    return TraceBottleneckAnalyzer(**kw)


class TestEnums:
    def test_span_kind_server(self):
        assert SpanKind.SERVER == "server"

    def test_bottleneck_type(self):
        assert BottleneckType.SLOW_QUERY == "slow_query"

    def test_optimization_priority(self):
        assert OptimizationPriority.HIGH == "high"


class TestModels:
    def test_record_defaults(self):
        r = TraceSpanRecord()
        assert r.id
        assert r.created_at > 0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(
            trace_id="t-1",
            span_id="s-1",
            operation_name="GET /api/users",
            service="api",
            duration_ms=150.0,
        )
        assert rec.trace_id == "t-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(
                trace_id=f"t-{i}",
                span_id=f"s-{i}",
                operation_name=f"op-{i}",
                service="api",
                duration_ms=float(i),
            )
        assert len(eng._records) == 3


class TestCriticalPath:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            trace_id="t-1", span_id="s-1", operation_name="api", service="api", duration_ms=100.0
        )
        eng.add_record(
            trace_id="t-1", span_id="s-2", operation_name="db", service="db", duration_ms=80.0
        )
        result = eng.analyze_critical_path("t-1")
        assert isinstance(result, dict)


class TestLatencyAttribution:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            trace_id="t-1", span_id="s-1", operation_name="api", service="api", duration_ms=100.0
        )
        result = eng.compute_latency_attribution("api")
        assert isinstance(result, dict)


class TestOptimizationTargets:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            trace_id="t-1",
            span_id="s-1",
            operation_name="slow-op",
            service="api",
            duration_ms=5000.0,
        )
        result = eng.identify_optimization_targets()
        assert isinstance(result, list)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(
            trace_id="t-1", span_id="s-1", operation_name="api", service="api", duration_ms=100.0
        )
        result = eng.process("api")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(
            trace_id="t-1", span_id="s-1", operation_name="api", service="api", duration_ms=100.0
        )
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            trace_id="t-1", span_id="s-1", operation_name="api", service="api", duration_ms=100.0
        )
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(
            trace_id="t-1", span_id="s-1", operation_name="api", service="api", duration_ms=100.0
        )
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
