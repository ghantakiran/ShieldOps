"""Tests for shieldops.security.posture_simulator."""

from __future__ import annotations

from shieldops.security.posture_simulator import (
    AttackScenario,
    PostureLevel,
    PostureSimulatorReport,
    SecurityPostureSimulator,
    SimulationRecord,
    SimulationResult,
    SimulationScenario,
)


def _engine(**kw) -> SecurityPostureSimulator:
    return SecurityPostureSimulator(**kw)


# ---------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------


class TestEnums:
    # AttackScenario (5)
    def test_attack_lateral_movement(self):
        assert AttackScenario.LATERAL_MOVEMENT == "lateral_movement"

    def test_attack_privilege_escalation(self):
        assert AttackScenario.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_attack_data_exfiltration(self):
        assert AttackScenario.DATA_EXFILTRATION == "data_exfiltration"

    def test_attack_supply_chain(self):
        assert AttackScenario.SUPPLY_CHAIN == "supply_chain"

    def test_attack_insider_threat(self):
        assert AttackScenario.INSIDER_THREAT == "insider_threat"

    # SimulationResult (5)
    def test_result_blocked(self):
        assert SimulationResult.BLOCKED == "blocked"

    def test_result_detected(self):
        assert SimulationResult.DETECTED == "detected"

    def test_result_partially_detected(self):
        assert SimulationResult.PARTIALLY_DETECTED == "partially_detected"

    def test_result_undetected(self):
        assert SimulationResult.UNDETECTED == "undetected"

    def test_result_bypassed(self):
        assert SimulationResult.BYPASSED == "bypassed"

    # PostureLevel (5)
    def test_posture_hardened(self):
        assert PostureLevel.HARDENED == "hardened"

    def test_posture_strong(self):
        assert PostureLevel.STRONG == "strong"

    def test_posture_adequate(self):
        assert PostureLevel.ADEQUATE == "adequate"

    def test_posture_weak(self):
        assert PostureLevel.WEAK == "weak"

    def test_posture_vulnerable(self):
        assert PostureLevel.VULNERABLE == "vulnerable"


# ---------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------


class TestModels:
    def test_simulation_record_defaults(self):
        r = SimulationRecord()
        assert r.id
        assert r.scenario_name == ""
        assert r.attack == AttackScenario.LATERAL_MOVEMENT
        assert r.result == SimulationResult.BLOCKED
        assert r.posture == PostureLevel.ADEQUATE
        assert r.risk_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_simulation_scenario_defaults(self):
        r = SimulationScenario()
        assert r.id
        assert r.scenario_name == ""
        assert r.attack == AttackScenario.LATERAL_MOVEMENT
        assert r.posture == PostureLevel.ADEQUATE
        assert r.complexity_score == 5.0
        assert r.auto_remediate is False
        assert r.created_at > 0

    def test_report_defaults(self):
        r = PostureSimulatorReport()
        assert r.total_simulations == 0
        assert r.total_scenarios == 0
        assert r.blocked_rate_pct == 0.0
        assert r.by_attack == {}
        assert r.by_result == {}
        assert r.bypassed_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------
# record_simulation
# ---------------------------------------------------------------


