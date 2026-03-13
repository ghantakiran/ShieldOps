"""Tests for ReliabilityImprovementTracker."""

from __future__ import annotations

from shieldops.sla.reliability_improvement_tracker import (
    ImpactLevel,
    ImprovementType,
    InitiativeStatus,
    ReliabilityImprovementTracker,
)


def _engine(**kw) -> ReliabilityImprovementTracker:
    return ReliabilityImprovementTracker(**kw)


class TestEnums:
    def test_initiative_status_values(self):
        for v in InitiativeStatus:
            assert isinstance(v.value, str)

    def test_improvement_type_values(self):
        for v in ImprovementType:
            assert isinstance(v.value, str)

    def test_impact_level_values(self):
        for v in ImpactLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(initiative_id="i1")
        assert r.initiative_id == "i1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(initiative_id=f"i-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.add_record(
            initiative_id="i1",
            initiative_status=InitiativeStatus.COMPLETED,
            improvement_type=ImprovementType.ARCHITECTURE,
            impact_level=ImpactLevel.TRANSFORMATIVE,
            reliability_before=95.0,
            reliability_after=99.5,
            effort_hours=100.0,
        )
        assert r.reliability_after == 99.5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            initiative_id="i1",
            reliability_before=95.0,
            reliability_after=99.0,
            effort_hours=50.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "initiative_id")
        assert a.initiative_id == "i1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_stalled_detected(self):
        eng = _engine()
        r = eng.add_record(
            initiative_id="i1",
            initiative_status=InitiativeStatus.STALLED,
        )
        a = eng.process(r.id)
        assert a.stalled is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(initiative_id="i1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(initiative_id="i1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(initiative_id="i1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeImprovementEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            initiative_id="i1",
            reliability_before=95.0,
            reliability_after=99.0,
            effort_hours=50.0,
        )
        result = eng.compute_improvement_effectiveness()
        assert len(result) == 1
        assert result[0]["initiative_id"] == "i1"

    def test_empty(self):
        assert _engine().compute_improvement_effectiveness() == []


class TestDetectStalledInitiatives:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            initiative_id="i1",
            initiative_status=InitiativeStatus.STALLED,
            effort_hours=80.0,
        )
        result = eng.detect_stalled_initiatives()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_stalled_initiatives() == []


class TestRankInitiativesByReliabilityGain:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            initiative_id="i1",
            reliability_before=95.0,
            reliability_after=99.0,
        )
        eng.add_record(
            initiative_id="i2",
            reliability_before=90.0,
            reliability_after=99.5,
        )
        result = eng.rank_initiatives_by_reliability_gain()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_initiatives_by_reliability_gain() == []
