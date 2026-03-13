"""Tests for TerraformPlanImpactAnalyzer."""

from __future__ import annotations

from shieldops.changes.terraform_plan_impact_analyzer import (
    ChangeAction,
    ImpactLevel,
    ResourceCategory,
    TerraformPlanImpactAnalyzer,
)


def _engine(**kw) -> TerraformPlanImpactAnalyzer:
    return TerraformPlanImpactAnalyzer(**kw)


class TestEnums:
    def test_change_action_values(self):
        for v in ChangeAction:
            assert isinstance(v.value, str)

    def test_impact_level_values(self):
        for v in ImpactLevel:
            assert isinstance(v.value, str)

    def test_resource_category_values(self):
        for v in ResourceCategory:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(plan_id="p1")
        assert r.plan_id == "p1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(plan_id=f"p-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(plan_id="p1", risk_score=50.0)
        a = eng.process(r.id)
        assert hasattr(a, "plan_id")
        assert a.plan_id == "p1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(plan_id="p1")
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
        eng.record_item(plan_id="p1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(plan_id="p1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputePlanBlastRadius:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(plan_id="p1", affected_resources=5)
        result = eng.compute_plan_blast_radius()
        assert len(result) == 1
        assert result[0]["blast_radius"] == 5

    def test_empty(self):
        r = _engine().compute_plan_blast_radius()
        assert r == []


class TestDetectDestructiveChanges:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            plan_id="p1",
            change_action=ChangeAction.DELETE,
            risk_score=90.0,
        )
        result = eng.detect_destructive_changes()
        assert len(result) == 1
        assert result[0]["action"] == "delete"

    def test_empty(self):
        r = _engine().detect_destructive_changes()
        assert r == []


class TestRankPlansByRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(plan_id="p1", risk_score=50.0)
        eng.record_item(plan_id="p2", risk_score=80.0)
        result = eng.rank_plans_by_risk_score()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_plans_by_risk_score()
        assert r == []
