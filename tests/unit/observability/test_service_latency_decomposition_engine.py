"""Tests for ServiceLatencyDecompositionEngine."""

from __future__ import annotations

from shieldops.observability.service_latency_decomposition_engine import (
    DecompositionMethod,
    LatencyComponent,
    LatencyTrend,
    ServiceLatencyAnalysis,
    ServiceLatencyDecompositionEngine,
    ServiceLatencyRecord,
    ServiceLatencyReport,
)


def test_add_record() -> None:
    engine = ServiceLatencyDecompositionEngine()
    rec = engine.add_record(
        service_name="svc-a",
        operation_name="get-user",
        latency_component=LatencyComponent.PROCESSING,
        decomposition_method=DecompositionMethod.WATERFALL,
        latency_trend=LatencyTrend.STABLE,
        total_latency_ms=500.0,
        component_latency_ms=350.0,
        p99_latency_ms=800.0,
        sample_count=100,
    )
    assert isinstance(rec, ServiceLatencyRecord)
    assert rec.service_name == "svc-a"
    assert rec.total_latency_ms == 500.0


def test_process() -> None:
    engine = ServiceLatencyDecompositionEngine()
    rec = engine.add_record(
        service_name="svc-b",
        latency_component=LatencyComponent.NETWORK,
        total_latency_ms=1000.0,
        component_latency_ms=600.0,
        latency_trend=LatencyTrend.DEGRADING,
    )
    result = engine.process(rec.id)
    assert isinstance(result, ServiceLatencyAnalysis)
    assert result.service_name == "svc-b"
    assert result.contribution_pct == 60.0
    assert result.is_hotspot is True


def test_process_not_found() -> None:
    engine = ServiceLatencyDecompositionEngine()
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = ServiceLatencyDecompositionEngine()
    for svc, comp, trend, lat in [
        ("svc-a", LatencyComponent.PROCESSING, LatencyTrend.DEGRADING, 400.0),
        ("svc-b", LatencyComponent.NETWORK, LatencyTrend.STABLE, 200.0),
        ("svc-c", LatencyComponent.QUEUE, LatencyTrend.IMPROVING, 100.0),
        ("svc-d", LatencyComponent.SERIALIZATION, LatencyTrend.VOLATILE, 300.0),
    ]:
        engine.add_record(
            service_name=svc,
            latency_component=comp,
            latency_trend=trend,
            total_latency_ms=lat,
            component_latency_ms=lat * 0.5,
        )
    report = engine.generate_report()
    assert isinstance(report, ServiceLatencyReport)
    assert report.total_records == 4
    assert "processing" in report.by_latency_component


def test_get_stats() -> None:
    engine = ServiceLatencyDecompositionEngine()
    engine.add_record(latency_component=LatencyComponent.PROCESSING, total_latency_ms=100.0)
    engine.add_record(latency_component=LatencyComponent.NETWORK, total_latency_ms=200.0)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "component_distribution" in stats


def test_clear_data() -> None:
    engine = ServiceLatencyDecompositionEngine()
    engine.add_record(service_name="svc-x", total_latency_ms=50.0)
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_decompose_service_latency() -> None:
    engine = ServiceLatencyDecompositionEngine()
    engine.add_record(
        service_name="svc-a",
        latency_component=LatencyComponent.PROCESSING,
        total_latency_ms=400.0,
        component_latency_ms=200.0,
    )
    engine.add_record(
        service_name="svc-a",
        latency_component=LatencyComponent.NETWORK,
        total_latency_ms=400.0,
        component_latency_ms=120.0,
    )
    engine.add_record(
        service_name="svc-b",
        latency_component=LatencyComponent.QUEUE,
        total_latency_ms=100.0,
        component_latency_ms=80.0,
    )
    results = engine.decompose_service_latency()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "component_breakdown_pct" in results[0]


def test_identify_latency_hotspots() -> None:
    engine = ServiceLatencyDecompositionEngine()
    engine.add_record(service_name="svc-hot", total_latency_ms=800.0, component_latency_ms=400.0)
    engine.add_record(service_name="svc-ok", total_latency_ms=100.0, component_latency_ms=50.0)
    engine.add_record(service_name="svc-hot", total_latency_ms=900.0, component_latency_ms=450.0)
    results = engine.identify_latency_hotspots()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "is_hotspot" in results[0]
    assert results[0]["avg_latency_ms"] >= results[-1]["avg_latency_ms"]


def test_forecast_latency_trends() -> None:
    engine = ServiceLatencyDecompositionEngine()
    engine.add_record(
        service_name="svc-a",
        latency_trend=LatencyTrend.DEGRADING,
        p99_latency_ms=900.0,
        total_latency_ms=400.0,
        component_latency_ms=200.0,
    )
    engine.add_record(
        service_name="svc-a",
        latency_trend=LatencyTrend.DEGRADING,
        p99_latency_ms=950.0,
        total_latency_ms=420.0,
        component_latency_ms=210.0,
    )
    engine.add_record(
        service_name="svc-b",
        latency_trend=LatencyTrend.STABLE,
        p99_latency_ms=200.0,
        total_latency_ms=100.0,
        component_latency_ms=50.0,
    )
    results = engine.forecast_latency_trends()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "forecast_risk" in results[0]
    assert "degrading_pct" in results[0]
