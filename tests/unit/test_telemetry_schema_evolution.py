"""Tests for TelemetrySchemaEvolution."""

from __future__ import annotations

from shieldops.observability.telemetry_schema_evolution import (
    CompatibilityLevel,
    MigrationStatus,
    SchemaChange,
    TelemetrySchemaEvolution,
)


def _engine(**kw) -> TelemetrySchemaEvolution:
    return TelemetrySchemaEvolution(**kw)


class TestEnums:
    def test_schema_change_values(self):
        for v in SchemaChange:
            assert isinstance(v.value, str)

    def test_compatibility_level_values(self):
        for v in CompatibilityLevel:
            assert isinstance(v.value, str)

    def test_migration_status_values(self):
        for v in MigrationStatus:
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


class TestDetectSchemaDrift:
    def test_with_data(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=30.0)
        result = eng.detect_schema_drift()
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_schema_drift() == []


class TestComputeCompatibilityScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            compatibility_level=(CompatibilityLevel.BACKWARD),
            score=90.0,
        )
        result = eng.compute_compatibility_score()
        assert "backward" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_compatibility_score()
        assert result == {}


class TestGenerateMigrationPlan:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(name="a", service="svc-a", score=30.0)
        result = eng.generate_migration_plan()
        assert len(result) > 0

    def test_empty(self):
        eng = _engine()
        assert eng.generate_migration_plan() == []
