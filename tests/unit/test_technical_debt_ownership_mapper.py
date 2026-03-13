"""Tests for TechnicalDebtOwnershipMapper."""

from __future__ import annotations

from shieldops.analytics.technical_debt_ownership_mapper import (
    DebtAge,
    DebtType,
    OwnershipStatus,
    TechnicalDebtOwnershipMapper,
)


def _engine(**kw) -> TechnicalDebtOwnershipMapper:
    return TechnicalDebtOwnershipMapper(**kw)


class TestEnums:
    def test_debt_type_values(self):
        for v in DebtType:
            assert isinstance(v.value, str)

    def test_ownership_status_values(self):
        for v in OwnershipStatus:
            assert isinstance(v.value, str)

    def test_debt_age_values(self):
        for v in DebtAge:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(debt_id="d1")
        assert r.debt_id == "d1"

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            debt_id="d1",
            team_id="t1",
            severity_score=80.0,
            estimated_hours=40.0,
        )
        assert r.severity_score == 80.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(debt_id=f"d-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(debt_id="d1", team_id="t1")
        a = eng.process(r.id)
        assert hasattr(a, "team_id")
        assert a.team_id == "t1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(debt_id="d1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(debt_id="d1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(debt_id="d1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestMapDebtToOwners:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(debt_id="d1", team_id="t1")
        eng.add_record(debt_id="d2", team_id="t1")
        result = eng.map_debt_to_owners()
        assert len(result) == 1
        assert result[0]["debt_count"] == 2

    def test_empty(self):
        assert _engine().map_debt_to_owners() == []


class TestDetectOrphanedDebt:
    def test_with_orphaned(self):
        eng = _engine()
        eng.add_record(
            debt_id="d1",
            ownership=OwnershipStatus.ORPHANED,
            severity_score=90.0,
        )
        result = eng.detect_orphaned_debt()
        assert len(result) == 1
        assert result[0]["debt_id"] == "d1"

    def test_empty(self):
        r = _engine().detect_orphaned_debt()
        assert r == []


class TestRankTeamsByDebtBurden:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            debt_id="d1",
            team_id="t1",
            severity_score=80.0,
            estimated_hours=10.0,
        )
        eng.add_record(
            debt_id="d2",
            team_id="t2",
            severity_score=40.0,
            estimated_hours=5.0,
        )
        result = eng.rank_teams_by_debt_burden()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        eng = _engine()
        r = eng.rank_teams_by_debt_burden()
        assert r == []
