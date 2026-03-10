"""Tests for ObservabilityDependencyMapper."""

from __future__ import annotations

from shieldops.observability.observability_dependency_mapper import (
    DependencyDirection,
    HealthImpact,
    ObservabilityDependencyMapper,
    SignalType,
)


def _engine(**kw) -> ObservabilityDependencyMapper:
    return ObservabilityDependencyMapper(**kw)


class TestEnums:
    def test_signal_type(self):
        assert SignalType.METRIC == "metric"
        assert SignalType.EVENT == "event"

    def test_dependency_direction(self):
        assert DependencyDirection.UPSTREAM == "upstream"
        assert DependencyDirection.BIDIRECTIONAL == "bidirectional"

    def test_health_impact(self):
        assert HealthImpact.BLOCKING == "blocking"
        assert HealthImpact.INFORMATIONAL == "informational"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="d-1", service="api")
        assert rec.name == "d-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"d-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="d-1", score=55.0)
        result = eng.process("d-1")
        assert result["key"] == "d-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(name="d1", service="api")
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
        eng.add_record(name="d1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(name="d1", service="api")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestMapSignalDependencies:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="d1",
            source_service="api",
            target_service="db",
            service="api",
        )
        result = eng.map_signal_dependencies()
        assert "nodes" in result
        assert "edges" in result

    def test_empty(self):
        eng = _engine()
        result = eng.map_signal_dependencies()
        assert result["status"] == "no_data"


class TestDetectOrphanedSignals:
    def test_basic(self):
        eng = _engine()
        eng.add_record(name="d1", service="orphan-svc")
        result = eng.detect_orphaned_signals()
        assert isinstance(result, list)


class TestComputeDependencyRisk:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="d1",
            service="api",
            health_impact=HealthImpact.BLOCKING,
        )
        result = eng.compute_dependency_risk()
        assert isinstance(result, dict)
        assert "api" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_dependency_risk()
        assert result["status"] == "no_data"
