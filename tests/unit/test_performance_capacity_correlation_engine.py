"""Tests for PerformanceCapacityCorrelationEngine."""

from __future__ import annotations

from shieldops.analytics.performance_capacity_correlation_engine import (
    CapacityMetric,
    CorrelationStrength,
    PerformanceCapacityCorrelationEngine,
    PerformanceMetric,
)


def _engine(**kw) -> PerformanceCapacityCorrelationEngine:
    return PerformanceCapacityCorrelationEngine(**kw)


class TestEnums:
    def test_correlation_strength_values(self):
        for v in CorrelationStrength:
            assert isinstance(v.value, str)

    def test_capacity_metric_values(self):
        for v in CapacityMetric:
            assert isinstance(v.value, str)

    def test_performance_metric_values(self):
        for v in PerformanceMetric:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(resource_id="r1")
        assert r.resource_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(resource_id=f"r-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.add_record(
            resource_id="r1",
            correlation_strength=CorrelationStrength.STRONG,
            capacity_metric=CapacityMetric.MEMORY_PRESSURE,
            performance_metric=PerformanceMetric.THROUGHPUT,
            correlation_coefficient=0.92,
        )
        assert r.correlation_coefficient == 0.92


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(resource_id="r1", correlation_coefficient=0.85)
        a = eng.process(r.id)
        assert hasattr(a, "resource_id")
        assert a.resource_id == "r1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_capacity_driven(self):
        eng = _engine()
        r = eng.add_record(
            resource_id="r1",
            correlation_strength=CorrelationStrength.STRONG,
        )
        a = eng.process(r.id)
        assert a.capacity_driven is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(resource_id="r1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(resource_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(resource_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeCapacityPerformanceCorrelation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(resource_id="r1", correlation_coefficient=0.85)
        result = eng.compute_capacity_performance_correlation()
        assert len(result) == 1
        assert result[0]["resource_id"] == "r1"

    def test_empty(self):
        assert _engine().compute_capacity_performance_correlation() == []


class TestDetectCapacityDrivenDegradation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            resource_id="r1",
            correlation_strength=CorrelationStrength.STRONG,
            correlation_coefficient=0.95,
        )
        result = eng.detect_capacity_driven_degradation()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_capacity_driven_degradation() == []


class TestRankResourcesByPerformanceSensitivity:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(resource_id="r1", correlation_coefficient=0.85)
        eng.add_record(resource_id="r2", correlation_coefficient=0.45)
        result = eng.rank_resources_by_performance_sensitivity()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_resources_by_performance_sensitivity() == []
