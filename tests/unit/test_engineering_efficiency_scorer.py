"""Tests for EngineeringEfficiencyScorer."""

from __future__ import annotations

from shieldops.analytics.engineering_efficiency_scorer import (
    DrainType,
    EfficiencyDimension,
    EfficiencyGrade,
    EngineeringEfficiencyScorer,
)


def _engine(**kw) -> EngineeringEfficiencyScorer:
    return EngineeringEfficiencyScorer(**kw)


class TestEnums:
    def test_efficiency_dimension_values(self):
        for v in EfficiencyDimension:
            assert isinstance(v.value, str)

    def test_drain_type_values(self):
        for v in DrainType:
            assert isinstance(v.value, str)

    def test_efficiency_grade_values(self):
        for v in EfficiencyGrade:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(workflow_id="w1")
        assert r.workflow_id == "w1"

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            workflow_id="w1",
            efficiency_score=85.0,
            time_spent_hours=4.0,
        )
        assert r.efficiency_score == 85.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(workflow_id=f"w-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            workflow_id="w1",
            efficiency_score=80.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "workflow_id")
        assert a.workflow_id == "w1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(workflow_id="w1")
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
        eng.add_record(workflow_id="w1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(workflow_id="w1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeEfficiencyIndex:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            workflow_id="w1",
            efficiency_score=80.0,
        )
        result = eng.compute_efficiency_index()
        assert len(result) == 1
        assert result[0]["efficiency_index"] == 80.0

    def test_empty(self):
        assert _engine().compute_efficiency_index() == []


class TestDetectEfficiencyDrains:
    def test_with_drains(self):
        eng = _engine()
        eng.add_record(
            workflow_id="w1",
            grade=EfficiencyGrade.POOR,
            drain_type=DrainType.TOOLING,
            time_spent_hours=10.0,
        )
        result = eng.detect_efficiency_drains()
        assert len(result) == 1
        assert result[0]["total_hours"] == 10.0

    def test_empty(self):
        r = _engine().detect_efficiency_drains()
        assert r == []


class TestRankWorkflowsByOptimizationPotential:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            workflow_id="w1",
            efficiency_score=60.0,
            time_spent_hours=10.0,
        )
        eng.add_record(
            workflow_id="w2",
            efficiency_score=90.0,
            time_spent_hours=10.0,
        )
        result = eng.rank_workflows_by_optimization_potential()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        eng = _engine()
        r = eng.rank_workflows_by_optimization_potential()
        assert r == []
