"""Tests for InfrastructureBlueprintIntelligence."""

from __future__ import annotations

from shieldops.changes.infrastructure_blueprint_intelligence import (
    AdoptionLevel,
    BlueprintStatus,
    BlueprintType,
    InfrastructureBlueprintIntelligence,
)


def _engine(
    **kw,
) -> InfrastructureBlueprintIntelligence:
    return InfrastructureBlueprintIntelligence(**kw)


class TestEnums:
    def test_blueprint_status_values(self):
        for v in BlueprintStatus:
            assert isinstance(v.value, str)

    def test_adoption_level_values(self):
        for v in AdoptionLevel:
            assert isinstance(v.value, str)

    def test_blueprint_type_values(self):
        for v in BlueprintType:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(blueprint_id="b1")
        assert r.blueprint_id == "b1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(blueprint_id=f"b-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            blueprint_id="b1",
            adoption_count=10,
            drift_score=5.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "blueprint_id")
        assert a.has_drift is False

    def test_with_drift(self):
        eng = _engine()
        r = eng.record_item(
            blueprint_id="b1",
            drift_score=30.0,
        )
        a = eng.process(r.id)
        assert a.has_drift is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(blueprint_id="b1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(blueprint_id="b1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(blueprint_id="b1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAnalyzeBlueprintAdoption:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            blueprint_id="b1",
            adoption_count=15,
        )
        result = eng.analyze_blueprint_adoption()
        assert len(result) == 1
        assert result[0]["total_adoption"] == 15

    def test_empty(self):
        r = _engine().analyze_blueprint_adoption()
        assert r == []


class TestDetectBlueprintDrift:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            blueprint_id="b1",
            drift_score=50.0,
        )
        result = eng.detect_blueprint_drift()
        assert len(result) == 1
        assert result[0]["drift_score"] == 50.0

    def test_empty(self):
        r = _engine().detect_blueprint_drift()
        assert r == []


class TestRankBlueprintsByReuseValue:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            blueprint_id="b1",
            adoption_count=10,
            drift_score=5.0,
        )
        eng.record_item(
            blueprint_id="b2",
            adoption_count=20,
            drift_score=10.0,
        )
        result = eng.rank_blueprints_by_reuse_value()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_blueprints_by_reuse_value()
        assert r == []
