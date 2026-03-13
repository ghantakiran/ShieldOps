"""Tests for OtelServiceGraphEngine."""

from __future__ import annotations

from shieldops.topology.otel_service_graph_engine import (
    EdgeType,
    GraphFreshness,
    GraphSource,
    OtelServiceGraphEngine,
)


def _engine(**kw) -> OtelServiceGraphEngine:
    return OtelServiceGraphEngine(**kw)


class TestEnums:
    def test_graph_source_values(self):
        for v in GraphSource:
            assert isinstance(v.value, str)

    def test_edge_type_values(self):
        for v in EdgeType:
            assert isinstance(v.value, str)

    def test_graph_freshness_values(self):
        for v in GraphFreshness:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic_add(self):
        eng = _engine()
        r = eng.record_item(name="test-001", score=80.0)
        assert r.name == "test-001"
        assert r.score == 80.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test", score=40.0)
        result = eng.process(r.id)
        assert result["status"] == "processed"

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        report = eng.generate_report()
        assert report.total_records > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated_count(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.clear_data()
        assert len(eng._records) == 0


class TestBuildServiceGraph:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            name="a",
            graph_source=GraphSource.TRACE_SPANS,
            score=90.0,
        )
        result = eng.build_service_graph()
        assert "trace_spans" in result

    def test_empty(self):
        eng = _engine()
        assert eng.build_service_graph() == {}


class TestDetectUndiscoveredEdges:
    def test_with_data(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=30.0)
        result = eng.detect_undiscovered_edges()
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_undiscovered_edges() == []


class TestComputeGraphCompleteness:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="a", service="svc-a", score=30.0)
        result = eng.compute_graph_completeness()
        assert len(result) > 0

    def test_empty(self):
        eng = _engine()
        assert eng.compute_graph_completeness() == []
