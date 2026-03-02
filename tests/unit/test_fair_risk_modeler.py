"""Tests for shieldops.compliance.fair_risk_modeler — FAIRRiskModeler."""

from __future__ import annotations

from shieldops.compliance.fair_risk_modeler import (
    FAIRRiskModeler,
    ModelConfidence,
    RiskFactor,
    RiskModelAnalysis,
    RiskModelRecord,
    RiskModelReport,
    ScenarioType,
)


def _engine(**kw) -> FAIRRiskModeler:
    return FAIRRiskModeler(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_riskfactor_threat_event_frequency(self):
        assert RiskFactor.THREAT_EVENT_FREQUENCY == "threat_event_frequency"

    def test_riskfactor_vulnerability(self):
        assert RiskFactor.VULNERABILITY == "vulnerability"

    def test_riskfactor_contact_frequency(self):
        assert RiskFactor.CONTACT_FREQUENCY == "contact_frequency"

    def test_riskfactor_probability_of_action(self):
        assert RiskFactor.PROBABILITY_OF_ACTION == "probability_of_action"

    def test_riskfactor_loss_magnitude(self):
        assert RiskFactor.LOSS_MAGNITUDE == "loss_magnitude"

    def test_modelconfidence_very_high(self):
        assert ModelConfidence.VERY_HIGH == "very_high"

    def test_modelconfidence_high(self):
        assert ModelConfidence.HIGH == "high"

    def test_modelconfidence_medium(self):
        assert ModelConfidence.MEDIUM == "medium"

    def test_modelconfidence_low(self):
        assert ModelConfidence.LOW == "low"

    def test_modelconfidence_very_low(self):
        assert ModelConfidence.VERY_LOW == "very_low"

    def test_scenariotype_best_case(self):
        assert ScenarioType.BEST_CASE == "best_case"

    def test_scenariotype_likely_case(self):
        assert ScenarioType.LIKELY_CASE == "likely_case"

    def test_scenariotype_worst_case(self):
        assert ScenarioType.WORST_CASE == "worst_case"

    def test_scenariotype_monte_carlo(self):
        assert ScenarioType.MONTE_CARLO == "monte_carlo"

    def test_scenariotype_deterministic(self):
        assert ScenarioType.DETERMINISTIC == "deterministic"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_riskmodelrecord_defaults(self):
        r = RiskModelRecord()
        assert r.id
        assert r.scenario_name == ""
        assert r.risk_estimate == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_riskmodelanalysis_defaults(self):
        c = RiskModelAnalysis()
        assert c.id
        assert c.scenario_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_riskmodelreport_defaults(self):
        r = RiskModelReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_risk_count == 0
        assert r.avg_risk_estimate == 0
        assert r.by_factor == {}
        assert r.by_confidence == {}
        assert r.by_scenario == {}
        assert r.top_high_risk == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_scenario
# ---------------------------------------------------------------------------


class TestRecordScenario:
    def test_basic(self):
        eng = _engine()
        r = eng.record_scenario(
            scenario_name="test-item",
            risk_factor=RiskFactor.VULNERABILITY,
            risk_estimate=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.scenario_name == "test-item"
        assert r.risk_estimate == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_scenario(scenario_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_scenario
# ---------------------------------------------------------------------------


class TestGetScenario:
    def test_found(self):
        eng = _engine()
        r = eng.record_scenario(scenario_name="test-item")
        result = eng.get_scenario(r.id)
        assert result is not None
        assert result.scenario_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_scenario("nonexistent") is None


# ---------------------------------------------------------------------------
# list_scenarios
# ---------------------------------------------------------------------------


class TestListScenarios:
    def test_list_all(self):
        eng = _engine()
        eng.record_scenario(scenario_name="ITEM-001")
        eng.record_scenario(scenario_name="ITEM-002")
        assert len(eng.list_scenarios()) == 2

    def test_filter_by_risk_factor(self):
        eng = _engine()
        eng.record_scenario(scenario_name="ITEM-001", risk_factor=RiskFactor.THREAT_EVENT_FREQUENCY)
        eng.record_scenario(scenario_name="ITEM-002", risk_factor=RiskFactor.VULNERABILITY)
        results = eng.list_scenarios(risk_factor=RiskFactor.THREAT_EVENT_FREQUENCY)
        assert len(results) == 1

    def test_filter_by_scenario_type(self):
        eng = _engine()
        eng.record_scenario(scenario_name="ITEM-001", scenario_type=ScenarioType.BEST_CASE)
        eng.record_scenario(scenario_name="ITEM-002", scenario_type=ScenarioType.LIKELY_CASE)
        results = eng.list_scenarios(scenario_type=ScenarioType.BEST_CASE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_scenario(scenario_name="ITEM-001", team="security")
        eng.record_scenario(scenario_name="ITEM-002", team="platform")
        results = eng.list_scenarios(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_scenario(scenario_name=f"ITEM-{i}")
        assert len(eng.list_scenarios(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            scenario_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.scenario_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(scenario_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_factor_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_scenario(
            scenario_name="ITEM-001",
            risk_factor=RiskFactor.THREAT_EVENT_FREQUENCY,
            risk_estimate=90.0,
        )
        eng.record_scenario(
            scenario_name="ITEM-002",
            risk_factor=RiskFactor.THREAT_EVENT_FREQUENCY,
            risk_estimate=70.0,
        )
        result = eng.analyze_factor_distribution()
        assert "threat_event_frequency" in result
        assert result["threat_event_frequency"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_factor_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_risk_scenarios
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(risk_estimate_threshold=70.0)
        eng.record_scenario(scenario_name="ITEM-001", risk_estimate=90.0)
        eng.record_scenario(scenario_name="ITEM-002", risk_estimate=40.0)
        results = eng.identify_high_risk_scenarios()
        assert len(results) == 1
        assert results[0]["scenario_name"] == "ITEM-001"

    def test_sorted_descending(self):
        eng = _engine(risk_estimate_threshold=70.0)
        eng.record_scenario(scenario_name="ITEM-001", risk_estimate=80.0)
        eng.record_scenario(scenario_name="ITEM-002", risk_estimate=95.0)
        results = eng.identify_high_risk_scenarios()
        assert len(results) == 2
        assert results[0]["risk_estimate"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_scenarios() == []


# ---------------------------------------------------------------------------
# rank_by_risk_estimate
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_scenario(scenario_name="ITEM-001", service="auth-svc", risk_estimate=90.0)
        eng.record_scenario(scenario_name="ITEM-002", service="api-gw", risk_estimate=50.0)
        results = eng.rank_by_risk_estimate()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_estimate() == []


# ---------------------------------------------------------------------------
# detect_risk_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(scenario_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_risk_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(scenario_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(scenario_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(scenario_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(scenario_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_risk_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_risk_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(risk_estimate_threshold=70.0)
        eng.record_scenario(scenario_name="test-item", risk_estimate=90.0)
        report = eng.generate_report()
        assert isinstance(report, RiskModelReport)
        assert report.total_records == 1
        assert report.high_risk_count == 1
        assert len(report.top_high_risk) == 1
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
        eng.record_scenario(scenario_name="ITEM-001")
        eng.add_analysis(scenario_name="ITEM-001")
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

    def test_populated(self):
        eng = _engine()
        eng.record_scenario(
            scenario_name="ITEM-001",
            risk_factor=RiskFactor.THREAT_EVENT_FREQUENCY,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
