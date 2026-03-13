"""Tests for MitreRiskMapperEngine."""

from __future__ import annotations

from shieldops.security.mitre_risk_mapper_engine import (
    AttackPhase,
    MappingConfidence,
    MitreRiskMapperEngine,
    TacticCoverage,
)


def _engine(**kw) -> MitreRiskMapperEngine:
    return MitreRiskMapperEngine(**kw)


class TestEnums:
    def test_attack_phase_values(self):
        for v in AttackPhase:
            assert isinstance(v.value, str)

    def test_tactic_coverage_values(self):
        for v in TacticCoverage:
            assert isinstance(v.value, str)

    def test_mapping_confidence_values(self):
        for v in MappingConfidence:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(detection_id="d1")
        assert r.detection_id == "d1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(detection_id=f"d-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            detection_id="d1",
            technique_id="T1059",
        )
        a = eng.process(r.id)
        assert hasattr(a, "detection_id")
        assert a.detection_id == "d1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(detection_id="d1")
        assert eng.generate_report().total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(detection_id="d1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(detection_id="d1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestMapDetectionToTechnique:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            detection_id="d1",
            technique_id="T1059",
        )
        result = eng.map_detection_to_technique()
        assert len(result) == 1
        assert result[0]["detection_id"] == "d1"

    def test_empty(self):
        assert _engine().map_detection_to_technique() == []


class TestComputeTacticCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            detection_id="d1",
            attack_phase=AttackPhase.EXECUTION,
            coverage=TacticCoverage.FULL,
        )
        result = eng.compute_tactic_coverage()
        assert result["overall_coverage"] > 0

    def test_empty(self):
        result = _engine().compute_tactic_coverage()
        assert result["overall_coverage"] == 0.0


class TestIdentifyDetectionGaps:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            detection_id="d1",
            attack_phase=AttackPhase.EXECUTION,
        )
        result = eng.identify_detection_gaps()
        assert len(result) >= 1

    def test_empty(self):
        result = _engine().identify_detection_gaps()
        assert len(result) == 4
