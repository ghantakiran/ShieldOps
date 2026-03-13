"""Tests for EventSchemaRegistryIntelligence."""

from __future__ import annotations

from shieldops.observability.event_schema_registry_intelligence import (
    CompatibilityMode,
    EventSchemaRegistryIntelligence,
    EvolutionRisk,
    SchemaFormat,
)


def _engine(**kw) -> EventSchemaRegistryIntelligence:
    return EventSchemaRegistryIntelligence(**kw)


class TestEnums:
    def test_schema_format_values(self):
        for v in SchemaFormat:
            assert isinstance(v.value, str)

    def test_compatibility_mode_values(self):
        for v in CompatibilityMode:
            assert isinstance(v.value, str)

    def test_evolution_risk_values(self):
        for v in EvolutionRisk:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(schema_id="s1")
        assert r.schema_id == "s1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(schema_id=f"s-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().add_record()
        assert r.schema_format == SchemaFormat.AVRO
        assert r.version == 1


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(schema_id="s1", version=3)
        a = eng.process(r.id)
        assert hasattr(a, "schema_id")
        assert a.schema_id == "s1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(schema_id="s1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_high_risk_schemas(self):
        eng = _engine()
        eng.add_record(
            schema_id="s1",
            evolution_risk=EvolutionRisk.BREAKING,
        )
        rpt = eng.generate_report()
        assert len(rpt.high_risk_schemas) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(schema_id="s1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(schema_id="s1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestDetectSchemaConflicts:
    def test_with_conflicts(self):
        eng = _engine()
        eng.add_record(schema_id="s1", version=1)
        eng.add_record(schema_id="s1", version=2)
        result = eng.detect_schema_conflicts()
        assert len(result) == 1
        assert result[0]["version_count"] == 2

    def test_empty(self):
        assert _engine().detect_schema_conflicts() == []


class TestComputeSchemaEvolutionVelocity:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(schema_id="s1", version=1)
        eng.add_record(schema_id="s1", version=5)
        result = eng.compute_schema_evolution_velocity()
        assert len(result) == 1
        assert result[0]["velocity"] == 4

    def test_empty(self):
        r = _engine().compute_schema_evolution_velocity()
        assert r == []


class TestRankSchemasByCompatibilityRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            schema_id="s1",
            evolution_risk=EvolutionRisk.BREAKING,
        )
        eng.add_record(
            schema_id="s2",
            evolution_risk=EvolutionRisk.SAFE,
        )
        result = eng.rank_schemas_by_compatibility_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_schemas_by_compatibility_risk()
        assert r == []
