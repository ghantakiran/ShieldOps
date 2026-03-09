"""Tests for TelemetryPipelineOrchestrator."""

from __future__ import annotations

from shieldops.observability.telemetry_pipeline_orchestrator import (
    BackpressureEvent,
    BackpressureLevel,
    PipelineConfig,
    PipelineHealth,
    PipelineReport,
    PipelineStage,
    TelemetryPipelineOrchestrator,
)


def _engine(**kw) -> TelemetryPipelineOrchestrator:
    return TelemetryPipelineOrchestrator(**kw)


class TestEnums:
    def test_stage_collection(self):
        assert PipelineStage.COLLECTION == "collection"

    def test_stage_processing(self):
        assert PipelineStage.PROCESSING == "processing"

    def test_stage_routing(self):
        assert PipelineStage.ROUTING == "routing"

    def test_stage_storage(self):
        assert PipelineStage.STORAGE == "storage"

    def test_stage_export(self):
        assert PipelineStage.EXPORT == "export"

    def test_health_healthy(self):
        assert PipelineHealth.HEALTHY == "healthy"

    def test_health_degraded(self):
        assert PipelineHealth.DEGRADED == "degraded"

    def test_health_critical(self):
        assert PipelineHealth.CRITICAL == "critical"

    def test_bp_none(self):
        assert BackpressureLevel.NONE == "none"

    def test_bp_low(self):
        assert BackpressureLevel.LOW == "low"

    def test_bp_critical(self):
        assert BackpressureLevel.CRITICAL == "critical"


class TestModels:
    def test_config_defaults(self):
        c = PipelineConfig()
        assert c.id
        assert c.stage == PipelineStage.COLLECTION
        assert c.health == PipelineHealth.UNKNOWN
        assert c.enabled is True

    def test_backpressure_defaults(self):
        b = BackpressureEvent()
        assert b.id
        assert b.level == BackpressureLevel.NONE

    def test_report_defaults(self):
        r = PipelineReport()
        assert r.total_pipelines == 0
        assert r.recommendations == []


class TestConfigurePipeline:
    def test_basic(self):
        eng = _engine()
        p = eng.configure_pipeline("otel-collector", stage=PipelineStage.COLLECTION)
        assert p.name == "otel-collector"
        assert p.health == PipelineHealth.HEALTHY

    def test_custom_throughput(self):
        eng = _engine()
        p = eng.configure_pipeline("high-tp", max_throughput_eps=50000.0)
        assert p.max_throughput_eps == 50000.0

    def test_eviction(self):
        eng = _engine(max_pipelines=3)
        for i in range(5):
            eng.configure_pipeline(f"p-{i}")
        assert len(eng._pipelines) == 3


class TestValidatePipeline:
    def test_not_found(self):
        eng = _engine()
        result = eng.validate_pipeline("nonexistent")
        assert result["valid"] is False

    def test_valid(self):
        eng = _engine()
        eng.configure_pipeline("otel")
        result = eng.validate_pipeline("otel")
        assert result["valid"] is True

    def test_high_drop_rate(self):
        eng = _engine()
        p = eng.configure_pipeline("lossy")
        p.drop_rate_pct = 15.0
        result = eng.validate_pipeline("lossy")
        assert result["valid"] is False


class TestUpdateThroughput:
    def test_not_found(self):
        eng = _engine()
        result = eng.update_throughput("nonexistent", 1000)
        assert result["status"] == "not_found"

    def test_healthy(self):
        eng = _engine()
        eng.configure_pipeline("otel", max_throughput_eps=10000)
        result = eng.update_throughput("otel", 3000)
        assert result["health"] == "healthy"

    def test_degraded(self):
        eng = _engine()
        eng.configure_pipeline("otel", max_throughput_eps=10000)
        result = eng.update_throughput("otel", 7500)
        assert result["health"] == "degraded"

    def test_critical(self):
        eng = _engine()
        eng.configure_pipeline("otel", max_throughput_eps=10000)
        result = eng.update_throughput("otel", 9500)
        assert result["health"] == "critical"

    def test_critical_drop_rate(self):
        eng = _engine()
        eng.configure_pipeline("otel", max_throughput_eps=10000)
        result = eng.update_throughput("otel", 1000, drop_rate_pct=6.0)
        assert result["health"] == "critical"


class TestOptimizeThroughput:
    def test_no_suggestions(self):
        eng = _engine()
        result = eng.optimize_throughput()
        assert result[0]["type"] == "none"

    def test_scale_up(self):
        eng = _engine()
        p = eng.configure_pipeline("otel", max_throughput_eps=10000)
        p.throughput_eps = 9000
        result = eng.optimize_throughput()
        assert any(s["type"] == "scale_up" for s in result)

    def test_scale_down(self):
        eng = _engine()
        p = eng.configure_pipeline("otel", max_throughput_eps=10000)
        p.throughput_eps = 500
        result = eng.optimize_throughput()
        assert any(s["type"] == "scale_down" for s in result)


class TestMonitorBackpressure:
    def test_none(self):
        eng = _engine()
        event = eng.monitor_backpressure("otel", 50, max_queue=10000)
        assert event.level == BackpressureLevel.NONE

    def test_low(self):
        eng = _engine()
        event = eng.monitor_backpressure("otel", 2000, max_queue=10000)
        assert event.level == BackpressureLevel.LOW

    def test_medium(self):
        eng = _engine()
        event = eng.monitor_backpressure("otel", 5000, max_queue=10000)
        assert event.level == BackpressureLevel.MEDIUM

    def test_high(self):
        eng = _engine()
        event = eng.monitor_backpressure("otel", 8000, max_queue=10000)
        assert event.level == BackpressureLevel.HIGH

    def test_critical(self):
        eng = _engine()
        event = eng.monitor_backpressure("otel", 9500, max_queue=10000)
        assert event.level == BackpressureLevel.CRITICAL


class TestGetPipelineHealth:
    def test_empty(self):
        eng = _engine()
        result = eng.get_pipeline_health()
        assert result["overall"] == "unknown"

    def test_healthy(self):
        eng = _engine()
        eng.configure_pipeline("otel")
        result = eng.get_pipeline_health()
        assert result["overall"] == "healthy"

    def test_critical(self):
        eng = _engine()
        p = eng.configure_pipeline("otel")
        p.health = PipelineHealth.CRITICAL
        result = eng.get_pipeline_health()
        assert result["overall"] == "critical"


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_pipelines == 0

    def test_populated(self):
        eng = _engine()
        eng.configure_pipeline("otel")
        report = eng.generate_report()
        assert report.total_pipelines == 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.configure_pipeline("otel")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._pipelines) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_pipelines"] == 0

    def test_populated(self):
        eng = _engine()
        eng.configure_pipeline("otel")
        stats = eng.get_stats()
        assert stats["enabled_pipelines"] == 1
