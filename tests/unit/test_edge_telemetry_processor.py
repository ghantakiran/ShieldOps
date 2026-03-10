"""Tests for EdgeTelemetryProcessor."""

from __future__ import annotations

from shieldops.observability.edge_telemetry_processor import (
    EdgeNodeType,
    EdgeTelemetryProcessor,
    ProcessingMode,
    TelemetryProtocol,
)


def _engine(**kw) -> EdgeTelemetryProcessor:
    return EdgeTelemetryProcessor(**kw)


class TestEnums:
    def test_edge_node_type(self):
        assert EdgeNodeType.GATEWAY == "gateway"
        assert EdgeNodeType.SENSOR == "sensor"

    def test_telemetry_protocol(self):
        assert TelemetryProtocol.OTLP == "otlp"
        assert TelemetryProtocol.PROMETHEUS == "prometheus"

    def test_processing_mode(self):
        assert ProcessingMode.STREAMING == "streaming"
        assert ProcessingMode.BATCH == "batch"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="edge-1", service="api")
        assert rec.name == "edge-1"
        assert rec.service == "api"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"e-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="edge-1", score=80.0)
        result = eng.process("edge-1")
        assert isinstance(result, dict)
        assert result["key"] == "edge-1"
        assert result["avg_score"] == 80.0

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(name="e1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.add_record(name="e1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(name="e1", service="api")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0


class TestClassifyEdgeSources:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="e1",
            edge_node_type=EdgeNodeType.GATEWAY,
            protocol=TelemetryProtocol.OTLP,
            score=80.0,
        )
        result = eng.classify_edge_sources()
        assert isinstance(result, dict)
        assert "gateway:otlp" in result


class TestComputeLatencyOverhead:
    def test_basic(self):
        eng = _engine()
        eng.add_record(name="e1", latency_ms=50.0)
        result = eng.compute_latency_overhead()
        assert "total_avg_latency_ms" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_latency_overhead()
        assert result["status"] == "no_data"


class TestOptimizeEdgeRouting:
    def test_basic(self):
        eng = _engine()
        eng.add_record(name="e1", service="api", latency_ms=120.0)
        result = eng.optimize_edge_routing()
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "suggestion" in result[0]
