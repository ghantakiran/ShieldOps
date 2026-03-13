"""Tests for CrossServiceHopTracerEngine."""

from __future__ import annotations

from shieldops.observability.cross_service_hop_tracer_engine import (
    CrossServiceHopAnalysis,
    CrossServiceHopRecord,
    CrossServiceHopReport,
    CrossServiceHopTracerEngine,
    HopType,
    ServiceBoundary,
    TracingCompleteness,
)


def test_add_record() -> None:
    engine = CrossServiceHopTracerEngine()
    rec = engine.add_record(
        trace_id="trace-001",
        hop_type=HopType.DEPENDENCY,
        service_boundary=ServiceBoundary.CROSS_TEAM,
        tracing_completeness=TracingCompleteness.FULL_TRACE,
        latency_ms=45.0,
        hop_index=1,
        source_service="svc-a",
        target_service="svc-b",
    )
    assert isinstance(rec, CrossServiceHopRecord)
    assert rec.trace_id == "trace-001"
    assert rec.latency_ms == 45.0


def test_process() -> None:
    engine = CrossServiceHopTracerEngine()
    rec = engine.add_record(
        trace_id="trace-002",
        hop_type=HopType.CASCADE,
        service_boundary=ServiceBoundary.CROSS_ORG,
        tracing_completeness=TracingCompleteness.BLOCKED_TRACE,
        latency_ms=200.0,
    )
    result = engine.process(rec.id)
    assert isinstance(result, CrossServiceHopAnalysis)
    assert result.trace_id == "trace-002"
    assert result.is_blocked is True


def test_process_not_found() -> None:
    engine = CrossServiceHopTracerEngine()
    result = engine.process("ghost-trace")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = CrossServiceHopTracerEngine()
    for tid, ht, sb, tc, lat in [
        (
            "t1",
            HopType.DEPENDENCY,
            ServiceBoundary.SAME_SERVICE,
            TracingCompleteness.FULL_TRACE,
            10.0,
        ),
        (
            "t2",
            HopType.SHARED_RESOURCE,
            ServiceBoundary.SAME_TEAM,
            TracingCompleteness.PARTIAL_TRACE,
            50.0,
        ),
        (
            "t3",
            HopType.CASCADE,
            ServiceBoundary.CROSS_TEAM,
            TracingCompleteness.BLOCKED_TRACE,
            200.0,
        ),
        (
            "t4",
            HopType.CONFIGURATION,
            ServiceBoundary.CROSS_ORG,
            TracingCompleteness.ESTIMATED_TRACE,
            100.0,
        ),
    ]:
        engine.add_record(
            trace_id=tid,
            hop_type=ht,
            service_boundary=sb,
            tracing_completeness=tc,
            latency_ms=lat,
        )
    report = engine.generate_report()
    assert isinstance(report, CrossServiceHopReport)
    assert report.total_records == 4
    assert "dependency" in report.by_hop_type
    assert len(report.blocked_traces) >= 1


def test_get_stats() -> None:
    engine = CrossServiceHopTracerEngine()
    engine.add_record(hop_type=HopType.DEPENDENCY, latency_ms=10.0)
    engine.add_record(hop_type=HopType.CASCADE, latency_ms=100.0)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "hop_type_distribution" in stats


def test_clear_data() -> None:
    engine = CrossServiceHopTracerEngine()
    engine.add_record(trace_id="t-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_trace_cross_service_hops() -> None:
    engine = CrossServiceHopTracerEngine()
    engine.add_record(
        trace_id="trace-A",
        hop_index=1,
        source_service="svc-x",
        target_service="svc-y",
        latency_ms=30.0,
    )
    engine.add_record(
        trace_id="trace-A",
        hop_index=2,
        source_service="svc-y",
        target_service="svc-z",
        latency_ms=50.0,
    )
    engine.add_record(
        trace_id="trace-B",
        hop_index=1,
        source_service="svc-p",
        target_service="svc-q",
        latency_ms=5.0,
    )
    results = engine.trace_cross_service_hops()
    assert isinstance(results, list)
    trace_a = next(r for r in results if r["trace_id"] == "trace-A")
    assert trace_a["hop_count"] == 2
    assert trace_a["total_latency_ms"] == 80.0


def test_identify_hop_blockers() -> None:
    engine = CrossServiceHopTracerEngine()
    engine.add_record(
        trace_id="trace-X",
        hop_index=2,
        tracing_completeness=TracingCompleteness.BLOCKED_TRACE,
        source_service="svc-a",
        target_service="svc-b",
    )
    engine.add_record(
        trace_id="trace-Y",
        hop_index=1,
        tracing_completeness=TracingCompleteness.FULL_TRACE,
    )
    results = engine.identify_hop_blockers()
    assert isinstance(results, list)
    assert any(r["trace_id"] == "trace-X" for r in results)
    assert all(r.get("hop_index") is not None for r in results)


def test_compute_cross_service_latency() -> None:
    engine = CrossServiceHopTracerEngine()
    engine.add_record(service_boundary=ServiceBoundary.SAME_SERVICE, latency_ms=5.0)
    engine.add_record(service_boundary=ServiceBoundary.CROSS_ORG, latency_ms=300.0)
    engine.add_record(service_boundary=ServiceBoundary.CROSS_ORG, latency_ms=200.0)
    results = engine.compute_cross_service_latency()
    assert isinstance(results, list)
    assert results[0]["avg_latency_ms"] >= results[-1]["avg_latency_ms"]
    cross_org = next(r for r in results if r["service_boundary"] == "cross_org")
    assert cross_org["avg_latency_ms"] == 250.0
