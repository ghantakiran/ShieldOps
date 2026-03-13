"""Tests for ComplianceAutomationGapAnalyzer."""

from __future__ import annotations

from shieldops.compliance.compliance_automation_gap_analyzer import (
    AutomationLevel,
    ComplianceAutomationGapAnalyzer,
    GapType,
    RoiCategory,
)


def _engine(**kw) -> ComplianceAutomationGapAnalyzer:
    return ComplianceAutomationGapAnalyzer(**kw)


class TestEnums:
    def test_automation_level_values(self):
        for v in AutomationLevel:
            assert isinstance(v.value, str)

    def test_gap_type_values(self):
        for v in GapType:
            assert isinstance(v.value, str)

    def test_roi_category_values(self):
        for v in RoiCategory:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(control_id="c1")
        assert r.control_id == "c1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(control_id=f"c-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(control_id="c1", automation_potential=80.0, manual_hours=20.0)
        a = eng.process(r.id)
        assert hasattr(a, "control_id")
        assert a.control_id == "c1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(control_id="c1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(control_id="c1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(control_id="c1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeAutomationPotential:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(control_id="c1", automation_potential=75.0)
        result = eng.compute_automation_potential()
        assert len(result) == 1
        assert result[0]["control_id"] == "c1"

    def test_empty(self):
        assert _engine().compute_automation_potential() == []


class TestDetectManualBottlenecks:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            control_id="c1",
            automation_level=AutomationLevel.MANUAL,
            manual_hours=40.0,
        )
        result = eng.detect_manual_bottlenecks()
        assert len(result) == 1
        assert result[0]["control_id"] == "c1"

    def test_empty(self):
        assert _engine().detect_manual_bottlenecks() == []


class TestRankControlsByAutomationRoi:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(control_id="c1", manual_hours=10.0, estimated_savings=500.0)
        eng.add_record(control_id="c2", manual_hours=20.0, estimated_savings=200.0)
        result = eng.rank_controls_by_automation_roi()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_controls_by_automation_roi() == []
