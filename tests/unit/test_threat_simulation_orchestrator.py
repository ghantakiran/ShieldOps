"""Tests for ThreatSimulationOrchestrator."""

from __future__ import annotations

from shieldops.security.threat_simulation_orchestrator import (
    AttackTechnique,
    DefenseEvaluation,
    DefenseResult,
    Simulation,
    SimulationPhase,
    SimulationReport,
    ThreatSimulationOrchestrator,
)


def _engine(**kw) -> ThreatSimulationOrchestrator:
    return ThreatSimulationOrchestrator(**kw)


# --- Enum tests ---


class TestEnums:
    def test_technique_phishing(self):
        assert AttackTechnique.PHISHING == "phishing"

    def test_technique_lateral(self):
        assert AttackTechnique.LATERAL_MOVEMENT == "lateral_movement"

    def test_technique_priv_esc(self):
        assert AttackTechnique.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_technique_exfil(self):
        assert AttackTechnique.DATA_EXFILTRATION == "data_exfiltration"

    def test_technique_c2(self):
        assert AttackTechnique.COMMAND_AND_CONTROL == "command_and_control"

    def test_technique_cred(self):
        assert AttackTechnique.CREDENTIAL_THEFT == "credential_theft"

    def test_phase_planning(self):
        assert SimulationPhase.PLANNING == "planning"

    def test_phase_execution(self):
        assert SimulationPhase.EXECUTION == "execution"

    def test_phase_reporting(self):
        assert SimulationPhase.REPORTING == "reporting"

    def test_result_detected(self):
        assert DefenseResult.DETECTED == "detected"

    def test_result_blocked(self):
        assert DefenseResult.BLOCKED == "blocked"

    def test_result_missed(self):
        assert DefenseResult.MISSED == "missed"

    def test_result_partial(self):
        assert DefenseResult.PARTIALLY_DETECTED == "partially_detected"


# --- Model tests ---


class TestModels:
    def test_simulation_defaults(self):
        s = Simulation()
        assert s.id
        assert s.technique == AttackTechnique.PHISHING
        assert s.phase == SimulationPhase.PLANNING

    def test_evaluation_defaults(self):
        e = DefenseEvaluation()
        assert e.id
        assert e.result == DefenseResult.MISSED
        assert e.gaps == []

    def test_report_defaults(self):
        r = SimulationReport()
        assert r.total_simulations == 0
        assert r.detection_rate == 0.0


# --- plan_simulation ---


class TestPlanSimulation:
    def test_basic(self):
        eng = _engine()
        s = eng.plan_simulation(
            name="phishing-sim",
            technique=AttackTechnique.PHISHING,
            target_service="email",
            team="red-team",
            mitre_id="T1566",
        )
        assert s.name == "phishing-sim"
        assert s.mitre_id == "T1566"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.plan_simulation(name=f"s-{i}")
        assert len(eng._simulations) == 3


# --- execute_attack_scenario ---


class TestExecuteScenario:
    def test_success(self):
        eng = _engine()
        s = eng.plan_simulation(name="test")
        result = eng.execute_attack_scenario(s.id)
        assert result["phase"] == "execution"
        assert s.phase == SimulationPhase.EXECUTION

    def test_not_found(self):
        eng = _engine()
        result = eng.execute_attack_scenario("unknown")
        assert result["error"] == "not_found"


# --- evaluate_defenses ---


class TestEvaluateDefenses:
    def test_detected(self):
        eng = _engine()
        s = eng.plan_simulation(name="test")
        e = eng.evaluate_defenses(
            s.id,
            result=DefenseResult.DETECTED,
            defense_score=90.0,
            control_tested="WAF",
        )
        assert e.result == DefenseResult.DETECTED
        assert e.defense_score == 90.0
        assert s.phase == SimulationPhase.POST_EXPLOITATION

    def test_missed(self):
        eng = _engine()
        s = eng.plan_simulation(name="test")
        e = eng.evaluate_defenses(
            s.id,
            result=DefenseResult.MISSED,
            gaps=["no EDR"],
        )
        assert e.result == DefenseResult.MISSED
        assert len(e.gaps) == 1

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.evaluate_defenses(f"s-{i}", defense_score=50.0)
        assert len(eng._evaluations) == 2


# --- generate_report ---


class TestReport:
    def test_populated(self):
        eng = _engine(defense_threshold=80.0)
        s = eng.plan_simulation(name="test")
        eng.evaluate_defenses(
            s.id,
            result=DefenseResult.MISSED,
            defense_score=30.0,
            gaps=["gap1"],
        )
        report = eng.generate_report()
        assert isinstance(report, SimulationReport)
        assert report.total_simulations == 1
        assert report.total_evaluations == 1
        assert report.detection_rate == 0.0

    def test_high_detection(self):
        eng = _engine()
        s = eng.plan_simulation(name="test")
        eng.evaluate_defenses(s.id, result=DefenseResult.BLOCKED, defense_score=95.0)
        report = eng.generate_report()
        assert report.detection_rate == 100.0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert len(report.recommendations) > 0


# --- track_improvements ---


class TestTrackImprovements:
    def test_improving(self):
        eng = _engine()
        for score in [20.0, 25.0, 80.0, 85.0]:
            eng.evaluate_defenses(f"s-{score}", defense_score=score)
        result = eng.track_improvements()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.evaluate_defenses("s", defense_score=50.0)
        result = eng.track_improvements()
        assert result["trend"] == "stable"

    def test_insufficient(self):
        eng = _engine()
        result = eng.track_improvements()
        assert result["trend"] == "insufficient_data"


# --- list_simulations ---


class TestListSimulations:
    def test_all(self):
        eng = _engine()
        eng.plan_simulation(name="a")
        eng.plan_simulation(name="b")
        assert len(eng.list_simulations()) == 2

    def test_filter_technique(self):
        eng = _engine()
        eng.plan_simulation(name="a", technique=AttackTechnique.PHISHING)
        eng.plan_simulation(name="b", technique=AttackTechnique.LATERAL_MOVEMENT)
        r = eng.list_simulations(technique=AttackTechnique.PHISHING)
        assert len(r) == 1

    def test_filter_team(self):
        eng = _engine()
        eng.plan_simulation(name="a", team="red")
        eng.plan_simulation(name="b", team="blue")
        assert len(eng.list_simulations(team="red")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.plan_simulation(name=f"s-{i}")
        assert len(eng.list_simulations(limit=5)) == 5


# --- stats / clear ---


class TestStatsAndClear:
    def test_stats(self):
        eng = _engine()
        eng.plan_simulation(name="a", target_service="s", team="t")
        stats = eng.get_stats()
        assert stats["total_simulations"] == 1

    def test_clear(self):
        eng = _engine()
        eng.plan_simulation(name="test")
        eng.evaluate_defenses("s1", defense_score=50.0)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._simulations) == 0
        assert len(eng._evaluations) == 0
