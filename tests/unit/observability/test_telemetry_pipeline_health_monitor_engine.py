"""Tests for TelemetryPipelineHealthMonitorEngine."""

from __future__ import annotations

from shieldops.observability.telemetry_pipeline_health_monitor_engine import (
    HealthStatus,
    IssueType,
    PipelineStage,
    TelemetryPipelineAnalysis,
    TelemetryPipelineHealthMonitorEngine,
    TelemetryPipelineRecord,
    TelemetryPipelineReport,
)


def test_add_record() -> None:
    engine = TelemetryPipelineHealthMonitorEngine()
    rec = engine.add_record(
        pipeline_id="pipe-1",
        stage_name="collector-1",
        pipeline_stage=PipelineStage.COLLECTION,
        health_status=HealthStatus.HEALTHY,
        issue_type=IssueType.LATENCY,
        throughput_eps=10000.0,
        drop_rate=0.001,
        latency_ms=5.0,
        queue_depth=100,
        capacity_pct=40.0,
    )
    assert isinstance(rec, TelemetryPipelineRecord)
    assert rec.pipeline_id == "pipe-1"
    assert rec.throughput_eps == 10000.0


def test_process() -> None:
    engine = TelemetryPipelineHealthMonitorEngine()
    rec = engine.add_record(
        pipeline_id="pipe-2",
        stage_name="exporter-1",
        pipeline_stage=PipelineStage.EXPORT,
        health_status=HealthStatus.DEGRADED,
        drop_rate=0.1,
        capacity_pct=90.0,
    )
    result = engine.process(rec.id)
    assert isinstance(result, TelemetryPipelineAnalysis)
    assert result.pipeline_id == "pipe-2"
    assert result.is_bottleneck is True
    assert result.health_score < 100.0


def test_process_not_found() -> None:
    engine = TelemetryPipelineHealthMonitorEngine()
    result = engine.process("missing-pipeline")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = TelemetryPipelineHealthMonitorEngine()
    for pid, stage, sname, health, issue, throughput in [
        ("p1", PipelineStage.COLLECTION, "col-1", HealthStatus.HEALTHY, IssueType.LATENCY, 5000.0),
        (
            "p2",
            PipelineStage.PROCESSING,
            "proc-1",
            HealthStatus.DEGRADED,
            IssueType.BACKPRESSURE,
            3000.0,
        ),
        ("p3", PipelineStage.EXPORT, "exp-1", HealthStatus.UNHEALTHY, IssueType.DATA_LOSS, 1000.0),
        (
            "p4",
            PipelineStage.STORAGE,
            "stor-1",
            HealthStatus.UNKNOWN,
            IssueType.CONFIGURATION,
            8000.0,
        ),
    ]:
        engine.add_record(
            pipeline_id=pid,
            pipeline_stage=stage,
            stage_name=sname,
            health_status=health,
            issue_type=issue,
            throughput_eps=throughput,
        )
    report = engine.generate_report()
    assert isinstance(report, TelemetryPipelineReport)
    assert report.total_records == 4
    assert "collection" in report.by_pipeline_stage


def test_get_stats() -> None:
    engine = TelemetryPipelineHealthMonitorEngine()
    engine.add_record(pipeline_stage=PipelineStage.COLLECTION, throughput_eps=1000.0)
    engine.add_record(pipeline_stage=PipelineStage.EXPORT, throughput_eps=800.0)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "stage_distribution" in stats


def test_clear_data() -> None:
    engine = TelemetryPipelineHealthMonitorEngine()
    engine.add_record(pipeline_id="p-x", throughput_eps=500.0)
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_evaluate_pipeline_health() -> None:
    engine = TelemetryPipelineHealthMonitorEngine()
    engine.add_record(
        pipeline_stage=PipelineStage.COLLECTION,
        health_status=HealthStatus.HEALTHY,
        throughput_eps=5000.0,
        drop_rate=0.001,
        capacity_pct=30.0,
    )
    engine.add_record(
        pipeline_stage=PipelineStage.EXPORT,
        health_status=HealthStatus.UNHEALTHY,
        throughput_eps=500.0,
        drop_rate=0.15,
        capacity_pct=95.0,
    )
    engine.add_record(
        pipeline_stage=PipelineStage.COLLECTION,
        health_status=HealthStatus.DEGRADED,
        throughput_eps=3000.0,
        drop_rate=0.05,
        capacity_pct=70.0,
    )
    results = engine.evaluate_pipeline_health()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "unhealthy_pct" in results[0]
    assert "avg_throughput_eps" in results[0]


def test_detect_pipeline_bottlenecks() -> None:
    engine = TelemetryPipelineHealthMonitorEngine()
    engine.add_record(
        stage_name="exporter-critical",
        pipeline_stage=PipelineStage.EXPORT,
        capacity_pct=95.0,
        drop_rate=0.08,
        throughput_eps=500.0,
    )
    engine.add_record(
        stage_name="collector-ok",
        pipeline_stage=PipelineStage.COLLECTION,
        capacity_pct=40.0,
        drop_rate=0.001,
        throughput_eps=10000.0,
    )
    engine.add_record(
        stage_name="exporter-critical",
        pipeline_stage=PipelineStage.EXPORT,
        capacity_pct=92.0,
        drop_rate=0.07,
        throughput_eps=600.0,
    )
    results = engine.detect_pipeline_bottlenecks()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "is_bottleneck" in results[0]
    assert results[0]["avg_capacity_pct"] >= results[-1]["avg_capacity_pct"]


def test_forecast_pipeline_capacity() -> None:
    engine = TelemetryPipelineHealthMonitorEngine()
    engine.add_record(
        pipeline_stage=PipelineStage.STORAGE,
        capacity_pct=60.0,
        throughput_eps=8000.0,
    )
    engine.add_record(
        pipeline_stage=PipelineStage.STORAGE,
        capacity_pct=70.0,
        throughput_eps=9000.0,
    )
    engine.add_record(
        pipeline_stage=PipelineStage.PROCESSING,
        capacity_pct=30.0,
        throughput_eps=4000.0,
    )
    results = engine.forecast_pipeline_capacity()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "forecast_10_samples" in results[0]
    assert "capacity_risk" in results[0]
