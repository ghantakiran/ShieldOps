"""Tests for RiskComplianceBridge."""

from __future__ import annotations

from shieldops.compliance.risk_compliance_bridge import (
    ComplianceFramework,
    ComplianceImpact,
    RiskComplianceBridge,
    RiskToControlMapping,
)


def _engine(**kw) -> RiskComplianceBridge:
    return RiskComplianceBridge(**kw)


class TestEnums:
    def test_compliance_framework_values(self):
        for v in ComplianceFramework:
            assert isinstance(v.value, str)

    def test_risk_to_control_mapping_values(self):
        for v in RiskToControlMapping:
            assert isinstance(v.value, str)

    def test_compliance_impact_values(self):
        for v in ComplianceImpact:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(risk_id="r1")
        assert r.risk_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(risk_id=f"r-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(risk_id="r1")
        a = eng.process(r.id)
        assert hasattr(a, "risk_id")
        assert a.risk_id == "r1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(risk_id="r1")
        assert eng.generate_report().total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(risk_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(risk_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestMapRiskToControls:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(risk_id="r1", control_id="ctrl-1")
        result = eng.map_risk_to_controls()
        assert len(result) == 1
        assert result[0]["risk_id"] == "r1"

    def test_empty(self):
        assert _engine().map_risk_to_controls() == []


class TestComputeComplianceRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(risk_id="r1", risk_score=50.0)
        result = eng.compute_compliance_risk_score()
        assert result["overall_score"] == 50.0

    def test_empty(self):
        result = _engine().compute_compliance_risk_score()
        assert result["overall_score"] == 0.0


class TestDetectUnmappedRisks:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            risk_id="r1",
            mapping=RiskToControlMapping.UNMAPPED,
            risk_score=75.0,
        )
        result = eng.detect_unmapped_risks()
        assert len(result) == 1
        assert result[0]["risk_id"] == "r1"

    def test_empty(self):
        assert _engine().detect_unmapped_risks() == []
