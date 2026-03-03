"""Tests for shieldops.compliance.policy_impact_simulator — PolicyImpactSimulator."""

from __future__ import annotations

from shieldops.compliance.policy_impact_simulator import (
    ImpactCategory,
    PolicyImpactSimulator,
    SimulationAnalysis,
    SimulationRecord,
    SimulationReport,
    SimulationResult,
    SimulationType,
)


def _engine(**kw) -> PolicyImpactSimulator:
    return PolicyImpactSimulator(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert SimulationType.WHAT_IF == "what_if"

    def test_e1_v2(self):
        assert SimulationType.ROLLBACK == "rollback"

    def test_e1_v3(self):
        assert SimulationType.GRADUAL_ROLLOUT == "gradual_rollout"

    def test_e1_v4(self):
        assert SimulationType.A_B_TEST == "a_b_test"

    def test_e1_v5(self):
        assert SimulationType.FULL_DEPLOYMENT == "full_deployment"

    def test_e2_v1(self):
        assert ImpactCategory.ACCESS_RESTRICTION == "access_restriction"

    def test_e2_v2(self):
        assert ImpactCategory.WORKFLOW_CHANGE == "workflow_change"

    def test_e2_v3(self):
        assert ImpactCategory.COMPLIANCE_EFFECT == "compliance_effect"

    def test_e2_v4(self):
        assert ImpactCategory.COST_IMPACT == "cost_impact"

    def test_e2_v5(self):
        assert ImpactCategory.USER_EXPERIENCE == "user_experience"

    def test_e3_v1(self):
        assert SimulationResult.LOW_IMPACT == "low_impact"

    def test_e3_v2(self):
        assert SimulationResult.MODERATE == "moderate"

    def test_e3_v3(self):
        assert SimulationResult.HIGH_IMPACT == "high_impact"

    def test_e3_v4(self):
        assert SimulationResult.BREAKING == "breaking"

    def test_e3_v5(self):
        assert SimulationResult.UNKNOWN == "unknown"


class TestModels:
    def test_rec(self):
        r = SimulationRecord()
        assert r.id and r.impact_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = SimulationAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = SimulationReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_simulation(
            simulation_id="t",
            simulation_type=SimulationType.ROLLBACK,
            impact_category=ImpactCategory.WORKFLOW_CHANGE,
            simulation_result=SimulationResult.MODERATE,
            impact_score=92.0,
            service="s",
            team="t",
        )
        assert r.simulation_id == "t" and r.impact_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_simulation(simulation_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_simulation(simulation_id="t")
        assert eng.get_simulation(r.id) is not None

    def test_not_found(self):
        assert _engine().get_simulation("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_simulation(simulation_id="a")
        eng.record_simulation(simulation_id="b")
        assert len(eng.list_simulations()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_simulation(simulation_id="a", simulation_type=SimulationType.WHAT_IF)
        eng.record_simulation(simulation_id="b", simulation_type=SimulationType.ROLLBACK)
        assert len(eng.list_simulations(simulation_type=SimulationType.WHAT_IF)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_simulation(simulation_id="a", impact_category=ImpactCategory.ACCESS_RESTRICTION)
        eng.record_simulation(simulation_id="b", impact_category=ImpactCategory.WORKFLOW_CHANGE)
        assert len(eng.list_simulations(impact_category=ImpactCategory.ACCESS_RESTRICTION)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_simulation(simulation_id="a", team="x")
        eng.record_simulation(simulation_id="b", team="y")
        assert len(eng.list_simulations(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_simulation(simulation_id=f"t-{i}")
        assert len(eng.list_simulations(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            simulation_id="t",
            simulation_type=SimulationType.ROLLBACK,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(simulation_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_simulation(
            simulation_id="a", simulation_type=SimulationType.WHAT_IF, impact_score=90.0
        )
        eng.record_simulation(
            simulation_id="b", simulation_type=SimulationType.WHAT_IF, impact_score=70.0
        )
        assert "what_if" in eng.analyze_type_distribution()

    def test_empty(self):
        assert _engine().analyze_type_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(impact_threshold=80.0)
        eng.record_simulation(simulation_id="a", impact_score=60.0)
        eng.record_simulation(simulation_id="b", impact_score=90.0)
        assert len(eng.identify_impact_gaps()) == 1

    def test_sorted(self):
        eng = _engine(impact_threshold=80.0)
        eng.record_simulation(simulation_id="a", impact_score=50.0)
        eng.record_simulation(simulation_id="b", impact_score=30.0)
        assert len(eng.identify_impact_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_simulation(simulation_id="a", service="s1", impact_score=80.0)
        eng.record_simulation(simulation_id="b", service="s2", impact_score=60.0)
        assert eng.rank_by_impact()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_impact() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(simulation_id="t", analysis_score=float(v))
        assert eng.detect_impact_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(simulation_id="t", analysis_score=float(v))
        assert eng.detect_impact_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_impact_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_simulation(simulation_id="t", impact_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_simulation(simulation_id="t")
        eng.add_analysis(simulation_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_simulation(simulation_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_simulation(simulation_id="a")
        eng.record_simulation(simulation_id="b")
        eng.add_analysis(simulation_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
