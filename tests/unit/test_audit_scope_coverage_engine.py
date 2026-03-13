"""Tests for AuditScopeCoverageEngine."""

from __future__ import annotations

from shieldops.audit.audit_scope_coverage_engine import (
    AuditScopeCoverageEngine,
    AuditType,
    CoverageLevel,
    ScopeArea,
)


def _engine(**kw) -> AuditScopeCoverageEngine:
    return AuditScopeCoverageEngine(**kw)


class TestEnums:
    def test_coverage_level_values(self):
        for v in CoverageLevel:
            assert isinstance(v.value, str)

    def test_audit_type_values(self):
        for v in AuditType:
            assert isinstance(v.value, str)

    def test_scope_area_values(self):
        for v in ScopeArea:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(audit_id="a1")
        assert r.audit_id == "a1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(audit_id=f"a-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            audit_id="a1", coverage_ratio=85.0, total_controls=20, tested_controls=17
        )
        a = eng.process(r.id)
        assert hasattr(a, "audit_id")
        assert a.audit_id == "a1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(audit_id="a1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(audit_id="a1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(audit_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeScopeCoverageRatio:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(audit_id="a1", total_controls=20, tested_controls=15)
        result = eng.compute_scope_coverage_ratio()
        assert len(result) == 1
        assert result[0]["audit_id"] == "a1"

    def test_empty(self):
        assert _engine().compute_scope_coverage_ratio() == []


class TestDetectUntestedControls:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(control_id="c1", tested_controls=0, total_controls=10)
        result = eng.detect_untested_controls()
        assert len(result) == 1
        assert result[0]["control_id"] == "c1"

    def test_empty(self):
        assert _engine().detect_untested_controls() == []


class TestRankAuditCyclesByThoroughness:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(audit_id="a1", total_controls=20, tested_controls=18)
        eng.add_record(audit_id="a2", total_controls=20, tested_controls=10)
        result = eng.rank_audit_cycles_by_thoroughness()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_audit_cycles_by_thoroughness() == []
