"""Tests for shieldops.security.purple_team_automation_engine — PurpleTeamAutomationEngine."""

from __future__ import annotations

from shieldops.security.purple_team_automation_engine import (
    AttackTechnique,
    PurpleTeamAutomationEngine,
    PurpleTeamReport,
    SimulationAnalysis,
    SimulationRecord,
    SimulationResult,
    SimulationSource,
)


def _engine(**kw) -> PurpleTeamAutomationEngine:
    return PurpleTeamAutomationEngine(**kw)


class TestEnums:
    def test_attack_technique_initial_access(self):
        assert AttackTechnique.INITIAL_ACCESS == "initial_access"

    def test_attack_technique_execution(self):
        assert AttackTechnique.EXECUTION == "execution"

    def test_attack_technique_persistence(self):
        assert AttackTechnique.PERSISTENCE == "persistence"

    def test_attack_technique_privilege_escalation(self):
        assert AttackTechnique.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_attack_technique_defense_evasion(self):
        assert AttackTechnique.DEFENSE_EVASION == "defense_evasion"

    def test_simulation_source_atomic_red_team(self):
        assert SimulationSource.ATOMIC_RED_TEAM == "atomic_red_team"

    def test_simulation_source_caldera(self):
        assert SimulationSource.CALDERA == "caldera"

    def test_simulation_source_custom(self):
        assert SimulationSource.CUSTOM == "custom"

    def test_simulation_source_mitre_attack(self):
        assert SimulationSource.MITRE_ATTACK == "mitre_attack"

    def test_simulation_source_manual(self):
        assert SimulationSource.MANUAL == "manual"

    def test_simulation_result_detected(self):
        assert SimulationResult.DETECTED == "detected"

    def test_simulation_result_partially_detected(self):
        assert SimulationResult.PARTIALLY_DETECTED == "partially_detected"

    def test_simulation_result_missed(self):
        assert SimulationResult.MISSED == "missed"

    def test_simulation_result_blocked(self):
        assert SimulationResult.BLOCKED == "blocked"

    def test_simulation_result_error(self):
        assert SimulationResult.ERROR == "error"


class TestModels:
    def test_record_defaults(self):
        r = SimulationRecord()
        assert r.id
        assert r.name == ""
        assert r.attack_technique == AttackTechnique.INITIAL_ACCESS
        assert r.simulation_source == SimulationSource.ATOMIC_RED_TEAM
        assert r.simulation_result == SimulationResult.ERROR
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = SimulationAnalysis()
        assert a.id
        assert a.name == ""
        assert a.attack_technique == AttackTechnique.INITIAL_ACCESS
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PurpleTeamReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_attack_technique == {}
        assert r.by_simulation_source == {}
        assert r.by_simulation_result == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            attack_technique=AttackTechnique.INITIAL_ACCESS,
            simulation_source=SimulationSource.CALDERA,
            simulation_result=SimulationResult.DETECTED,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.attack_technique == AttackTechnique.INITIAL_ACCESS
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_attack_technique(self):
        eng = _engine()
        eng.record_entry(name="a", attack_technique=AttackTechnique.INITIAL_ACCESS)
        eng.record_entry(name="b", attack_technique=AttackTechnique.EXECUTION)
        assert len(eng.list_records(attack_technique=AttackTechnique.INITIAL_ACCESS)) == 1

    def test_filter_by_simulation_source(self):
        eng = _engine()
        eng.record_entry(name="a", simulation_source=SimulationSource.ATOMIC_RED_TEAM)
        eng.record_entry(name="b", simulation_source=SimulationSource.CALDERA)
        assert len(eng.list_records(simulation_source=SimulationSource.ATOMIC_RED_TEAM)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", attack_technique=AttackTechnique.EXECUTION, score=90.0)
        eng.record_entry(name="b", attack_technique=AttackTechnique.EXECUTION, score=70.0)
        result = eng.analyze_distribution()
        assert "execution" in result
        assert result["execution"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
