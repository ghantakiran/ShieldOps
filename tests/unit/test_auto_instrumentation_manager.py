"""Tests for AutoInstrumentationManager."""

from __future__ import annotations

from shieldops.observability.auto_instrumentation_manager import (
    AutoInstrumentationManager,
    CoverageLevel,
    InstrumentationMethod,
    InstrumentationTarget,
)


def _engine(**kw) -> AutoInstrumentationManager:
    return AutoInstrumentationManager(**kw)


class TestEnums:
    def test_instrumentation_target_values(self):
        for v in InstrumentationTarget:
            assert isinstance(v.value, str)

    def test_instrumentation_method_values(self):
        for v in InstrumentationMethod:
            assert isinstance(v.value, str)

    def test_coverage_level_values(self):
        for v in CoverageLevel:
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


class TestComputeInstrumentationCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            instrumentation_target=(InstrumentationTarget.PYTHON),
            score=90.0,
        )
        result = eng.compute_instrumentation_coverage()
        assert "python" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_instrumentation_coverage()
        assert result == {}


class TestDetectMissingInstrumentors:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            coverage_level=CoverageLevel.NONE,
        )
        result = eng.detect_missing_instrumentors()
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        result = eng.detect_missing_instrumentors()
        assert result == []


class TestRecommendInstrumentationPlan:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(name="a", service="svc-a", score=30.0)
        result = eng.recommend_instrumentation_plan()
        assert len(result) > 0

    def test_empty(self):
        eng = _engine()
        result = eng.recommend_instrumentation_plan()
        assert result == []
