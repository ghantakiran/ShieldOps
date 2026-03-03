"""Tests for shieldops.security.data_breach_simulator — DataBreachSimulator."""

from __future__ import annotations

from shieldops.security.data_breach_simulator import (
    BreachAnalysis,
    BreachRecord,
    BreachScenario,
    BreachSimulationReport,
    DataBreachSimulator,
    DataSensitivity,
    SimulationMode,
)


def _engine(**kw) -> DataBreachSimulator:
    return DataBreachSimulator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_scenario_insider_threat(self):
        assert BreachScenario.INSIDER_THREAT == "insider_threat"

    def test_scenario_external_attack(self):
        assert BreachScenario.EXTERNAL_ATTACK == "external_attack"

    def test_scenario_accidental_exposure(self):
        assert BreachScenario.ACCIDENTAL_EXPOSURE == "accidental_exposure"

    def test_scenario_third_party(self):
        assert BreachScenario.THIRD_PARTY == "third_party"

    def test_scenario_system_failure(self):
        assert BreachScenario.SYSTEM_FAILURE == "system_failure"

    def test_sensitivity_public(self):
        assert DataSensitivity.PUBLIC == "public"

    def test_sensitivity_internal(self):
        assert DataSensitivity.INTERNAL == "internal"

    def test_sensitivity_confidential(self):
        assert DataSensitivity.CONFIDENTIAL == "confidential"

    def test_sensitivity_restricted(self):
        assert DataSensitivity.RESTRICTED == "restricted"

    def test_sensitivity_top_secret(self):
        assert DataSensitivity.TOP_SECRET == "top_secret"  # noqa: S105

    def test_mode_tabletop(self):
        assert SimulationMode.TABLETOP == "tabletop"

    def test_mode_automated(self):
        assert SimulationMode.AUTOMATED == "automated"

    def test_mode_hybrid(self):
        assert SimulationMode.HYBRID == "hybrid"

    def test_mode_targeted(self):
        assert SimulationMode.TARGETED == "targeted"

    def test_mode_full_scale(self):
        assert SimulationMode.FULL_SCALE == "full_scale"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_breach_record_defaults(self):
        r = BreachRecord()
        assert r.id
        assert r.simulation_id == ""
        assert r.breach_scenario == BreachScenario.EXTERNAL_ATTACK
        assert r.data_sensitivity == DataSensitivity.CONFIDENTIAL
        assert r.simulation_mode == SimulationMode.TABLETOP
        assert r.readiness_score == 0.0
        assert r.environment == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_breach_analysis_defaults(self):
        a = BreachAnalysis()
        assert a.id
        assert a.simulation_id == ""
        assert a.breach_scenario == BreachScenario.EXTERNAL_ATTACK
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = BreachSimulationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_readiness_score == 0.0
        assert r.by_scenario == {}
        assert r.by_sensitivity == {}
        assert r.by_mode == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_simulation / get_simulation
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_simulation(
            simulation_id="sim-001",
            breach_scenario=BreachScenario.INSIDER_THREAT,
            data_sensitivity=DataSensitivity.RESTRICTED,
            simulation_mode=SimulationMode.AUTOMATED,
            readiness_score=75.0,
            environment="prod",
            team="blue-team",
        )
        assert r.simulation_id == "sim-001"
        assert r.breach_scenario == BreachScenario.INSIDER_THREAT
        assert r.readiness_score == 75.0
        assert r.environment == "prod"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_simulation(
            simulation_id="sim-001", breach_scenario=BreachScenario.THIRD_PARTY
        )
        result = eng.get_simulation(r.id)
        assert result is not None
        assert result.breach_scenario == BreachScenario.THIRD_PARTY

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_simulation("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_simulation(simulation_id=f"sim-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_simulations
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_simulation(simulation_id="s-001")
        eng.record_simulation(simulation_id="s-002")
        assert len(eng.list_simulations()) == 2

    def test_filter_by_scenario(self):
        eng = _engine()
        eng.record_simulation(simulation_id="s-001", breach_scenario=BreachScenario.INSIDER_THREAT)
        eng.record_simulation(simulation_id="s-002", breach_scenario=BreachScenario.EXTERNAL_ATTACK)
        results = eng.list_simulations(breach_scenario=BreachScenario.INSIDER_THREAT)
        assert len(results) == 1

    def test_filter_by_mode(self):
        eng = _engine()
        eng.record_simulation(simulation_id="s-001", simulation_mode=SimulationMode.TABLETOP)
        eng.record_simulation(simulation_id="s-002", simulation_mode=SimulationMode.FULL_SCALE)
        results = eng.list_simulations(simulation_mode=SimulationMode.TABLETOP)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_simulation(simulation_id="s-001", team="blue-team")
        eng.record_simulation(simulation_id="s-002", team="red-team")
        results = eng.list_simulations(team="blue-team")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_simulation(simulation_id=f"s-{i}")
        assert len(eng.list_simulations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            simulation_id="sim-001",
            breach_scenario=BreachScenario.EXTERNAL_ATTACK,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="readiness gap identified",
        )
        assert a.simulation_id == "sim-001"
        assert a.breach_scenario == BreachScenario.EXTERNAL_ATTACK
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(simulation_id=f"s-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(simulation_id="sim-999", breach_scenario=BreachScenario.SYSTEM_FAILURE)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_scenario_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_simulation(
            simulation_id="s-001",
            breach_scenario=BreachScenario.EXTERNAL_ATTACK,
            readiness_score=90.0,
        )
        eng.record_simulation(
            simulation_id="s-002",
            breach_scenario=BreachScenario.EXTERNAL_ATTACK,
            readiness_score=70.0,
        )
        result = eng.analyze_scenario_distribution()
        assert "external_attack" in result
        assert result["external_attack"]["count"] == 2
        assert result["external_attack"]["avg_readiness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_scenario_distribution() == {}


# ---------------------------------------------------------------------------
# identify_readiness_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_simulation(simulation_id="s-001", readiness_score=60.0)
        eng.record_simulation(simulation_id="s-002", readiness_score=90.0)
        results = eng.identify_readiness_gaps()
        assert len(results) == 1
        assert results[0]["simulation_id"] == "s-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_simulation(simulation_id="s-001", readiness_score=50.0)
        eng.record_simulation(simulation_id="s-002", readiness_score=30.0)
        results = eng.identify_readiness_gaps()
        assert results[0]["readiness_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_readiness
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_simulation(simulation_id="s-001", environment="prod", readiness_score=90.0)
        eng.record_simulation(simulation_id="s-002", environment="staging", readiness_score=50.0)
        results = eng.rank_by_readiness()
        assert results[0]["environment"] == "staging"
        assert results[0]["avg_readiness_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_readiness() == []


# ---------------------------------------------------------------------------
# detect_readiness_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(simulation_id="s-001", analysis_score=50.0)
        result = eng.detect_readiness_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(simulation_id="s-001", analysis_score=20.0)
        eng.add_analysis(simulation_id="s-002", analysis_score=20.0)
        eng.add_analysis(simulation_id="s-003", analysis_score=80.0)
        eng.add_analysis(simulation_id="s-004", analysis_score=80.0)
        result = eng.detect_readiness_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_readiness_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_simulation(
            simulation_id="sim-001",
            breach_scenario=BreachScenario.INSIDER_THREAT,
            data_sensitivity=DataSensitivity.RESTRICTED,
            simulation_mode=SimulationMode.HYBRID,
            readiness_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, BreachSimulationReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_simulation(simulation_id="s-001")
        eng.add_analysis(simulation_id="s-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["scenario_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(simulation_id=f"s-{i}")
        assert len(eng._analyses) == 3
