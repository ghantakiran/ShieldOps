"""Tests for InfrastructureDriftIntelligenceV2."""

from __future__ import annotations

from shieldops.changes.infrastructure_drift_intelligence import (
    DriftCategory,
    DriftRootCause,
    InfrastructureDriftIntelligenceV2,
    RemediationAction,
)


def _engine(**kw) -> InfrastructureDriftIntelligenceV2:
    return InfrastructureDriftIntelligenceV2(**kw)


class TestEnums:
    def test_drift_category(self):
        assert DriftCategory.CONFIGURATION == "configuration"

    def test_root_cause(self):
        assert DriftRootCause.MANUAL_CHANGE == "manual_change"

    def test_remediation_action(self):
        assert RemediationAction.AUTO_REVERT == "auto_revert"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(name="sg-drift", category=DriftCategory.CONFIGURATION)
        assert rec.name == "sg-drift"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"drift-{i}")
        assert len(eng._records) == 3


class TestClassifyRootCauses:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="d1", root_cause=DriftRootCause.MANUAL_CHANGE)
        result = eng.classify_root_causes()
        assert isinstance(result, dict)


class TestComplianceImpact:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="d1", compliance_impact=True)
        result = eng.assess_compliance_impact()
        assert isinstance(result, (dict, list))


class TestAutoRemediation:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="d1", remediation_action=RemediationAction.AUTO_REVERT)
        result = eng.plan_auto_remediation()
        assert isinstance(result, list)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="d1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="d1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="d1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
