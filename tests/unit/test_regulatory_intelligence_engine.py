"""Tests for shieldops.compliance.regulatory_intelligence_engine — RegulatoryIntelligenceEngine."""

from __future__ import annotations

from shieldops.compliance.regulatory_intelligence_engine import (
    ChangeImpact,
    ComplianceGapStatus,
    RegulationType,
    RegulatoryIntelligenceEngine,
)


def _engine(**kw) -> RegulatoryIntelligenceEngine:
    return RegulatoryIntelligenceEngine(**kw)


class TestEnums:
    def test_regulation_type(self):
        assert RegulationType.GDPR == "gdpr"

    def test_change_impact(self):
        assert ChangeImpact.HIGH == "high"

    def test_gap_status(self):
        assert ComplianceGapStatus.OPEN == "open"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(regulation_name="GDPR Art. 17", regulation_type=RegulationType.GDPR)
        assert rec.regulation_name == "GDPR Art. 17"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(regulation_name=f"reg-{i}")
        assert len(eng._records) == 3


class TestImpactAssessment:
    def test_basic(self):
        eng = _engine()
        eng.add_record(regulation_name="GDPR", change_impact=ChangeImpact.HIGH)
        result = eng.assess_impact()
        assert isinstance(result, (dict, list))


class TestComplianceGaps:
    def test_basic(self):
        eng = _engine()
        eng.add_record(regulation_name="GDPR", gap_status=ComplianceGapStatus.OPEN)
        result = eng.detect_compliance_gaps()
        assert isinstance(result, list)


class TestRequirementMapping:
    def test_basic(self):
        eng = _engine()
        eng.add_record(regulation_name="GDPR", regulation_type=RegulationType.GDPR)
        result = eng.map_requirements()
        assert isinstance(result, dict)


class TestApproachingDeadlines:
    def test_basic(self):
        eng = _engine()
        eng.add_record(regulation_name="GDPR", days_until_deadline=15)
        result = eng.identify_approaching_deadlines()
        assert isinstance(result, list)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(regulation_name="GDPR", service="compliance")
        result = eng.process("compliance")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(regulation_name="GDPR")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(regulation_name="GDPR")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(regulation_name="GDPR")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