class TestRecordSimulation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_simulation(
            "scn-a",
            attack=AttackScenario.LATERAL_MOVEMENT,
            result=SimulationResult.BLOCKED,
        )
        assert r.scenario_name == "scn-a"
        assert r.attack == AttackScenario.LATERAL_MOVEMENT

    def test_with_posture(self):
        eng = _engine()
        r = eng.record_simulation(
            "scn-b",
            posture=PostureLevel.HARDENED,
        )
        assert r.posture == PostureLevel.HARDENED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_simulation(f"scn-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------
# get_simulation
# ---------------------------------------------------------------


class TestGetSimulation:
    def test_found(self):
        eng = _engine()
        r = eng.record_simulation("scn-a")
        assert eng.get_simulation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_simulation("nonexistent") is None


# ---------------------------------------------------------------
# list_simulations
# ---------------------------------------------------------------


class TestListSimulations:
    def test_list_all(self):
        eng = _engine()
        eng.record_simulation("scn-a")
        eng.record_simulation("scn-b")
        assert len(eng.list_simulations()) == 2

    def test_filter_by_scenario(self):
        eng = _engine()
        eng.record_simulation("scn-a")
        eng.record_simulation("scn-b")
        results = eng.list_simulations(scenario_name="scn-a")
        assert len(results) == 1

    def test_filter_by_attack(self):
        eng = _engine()
        eng.record_simulation(
            "scn-a",
            attack=AttackScenario.SUPPLY_CHAIN,
        )
        eng.record_simulation(
            "scn-b",
            attack=AttackScenario.INSIDER_THREAT,
        )
        results = eng.list_simulations(attack=AttackScenario.SUPPLY_CHAIN)
        assert len(results) == 1


# ---------------------------------------------------------------
# add_scenario
# ---------------------------------------------------------------


class TestAddScenario:
    def test_basic(self):
        eng = _engine()
        s = eng.add_scenario(
            "lateral-test",
            attack=AttackScenario.LATERAL_MOVEMENT,
            posture=PostureLevel.HARDENED,
            complexity_score=8.0,
            auto_remediate=True,
        )
        assert s.scenario_name == "lateral-test"
        assert s.auto_remediate is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_scenario(f"scn-{i}")
        assert len(eng._scenarios) == 2


# ---------------------------------------------------------------
# analyze_posture_strength
# ---------------------------------------------------------------


class TestAnalyzePostureStrength:
    def test_with_data(self):
        eng = _engine()
        eng.record_simulation(
            "scn-a",
            result=SimulationResult.BLOCKED,
        )
        eng.record_simulation(
            "scn-a",
            result=SimulationResult.BYPASSED,
        )
        result = eng.analyze_posture_strength("scn-a")
        assert result["scenario_name"] == "scn-a"
        assert result["simulation_count"] == 2
        assert result["blocked_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_posture_strength("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_blocked_rate_pct=50.0)
        eng.record_simulation(
            "scn-a",
            result=SimulationResult.BLOCKED,
        )
        result = eng.analyze_posture_strength("scn-a")
        assert result["meets_threshold"] is True


# ---------------------------------------------------------------
# identify_bypassed_defenses
# ---------------------------------------------------------------


class TestIdentifyBypassedDefenses:
    def test_with_bypassed(self):
        eng = _engine()
        eng.record_simulation(
            "scn-a",
            result=SimulationResult.BYPASSED,
        )
        eng.record_simulation(
            "scn-a",
            result=SimulationResult.UNDETECTED,
        )
        eng.record_simulation(
            "scn-b",
            result=SimulationResult.BLOCKED,
        )
        results = eng.identify_bypassed_defenses()
        assert len(results) == 1
        assert results[0]["scenario_name"] == "scn-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_bypassed_defenses() == []


# ---------------------------------------------------------------
# rank_by_risk_score
# ---------------------------------------------------------------


class TestRankByRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_simulation("scn-a", risk_score=90.0)
        eng.record_simulation("scn-a", risk_score=80.0)
        eng.record_simulation("scn-b", risk_score=50.0)
        results = eng.rank_by_risk_score()
        assert results[0]["scenario_name"] == "scn-a"
        assert results[0]["avg_risk_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# ---------------------------------------------------------------
# detect_posture_weaknesses
# ---------------------------------------------------------------


class TestDetectPostureWeaknesses:
    def test_with_weaknesses(self):
        eng = _engine()
        for _ in range(5):
            eng.record_simulation(
                "scn-a",
                result=SimulationResult.DETECTED,
            )
        eng.record_simulation(
            "scn-b",
            result=SimulationResult.BLOCKED,
        )
        results = eng.detect_posture_weaknesses()
        assert len(results) == 1
        assert results[0]["scenario_name"] == "scn-a"
        assert results[0]["weakness_detected"] is True

    def test_no_weaknesses(self):
        eng = _engine()
        eng.record_simulation(
            "scn-a",
            result=SimulationResult.DETECTED,
        )
        assert eng.detect_posture_weaknesses() == []


# ---------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_simulation(
            "scn-a",
            result=SimulationResult.BLOCKED,
        )
        eng.record_simulation(
            "scn-b",
            result=SimulationResult.BYPASSED,
        )
        eng.record_simulation(
            "scn-b",
            result=SimulationResult.BYPASSED,
        )
        eng.add_scenario("scn-1")
        report = eng.generate_report()
        assert report.total_simulations == 3
        assert report.total_scenarios == 1
        assert report.by_attack != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_simulations == 0
        assert "below" in report.recommendations[0]


# ---------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_simulation("scn-a")
        eng.add_scenario("scn-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._scenarios) == 0


# ---------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_simulations"] == 0
        assert stats["total_scenarios"] == 0
        assert stats["attack_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_simulation(
            "scn-a",
            attack=AttackScenario.LATERAL_MOVEMENT,
        )
        eng.record_simulation(
            "scn-b",
            attack=AttackScenario.SUPPLY_CHAIN,
        )
        eng.add_scenario("s1")
        stats = eng.get_stats()
        assert stats["total_simulations"] == 2
        assert stats["total_scenarios"] == 1
        assert stats["unique_scenarios"] == 2
