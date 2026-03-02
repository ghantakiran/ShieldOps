"""Tests for shieldops.security.adversary_simulation_engine — AdversarySimulationEngine."""

from __future__ import annotations

from shieldops.security.adversary_simulation_engine import (
    AdversarySimulationEngine,
    AdversarySimulationReport,
    SimulationAnalysis,
    SimulationOutcome,
    SimulationRecord,
    SimulationType,
    TTPCategory,
)


def _engine(**kw) -> AdversarySimulationEngine:
    return AdversarySimulationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_red_team(self):
        assert SimulationType.RED_TEAM == "red_team"

    def test_type_purple_team(self):
        assert SimulationType.PURPLE_TEAM == "purple_team"

    def test_type_tabletop(self):
        assert SimulationType.TABLETOP == "tabletop"

    def test_type_automated(self):
        assert SimulationType.AUTOMATED == "automated"

    def test_type_breach_simulation(self):
        assert SimulationType.BREACH_SIMULATION == "breach_simulation"

    def test_ttp_initial_access(self):
        assert TTPCategory.INITIAL_ACCESS == "initial_access"

    def test_ttp_lateral_movement(self):
        assert TTPCategory.LATERAL_MOVEMENT == "lateral_movement"

    def test_ttp_exfiltration(self):
        assert TTPCategory.EXFILTRATION == "exfiltration"

    def test_ttp_command_control(self):
        assert TTPCategory.COMMAND_CONTROL == "command_control"

    def test_ttp_impact(self):
        assert TTPCategory.IMPACT == "impact"

    def test_outcome_detected(self):
        assert SimulationOutcome.DETECTED == "detected"

    def test_outcome_partially_detected(self):
        assert SimulationOutcome.PARTIALLY_DETECTED == "partially_detected"

    def test_outcome_missed(self):
        assert SimulationOutcome.MISSED == "missed"

    def test_outcome_blocked(self):
        assert SimulationOutcome.BLOCKED == "blocked"

    def test_outcome_contained(self):
        assert SimulationOutcome.CONTAINED == "contained"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_simulation_record_defaults(self):
        r = SimulationRecord()
        assert r.id
        assert r.simulation_name == ""
        assert r.simulation_type == SimulationType.RED_TEAM
        assert r.ttp_category == TTPCategory.INITIAL_ACCESS
        assert r.simulation_outcome == SimulationOutcome.DETECTED
        assert r.detection_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_simulation_analysis_defaults(self):
        c = SimulationAnalysis()
        assert c.id
        assert c.simulation_name == ""
        assert c.simulation_type == SimulationType.RED_TEAM
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_adversary_simulation_report_defaults(self):
        r = AdversarySimulationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_detection_count == 0
        assert r.avg_detection_score == 0.0
        assert r.by_type == {}
        assert r.by_ttp == {}
        assert r.by_outcome == {}
        assert r.top_low_detection == []
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
            simulation_name="apt29-simulation",
            simulation_type=SimulationType.PURPLE_TEAM,
            ttp_category=TTPCategory.LATERAL_MOVEMENT,
            simulation_outcome=SimulationOutcome.PARTIALLY_DETECTED,
            detection_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.simulation_name == "apt29-simulation"
        assert r.simulation_type == SimulationType.PURPLE_TEAM
        assert r.ttp_category == TTPCategory.LATERAL_MOVEMENT
        assert r.simulation_outcome == SimulationOutcome.PARTIALLY_DETECTED
        assert r.detection_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_simulation(simulation_name=f"SIM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_simulation
# ---------------------------------------------------------------------------


class TestGetSimulation:
    def test_found(self):
        eng = _engine()
        r = eng.record_simulation(
            simulation_name="apt29-simulation",
            simulation_outcome=SimulationOutcome.DETECTED,
        )
        result = eng.get_simulation(r.id)
        assert result is not None
        assert result.simulation_outcome == SimulationOutcome.DETECTED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_simulation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_simulations
# ---------------------------------------------------------------------------


class TestListSimulations:
    def test_list_all(self):
        eng = _engine()
        eng.record_simulation(simulation_name="SIM-001")
        eng.record_simulation(simulation_name="SIM-002")
        assert len(eng.list_simulations()) == 2

    def test_filter_by_simulation_type(self):
        eng = _engine()
        eng.record_simulation(
            simulation_name="SIM-001",
            simulation_type=SimulationType.RED_TEAM,
        )
        eng.record_simulation(
            simulation_name="SIM-002",
            simulation_type=SimulationType.TABLETOP,
        )
        results = eng.list_simulations(simulation_type=SimulationType.RED_TEAM)
        assert len(results) == 1

    def test_filter_by_ttp_category(self):
        eng = _engine()
        eng.record_simulation(
            simulation_name="SIM-001",
            ttp_category=TTPCategory.INITIAL_ACCESS,
        )
        eng.record_simulation(
            simulation_name="SIM-002",
            ttp_category=TTPCategory.EXFILTRATION,
        )
        results = eng.list_simulations(
            ttp_category=TTPCategory.INITIAL_ACCESS,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_simulation(simulation_name="SIM-001", team="security")
        eng.record_simulation(simulation_name="SIM-002", team="platform")
        results = eng.list_simulations(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_simulation(simulation_name=f"SIM-{i}")
        assert len(eng.list_simulations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            simulation_name="apt29-simulation",
            simulation_type=SimulationType.PURPLE_TEAM,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="low detection rate observed",
        )
        assert a.simulation_name == "apt29-simulation"
        assert a.simulation_type == SimulationType.PURPLE_TEAM
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(simulation_name=f"SIM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_simulation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeSimulationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_simulation(
            simulation_name="SIM-001",
            simulation_type=SimulationType.RED_TEAM,
            detection_score=90.0,
        )
        eng.record_simulation(
            simulation_name="SIM-002",
            simulation_type=SimulationType.RED_TEAM,
            detection_score=70.0,
        )
        result = eng.analyze_simulation_distribution()
        assert "red_team" in result
        assert result["red_team"]["count"] == 2
        assert result["red_team"]["avg_detection_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_simulation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_detection_simulations
# ---------------------------------------------------------------------------


class TestIdentifyLowDetectionSimulations:
    def test_detects_below_threshold(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_simulation(simulation_name="SIM-001", detection_score=60.0)
        eng.record_simulation(simulation_name="SIM-002", detection_score=90.0)
        results = eng.identify_low_detection_simulations()
        assert len(results) == 1
        assert results[0]["simulation_name"] == "SIM-001"

    def test_sorted_ascending(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_simulation(simulation_name="SIM-001", detection_score=50.0)
        eng.record_simulation(simulation_name="SIM-002", detection_score=30.0)
        results = eng.identify_low_detection_simulations()
        assert len(results) == 2
        assert results[0]["detection_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_detection_simulations() == []


# ---------------------------------------------------------------------------
# rank_by_detection
# ---------------------------------------------------------------------------


class TestRankByDetection:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_simulation(simulation_name="SIM-001", service="auth-svc", detection_score=90.0)
        eng.record_simulation(simulation_name="SIM-002", service="api-gw", detection_score=50.0)
        results = eng.rank_by_detection()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_detection_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_detection() == []


# ---------------------------------------------------------------------------
# detect_simulation_trends
# ---------------------------------------------------------------------------


class TestDetectSimulationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(simulation_name="SIM-001", analysis_score=50.0)
        result = eng.detect_simulation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(simulation_name="SIM-001", analysis_score=20.0)
        eng.add_analysis(simulation_name="SIM-002", analysis_score=20.0)
        eng.add_analysis(simulation_name="SIM-003", analysis_score=80.0)
        eng.add_analysis(simulation_name="SIM-004", analysis_score=80.0)
        result = eng.detect_simulation_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_simulation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_simulation(
            simulation_name="apt29-simulation",
            simulation_type=SimulationType.PURPLE_TEAM,
            ttp_category=TTPCategory.LATERAL_MOVEMENT,
            simulation_outcome=SimulationOutcome.PARTIALLY_DETECTED,
            detection_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AdversarySimulationReport)
        assert report.total_records == 1
        assert report.low_detection_count == 1
        assert len(report.top_low_detection) == 1
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
        eng.record_simulation(simulation_name="SIM-001")
        eng.add_analysis(simulation_name="SIM-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_simulation(
            simulation_name="SIM-001",
            simulation_type=SimulationType.RED_TEAM,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "red_team" in stats["type_distribution"]
