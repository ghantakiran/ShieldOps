"""Tests for AdversaryEmulationEngine."""

from __future__ import annotations

from shieldops.security.adversary_emulation_engine import (
    AdversaryEmulationEngine,
    EmulationFramework,
    EmulationOutcome,
    EmulationPhase,
)


def _engine(**kw) -> AdversaryEmulationEngine:
    return AdversaryEmulationEngine(**kw)


class TestEnums:
    def test_fw_mitre(self):
        assert EmulationFramework.MITRE_ATTACK == "mitre_attack"

    def test_fw_ckc(self):
        assert EmulationFramework.CYBER_KILL_CHAIN == "cyber_kill_chain"

    def test_fw_diamond(self):
        assert EmulationFramework.DIAMOND_MODEL == "diamond_model"

    def test_fw_custom(self):
        assert EmulationFramework.CUSTOM == "custom"

    def test_phase_recon(self):
        assert EmulationPhase.RECON == "recon"

    def test_phase_weaponize(self):
        assert EmulationPhase.WEAPONIZE == "weaponize"

    def test_phase_deliver(self):
        assert EmulationPhase.DELIVER == "deliver"

    def test_phase_exploit(self):
        assert EmulationPhase.EXPLOIT == "exploit"

    def test_phase_install(self):
        assert EmulationPhase.INSTALL == "install"

    def test_phase_command(self):
        assert EmulationPhase.COMMAND == "command"

    def test_phase_actions(self):
        assert EmulationPhase.ACTIONS == "actions"

    def test_outcome_detected(self):
        assert EmulationOutcome.DETECTED == "detected"

    def test_outcome_blocked(self):
        assert EmulationOutcome.BLOCKED == "blocked"

    def test_outcome_evaded(self):
        assert EmulationOutcome.EVADED == "evaded"

    def test_outcome_partial(self):
        assert EmulationOutcome.PARTIAL == "partial"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            emulation_id="e1",
            framework=EmulationFramework.MITRE_ATTACK,
            detection_rate=0.9,
        )
        assert r.emulation_id == "e1"
        assert r.detection_rate == 0.9

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(emulation_id=f"e-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(emulation_id="e1", detection_rate=0.85)
        a = eng.process(r.id)
        assert a is not None
        assert a.emulation_id == "e1"

    def test_missing_key(self):
        assert _engine().process("missing") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(emulation_id="e1")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(emulation_id="e1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(emulation_id="e1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGenerateEmulationPlan:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            emulation_id="e1",
            phase=EmulationPhase.RECON,
        )
        result = eng.generate_emulation_plan()
        assert len(result) == 1
        assert result[0]["phase"] == "recon"

    def test_empty(self):
        assert _engine().generate_emulation_plan() == []


class TestEvaluateDetectionCoverage:
    def test_basic(self):
        eng = _engine()
        eng.add_record(emulation_id="e1", detection_rate=0.9)
        result = eng.evaluate_detection_coverage()
        assert result["overall_coverage"] == 0.9

    def test_empty(self):
        result = _engine().evaluate_detection_coverage()
        assert result["overall_coverage"] == 0.0


class TestScoreDefenseReadiness:
    def test_basic(self):
        eng = _engine()
        eng.add_record(emulation_id="e1", readiness_score=85.0)
        result = eng.score_defense_readiness()
        assert result["overall_readiness"] == 85.0

    def test_empty(self):
        result = _engine().score_defense_readiness()
        assert result["overall_readiness"] == 0.0
