"""Tests for shieldops.observability.telemetry_schema_registry — TelemetrySchemaRegistry."""

from __future__ import annotations

from shieldops.observability.telemetry_schema_registry import (
    CompatibilityMode,
    FieldStatus,
    MigrationStatus,
    SchemaRecord,
    SchemaType,
    TelemetrySchemaRegistry,
)


def _engine(**kw) -> TelemetrySchemaRegistry:
    return TelemetrySchemaRegistry(**kw)


class TestEnums:
    def test_schema_type(self):
        assert SchemaType.METRIC == "metric"

    def test_compatibility(self):
        assert CompatibilityMode.BACKWARD == "backward"

    def test_field_status(self):
        assert FieldStatus.ACTIVE == "active"

    def test_migration_status(self):
        assert MigrationStatus.PLANNED == "planned"


class TestModels:
    def test_record_defaults(self):
        r = SchemaRecord()
        assert r.id
        assert r.created_at > 0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(schema_name="http_requests", version="1.0")
        assert rec.schema_name == "http_requests"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(schema_name=f"schema-{i}", version="1.0")
        assert len(eng._records) == 3


class TestCompatibilityValidation:
    def test_basic(self):
        eng = _engine()
        eng.add_record(schema_name="http_requests", version="1.0")
        result = eng.validate_compatibility("http_requests")
        assert isinstance(result, dict)


class TestMigrationPlanning:
    def test_basic(self):
        eng = _engine()
        eng.add_record(schema_name="http_requests", version="1.0")
        result = eng.plan_migration("http_requests")
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(schema_name="http_requests", version="1.0", service="api")
        result = eng.process("http_requests")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(schema_name="http_requests", version="1.0")
        report = eng.generate_report()
        assert report.total_schemas >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_schemas == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(schema_name="http_requests", version="1.0")
        stats = eng.get_stats()
        assert stats["total_schemas"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(schema_name="http_requests", version="1.0")
        eng.clear_data()
        assert eng.get_stats()["total_schemas"] == 0
