"""Tests for shieldops.analytics.capacity_simulation — CapacitySimulationEngine."""

from __future__ import annotations

from shieldops.analytics.capacity_simulation import (
    CapacitySimulationEngine,
    CapacitySimulationReport,
    SimulationConfidence,
    SimulationOutcome,
    SimulationRecord,
    SimulationResult,
    SimulationScenario,
)


def _engine(**kw) -> CapacitySimulationEngine:
    return CapacitySimulationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_scenario_peak_load(self):
        assert SimulationScenario.PEAK_LOAD == "peak_load"

    def test_scenario_failure_mode(self):
        assert SimulationScenario.FAILURE_MODE == "failure_mode"

    def test_scenario_growth_projection(self):
        assert SimulationScenario.GROWTH_PROJECTION == "growth_projection"

    def test_scenario_cost_optimization(self):
        assert SimulationScenario.COST_OPTIMIZATION == "cost_optimization"

    def test_scenario_disaster_recovery(self):
        assert SimulationScenario.DISASTER_RECOVERY == "disaster_recovery"

    def test_outcome_within_capacity(self):
        assert SimulationOutcome.WITHIN_CAPACITY == "within_capacity"

    def test_outcome_near_limit(self):
        assert SimulationOutcome.NEAR_LIMIT == "near_limit"

    def test_outcome_over_capacity(self):
        assert SimulationOutcome.OVER_CAPACITY == "over_capacity"

    def test_outcome_requires_scaling(self):
        assert SimulationOutcome.REQUIRES_SCALING == "requires_scaling"

    def test_outcome_critical_shortage(self):
        assert SimulationOutcome.CRITICAL_SHORTAGE == "critical_shortage"

    def test_confidence_high(self):
        assert SimulationConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert SimulationConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert SimulationConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert SimulationConfidence.SPECULATIVE == "speculative"

    def test_confidence_unknown(self):
        assert SimulationConfidence.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_simulation_record_defaults(self):
        r = SimulationRecord()
        assert r.id
        assert r.scenario_id == ""
        assert r.simulation_scenario == SimulationScenario.PEAK_LOAD
        assert r.simulation_outcome == SimulationOutcome.WITHIN_CAPACITY
        assert r.simulation_confidence == SimulationConfidence.UNKNOWN
        assert r.capacity_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_simulation_result_defaults(self):
        r = SimulationResult()
        assert r.id
        assert r.scenario_id == ""
        assert r.simulation_scenario == SimulationScenario.PEAK_LOAD
        assert r.result_value == 0.0
        assert r.threshold == 0.0
        assert r.breached is False
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = CapacitySimulationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_results == 0
        assert r.over_capacity_count == 0
        assert r.avg_capacity_score == 0.0
        assert r.by_scenario == {}
        assert r.by_outcome == {}
        assert r.by_confidence == {}
        assert r.top_at_risk == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_simulation
# ---------------------------------------------------------------------------


