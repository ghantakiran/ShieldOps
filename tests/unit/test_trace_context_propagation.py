"""Tests for TraceContextPropagation."""

from __future__ import annotations

from shieldops.observability.trace_context_propagation import (
    PropagationFormat,
    PropagationIssue,
    ServiceBoundary,
    TraceContextPropagation,
)


def _engine(**kw) -> TraceContextPropagation:
    return TraceContextPropagation(**kw)


class TestEnums:
    def test_propagation_format_values(self):
        for v in PropagationFormat:
            assert isinstance(v.value, str)

    def test_propagation_issue_values(self):
        for v in PropagationIssue:
            assert isinstance(v.value, str)

    def test_service_boundary_values(self):
        for v in ServiceBoundary:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(name="test-001", score=80.0)
        assert r.name == "test-001"
        assert r.score == 80.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(name=f"item-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(name="test", score=40.0)
        result = eng.process(r.id)
        assert result["status"] == "processed"

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=50.0)
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
        eng.add_record(name="a")
        eng.add_record(name="b")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(name="a")
        eng.clear_data()
        assert len(eng._records) == 0


class TestDetectPropagationBreaks:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            propagation_issue=(PropagationIssue.CONTEXT_LOST),
        )
        result = eng.detect_propagation_breaks()
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_propagation_breaks() == []


class TestComputeContextCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            propagation_format=PropagationFormat.W3C,
            score=90.0,
        )
        result = eng.compute_context_coverage()
        assert "w3c" in result

    def test_empty(self):
        eng = _engine()
        assert eng.compute_context_coverage() == {}


class TestRecommendPropagationFixes:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(name="a", service="svc-a", score=30.0)
        result = eng.recommend_propagation_fixes()
        assert len(result) > 0

    def test_empty(self):
        eng = _engine()
        assert eng.recommend_propagation_fixes() == []
