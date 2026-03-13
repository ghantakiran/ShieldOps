"""Tests for IntelligentWasteClassifier."""

from __future__ import annotations

from shieldops.billing.intelligent_waste_classifier import (
    ConfidenceLevel,
    IntelligentWasteClassifier,
    RemediationComplexity,
    WasteCategory,
)


def _engine(**kw) -> IntelligentWasteClassifier:
    return IntelligentWasteClassifier(**kw)


class TestEnums:
    def test_waste_category_values(self):
        for v in WasteCategory:
            assert isinstance(v.value, str)

    def test_remediation_complexity_values(self):
        for v in RemediationComplexity:
            assert isinstance(v.value, str)

    def test_confidence_level_values(self):
        for v in ConfidenceLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(resource_id="res1")
        assert r.resource_id == "res1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(resource_id=f"r-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            resource_id="res1",
            monthly_waste=100,
            remediation_complexity=RemediationComplexity.TRIVIAL,
        )
        a = eng.process(r.id)
        assert a.recovery_value == 1200.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_complex_multiplier(self):
        eng = _engine()
        r = eng.add_record(
            monthly_waste=100,
            remediation_complexity=RemediationComplexity.COMPLEX,
        )
        a = eng.process(r.id)
        assert a.recovery_value == 720.0


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(monthly_waste=500)
        rpt = eng.generate_report()
        assert rpt.total_monthly_waste == 500.0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_waste_recommendation(self):
        eng = _engine()
        eng.add_record(monthly_waste=100)
        rpt = eng.generate_report()
        assert any("recoverable" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(resource_id="res1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestClassifyWasteCategory:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            waste_category=WasteCategory.ORPHANED,
            monthly_waste=200,
        )
        result = eng.classify_waste_category()
        assert len(result) == 1
        assert result[0]["category"] == "orphaned"

    def test_empty(self):
        assert _engine().classify_waste_category() == []


class TestEstimateWasteRecoveryValue:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(resource_id="r1", monthly_waste=100)
        result = eng.estimate_waste_recovery_value()
        assert result[0]["annual_recovery"] == 1200.0

    def test_empty(self):
        assert _engine().estimate_waste_recovery_value() == []


class TestPrioritizeWasteRemediation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            resource_id="r1",
            monthly_waste=100,
            remediation_complexity=RemediationComplexity.TRIVIAL,
        )
        result = eng.prioritize_waste_remediation()
        assert len(result) == 1
        assert result[0]["priority_score"] == 400.0

    def test_empty(self):
        assert _engine().prioritize_waste_remediation() == []