class TestRecordSimulation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_simulation(
            scenario_id="SIM-001",
            simulation_scenario=SimulationScenario.PEAK_LOAD,
            simulation_outcome=SimulationOutcome.OVER_CAPACITY,
            simulation_confidence=SimulationConfidence.HIGH,
            capacity_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.scenario_id == "SIM-001"
        assert r.simulation_scenario == SimulationScenario.PEAK_LOAD
        assert r.simulation_outcome == SimulationOutcome.OVER_CAPACITY
        assert r.simulation_confidence == SimulationConfidence.HIGH
        assert r.capacity_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_simulation(scenario_id=f"SIM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_simulation
# ---------------------------------------------------------------------------


class TestGetSimulation:
    def test_found(self):
        eng = _engine()
        r = eng.record_simulation(
            scenario_id="SIM-001",
            capacity_score=85.0,
        )
        result = eng.get_simulation(r.id)
        assert result is not None
        assert result.capacity_score == 85.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_simulation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_simulations
# ---------------------------------------------------------------------------


class TestListSimulations:
    def test_list_all(self):
        eng = _engine()
        eng.record_simulation(scenario_id="SIM-001")
        eng.record_simulation(scenario_id="SIM-002")
        assert len(eng.list_simulations()) == 2

    def test_filter_by_scenario(self):
        eng = _engine()
        eng.record_simulation(
            scenario_id="SIM-001",
            simulation_scenario=SimulationScenario.PEAK_LOAD,
        )
        eng.record_simulation(
            scenario_id="SIM-002",
            simulation_scenario=SimulationScenario.FAILURE_MODE,
        )
        results = eng.list_simulations(scenario=SimulationScenario.PEAK_LOAD)
        assert len(results) == 1

    def test_filter_by_outcome(self):
        eng = _engine()
        eng.record_simulation(
            scenario_id="SIM-001",
            simulation_outcome=SimulationOutcome.OVER_CAPACITY,
        )
        eng.record_simulation(
            scenario_id="SIM-002",
            simulation_outcome=SimulationOutcome.WITHIN_CAPACITY,
        )
        results = eng.list_simulations(outcome=SimulationOutcome.OVER_CAPACITY)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_simulation(scenario_id="SIM-001", service="api-gateway")
        eng.record_simulation(scenario_id="SIM-002", service="auth-svc")
        results = eng.list_simulations(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_simulation(scenario_id="SIM-001", team="sre")
        eng.record_simulation(scenario_id="SIM-002", team="platform")
        results = eng.list_simulations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_simulation(scenario_id=f"SIM-{i}")
        assert len(eng.list_simulations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_result
# ---------------------------------------------------------------------------


class TestAddResult:
    def test_basic(self):
        eng = _engine()
        r = eng.add_result(
            scenario_id="SIM-001",
            simulation_scenario=SimulationScenario.PEAK_LOAD,
            result_value=92.0,
            threshold=80.0,
            breached=True,
            description="CPU exceeded threshold",
        )
        assert r.scenario_id == "SIM-001"
        assert r.simulation_scenario == SimulationScenario.PEAK_LOAD
        assert r.result_value == 92.0
        assert r.threshold == 80.0
        assert r.breached is True
        assert r.description == "CPU exceeded threshold"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_result(scenario_id=f"SIM-{i}")
        assert len(eng._results) == 2


# ---------------------------------------------------------------------------
# analyze_simulation_outcomes
# ---------------------------------------------------------------------------


class TestAnalyzeSimulationOutcomes:
    def test_with_data(self):
        eng = _engine()
        eng.record_simulation(
            scenario_id="SIM-001",
            simulation_scenario=SimulationScenario.PEAK_LOAD,
            capacity_score=80.0,
        )
        eng.record_simulation(
            scenario_id="SIM-002",
            simulation_scenario=SimulationScenario.PEAK_LOAD,
            capacity_score=60.0,
        )
        result = eng.analyze_simulation_outcomes()
        assert "peak_load" in result
        assert result["peak_load"]["count"] == 2
        assert result["peak_load"]["avg_capacity_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_simulation_outcomes() == {}


# ---------------------------------------------------------------------------
# identify_over_capacity_scenarios
# ---------------------------------------------------------------------------


class TestIdentifyOverCapacityScenarios:
    def test_detects_over_capacity(self):
        eng = _engine()
        eng.record_simulation(
            scenario_id="SIM-001",
            simulation_outcome=SimulationOutcome.OVER_CAPACITY,
        )
        eng.record_simulation(
            scenario_id="SIM-002",
            simulation_outcome=SimulationOutcome.WITHIN_CAPACITY,
        )
        results = eng.identify_over_capacity_scenarios()
        assert len(results) == 1
        assert results[0]["scenario_id"] == "SIM-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_over_capacity_scenarios() == []


# ---------------------------------------------------------------------------
# rank_by_risk
# ---------------------------------------------------------------------------


class TestRankByRisk:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_simulation(
            scenario_id="SIM-001",
            service="api-gateway",
            simulation_outcome=SimulationOutcome.OVER_CAPACITY,
        )
        eng.record_simulation(
            scenario_id="SIM-002",
            service="api-gateway",
            simulation_outcome=SimulationOutcome.CRITICAL_SHORTAGE,
        )
        eng.record_simulation(
            scenario_id="SIM-003",
            service="auth-svc",
            simulation_outcome=SimulationOutcome.OVER_CAPACITY,
        )
        results = eng.rank_by_risk()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["over_capacity_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk() == []


# ---------------------------------------------------------------------------
# detect_capacity_trends
# ---------------------------------------------------------------------------


class TestDetectCapacityTrends:
    def test_stable(self):
        eng = _engine()
        for val in [50.0, 50.0, 50.0, 50.0]:
            eng.add_result(scenario_id="SIM-001", result_value=val)
        result = eng.detect_capacity_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for val in [30.0, 30.0, 80.0, 80.0]:
            eng.add_result(scenario_id="SIM-001", result_value=val)
        result = eng.detect_capacity_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_capacity_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_simulation(
            scenario_id="SIM-001",
            simulation_scenario=SimulationScenario.PEAK_LOAD,
            simulation_outcome=SimulationOutcome.OVER_CAPACITY,
            capacity_score=40.0,
            service="api-gateway",
        )
        report = eng.generate_report()
        assert isinstance(report, CapacitySimulationReport)
        assert report.total_records == 1
        assert report.over_capacity_count == 1
        assert len(report.top_at_risk) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_simulation(scenario_id="SIM-001")
        eng.add_result(scenario_id="SIM-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._results) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_results"] == 0
        assert stats["scenario_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_simulation(
            scenario_id="SIM-001",
            simulation_scenario=SimulationScenario.PEAK_LOAD,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "peak_load" in stats["scenario_distribution"]
