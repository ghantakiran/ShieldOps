"""Tests for ComplianceViolationPredictor."""

from __future__ import annotations

from shieldops.security.compliance_violation_predictor import (
    ComplianceFramework,
    ComplianceViolationPredictor,
    ControlGap,
    ViolationLikelihood,
)


def _engine(**kw) -> ComplianceViolationPredictor:
    return ComplianceViolationPredictor(**kw)


class TestEnums:
    def test_fw_soc2(self):
        assert ComplianceFramework.SOC2 == "soc2"

    def test_fw_hipaa(self):
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_fw_pci(self):
        assert ComplianceFramework.PCI_DSS == "pci_dss"

    def test_fw_gdpr(self):
        assert ComplianceFramework.GDPR == "gdpr"

    def test_likelihood_certain(self):
        assert ViolationLikelihood.CERTAIN == "certain"

    def test_likelihood_likely(self):
        assert ViolationLikelihood.LIKELY == "likely"

    def test_likelihood_possible(self):
        assert ViolationLikelihood.POSSIBLE == "possible"

    def test_likelihood_unlikely(self):
        assert ViolationLikelihood.UNLIKELY == "unlikely"

    def test_gap_missing(self):
        assert ControlGap.MISSING == "missing"

    def test_gap_weak(self):
        assert ControlGap.WEAK == "weak"

    def test_gap_partial(self):
        assert ControlGap.PARTIAL == "partial"

    def test_gap_strong(self):
        assert ControlGap.STRONG == "strong"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            control_id="c1",
            framework=ComplianceFramework.SOC2,
            risk_score=80.0,
        )
        assert r.control_id == "c1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(control_id=f"c-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(
            control_id="c1",
            risk_score=90.0,
            likelihood=ViolationLikelihood.LIKELY,
        )
        a = eng.process(r.id)
        assert a is not None
        assert a.control_id == "c1"

    def test_missing_key(self):
        assert _engine().process("x") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(control_id="c1")
        assert eng.generate_report().total_records == 1

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


class TestPredictViolationRisk:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            control_id="c1",
            framework=ComplianceFramework.HIPAA,
            risk_score=85.0,
        )
        result = eng.predict_violation_risk()
        assert len(result) == 1
        assert result[0]["framework"] == "hipaa"

    def test_empty(self):
        assert _engine().predict_violation_risk() == []


class TestIdentifyControlWeaknesses:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            control_id="c1",
            gap=ControlGap.MISSING,
            risk_score=90.0,
        )
        result = eng.identify_control_weaknesses()
        assert len(result) == 1
        assert result[0]["gap"] == "missing"

    def test_strong_excluded(self):
        eng = _engine()
        eng.add_record(control_id="c1", gap=ControlGap.STRONG)
        assert eng.identify_control_weaknesses() == []


class TestRecommendPreventiveActions:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            control_id="c1",
            gap=ControlGap.WEAK,
            risk_score=60.0,
        )
        result = eng.recommend_preventive_actions()
        assert result["total_actions"] > 0

    def test_empty(self):
        result = _engine().recommend_preventive_actions()
        assert result["total_actions"] == 0
