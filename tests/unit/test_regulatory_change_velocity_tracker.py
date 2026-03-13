"""Tests for RegulatoryChangeVelocityTracker."""

from __future__ import annotations

from shieldops.compliance.regulatory_change_velocity_tracker import (
    ChangeImpact,
    ChangeType,
    Jurisdiction,
    RegulatoryChangeVelocityTracker,
)


def _engine(**kw) -> RegulatoryChangeVelocityTracker:
    return RegulatoryChangeVelocityTracker(**kw)


class TestEnums:
    def test_change_impact_values(self):
        for v in ChangeImpact:
            assert isinstance(v.value, str)

    def test_jurisdiction_values(self):
        for v in Jurisdiction:
            assert isinstance(v.value, str)

    def test_change_type_values(self):
        for v in ChangeType:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(regulation_id="reg1")
        assert r.regulation_id == "reg1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(regulation_id=f"reg-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(regulation_id="reg1", velocity_score=5.0)
        a = eng.process(r.id)
        assert hasattr(a, "regulation_id")
        assert a.regulation_id == "reg1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(regulation_id="reg1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(regulation_id="reg1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(regulation_id="reg1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeChangeVelocityByJurisdiction:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(regulation_id="reg1", velocity_score=3.0)
        result = eng.compute_change_velocity_by_jurisdiction()
        assert len(result) == 1
        assert result[0]["jurisdiction"] == "us_federal"

    def test_empty(self):
        assert _engine().compute_change_velocity_by_jurisdiction() == []


class TestDetectHighImpactChanges:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            regulation_id="reg1",
            change_impact=ChangeImpact.CRITICAL,
            affected_controls=10,
        )
        result = eng.detect_high_impact_changes()
        assert len(result) == 1
        assert result[0]["regulation_id"] == "reg1"

    def test_empty(self):
        assert _engine().detect_high_impact_changes() == []


class TestRankRegulationsByChangeFrequency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(regulation_id="reg1")
        eng.add_record(regulation_id="reg2")
        result = eng.rank_regulations_by_change_frequency()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_regulations_by_change_frequency() == []
