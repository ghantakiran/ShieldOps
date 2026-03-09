"""Tests for shieldops.changes.iac_validation_engine — IacValidationEngine."""

from __future__ import annotations

from shieldops.changes.iac_validation_engine import (
    BlastRadiusLevel,
    IacToolType,
    IacValidationEngine,
    IacValidationRecord,
    ValidationResult,
)


def _engine(**kw) -> IacValidationEngine:
    return IacValidationEngine(**kw)


class TestEnums:
    def test_tool_terraform(self):
        assert IacToolType.TERRAFORM == "terraform"

    def test_validation_passed(self):
        assert ValidationResult.PASSED == "passed"

    def test_blast_radius(self):
        assert BlastRadiusLevel.HIGH == "high"


class TestModels:
    def test_record_defaults(self):
        r = IacValidationRecord()
        assert r.id
        assert r.created_at > 0


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(name="vpc-update", tool_type=IacToolType.TERRAFORM)
        assert rec.name == "vpc-update"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"plan-{i}")
        assert len(eng._records) == 3


class TestBlastRadius:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="plan-1")
        result = eng.calculate_blast_radius()
        assert isinstance(result, (dict, list))


class TestCostImpact:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="plan-1", estimated_cost_delta=500.0)
        result = eng.estimate_cost_impact()
        assert isinstance(result, dict)


class TestPolicyViolations:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="plan-1", validation_result=ValidationResult.FAILED)
        result = eng.identify_policy_violations()
        assert isinstance(result, list)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="plan-1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="plan-1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="plan-1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
