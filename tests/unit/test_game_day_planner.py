"""Tests for shieldops.operations.game_day_planner — GameDayPlanner.

Covers GameDayStatus, ScenarioComplexity, and ObjectiveType enums,
GameDayPlan / GameDayScenario / GameDayReport models, and all
GameDayPlanner operations including game day creation, scenario management,
team readiness, coverage gap identification, action item tracking, and
report generation.
"""

from __future__ import annotations

from shieldops.operations.game_day_planner import (
    GameDayPlan,
    GameDayPlanner,
    GameDayReport,
    GameDayScenario,
    GameDayStatus,
    ObjectiveType,
    ScenarioComplexity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kw) -> GameDayPlanner:
    return GameDayPlanner(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of GameDayStatus, ScenarioComplexity, and ObjectiveType."""

    # -- GameDayStatus (5 members) -------------------------------------------

    def test_status_planning(self):
        assert GameDayStatus.PLANNING == "planning"

    def test_status_scheduled(self):
        assert GameDayStatus.SCHEDULED == "scheduled"

    def test_status_in_progress(self):
        assert GameDayStatus.IN_PROGRESS == "in_progress"

    def test_status_completed(self):
        assert GameDayStatus.COMPLETED == "completed"

    def test_status_cancelled(self):
        assert GameDayStatus.CANCELLED == "cancelled"

    # -- ScenarioComplexity (5 members) --------------------------------------

    def test_complexity_basic(self):
        assert ScenarioComplexity.BASIC == "basic"

    def test_complexity_intermediate(self):
        assert ScenarioComplexity.INTERMEDIATE == "intermediate"

    def test_complexity_advanced(self):
        assert ScenarioComplexity.ADVANCED == "advanced"

    def test_complexity_expert(self):
        assert ScenarioComplexity.EXPERT == "expert"

    def test_complexity_extreme(self):
        assert ScenarioComplexity.EXTREME == "extreme"

    # -- ObjectiveType (5 members) -------------------------------------------

    def test_objective_detection_time(self):
        assert ObjectiveType.DETECTION_TIME == "detection_time"

    def test_objective_recovery_time(self):
        assert ObjectiveType.RECOVERY_TIME == "recovery_time"

    def test_objective_communication(self):
        assert ObjectiveType.COMMUNICATION == "communication"

    def test_objective_escalation(self):
        assert ObjectiveType.ESCALATION == "escalation"

    def test_objective_documentation(self):
        assert ObjectiveType.DOCUMENTATION == "documentation"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_game_day_plan_defaults(self):
        gd = GameDayPlan()
        assert gd.id
        assert gd.name == ""
        assert gd.status == GameDayStatus.PLANNING
        assert gd.scheduled_date == ""
        assert gd.teams == []
        assert gd.objectives == []
        assert gd.scenarios == []
        assert gd.lessons_learned == []
        assert gd.created_at > 0

    def test_game_day_scenario_defaults(self):
        s = GameDayScenario()
        assert s.id
        assert s.game_day_id == ""
        assert s.name == ""
        assert s.complexity == ScenarioComplexity.BASIC
        assert s.description == ""
        assert s.target_service == ""
        assert s.expected_outcome == ""
        assert s.actual_outcome == ""
        assert s.score == 0.0
        assert s.created_at > 0

    def test_game_day_report_defaults(self):
        r = GameDayReport()
        assert r.total_game_days == 0
        assert r.total_scenarios == 0
        assert r.avg_score == 0.0
        assert r.by_status == {}
        assert r.by_complexity == {}
        assert r.coverage_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ===========================================================================
# CreateGameDay
# ===========================================================================


class TestCreateGameDay:
    """Test GameDayPlanner.create_game_day."""

    def test_basic_creation(self):
        eng = _engine()
        gd = eng.create_game_day(
            name="Q1 Resilience Day",
            scheduled_date="2026-03-15",
            teams=["platform", "infra"],
            objectives=["Validate failover", "Test alerts"],
        )
        assert gd.id
        assert gd.name == "Q1 Resilience Day"
        assert gd.scheduled_date == "2026-03-15"
        assert gd.teams == ["platform", "infra"]
        assert gd.objectives == ["Validate failover", "Test alerts"]
        assert gd.status == GameDayStatus.PLANNING

    def test_eviction_on_overflow(self):
        eng = _engine(max_game_days=2)
        eng.create_game_day(name="gd-1")
        eng.create_game_day(name="gd-2")
        gd3 = eng.create_game_day(name="gd-3")
        days = eng.list_game_days(limit=10)
        assert len(days) == 2
        assert days[-1].id == gd3.id


# ===========================================================================
# GetGameDay
# ===========================================================================


class TestGetGameDay:
    """Test GameDayPlanner.get_game_day."""

    def test_found(self):
        eng = _engine()
        gd = eng.create_game_day(name="find-me")
        assert eng.get_game_day(gd.id) is gd

    def test_not_found(self):
        eng = _engine()
        assert eng.get_game_day("nonexistent-id") is None


# ===========================================================================
# ListGameDays
# ===========================================================================


class TestListGameDays:
    """Test GameDayPlanner.list_game_days with optional filtering."""

    def test_all_game_days(self):
        eng = _engine()
        eng.create_game_day(name="gd-1")
        eng.create_game_day(name="gd-2")
        assert len(eng.list_game_days()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.create_game_day(name="planning-gd")
        completed_gd = eng.create_game_day(name="completed-gd")
        completed_gd.status = GameDayStatus.COMPLETED
        results = eng.list_game_days(status=GameDayStatus.COMPLETED)
        assert len(results) == 1
        assert results[0].id == completed_gd.id


# ===========================================================================
# AddScenario
# ===========================================================================


class TestAddScenario:
    """Test GameDayPlanner.add_scenario."""

    def test_add_to_existing_game_day(self):
        eng = _engine()
        gd = eng.create_game_day(name="test-gd")
        scenario = eng.add_scenario(
            game_day_id=gd.id,
            name="DB failover",
            complexity=ScenarioComplexity.ADVANCED,
            description="Simulate primary DB failure",
            target_service="db-svc",
            expected_outcome="Secondary takes over within 30s",
        )
        assert scenario is not None
        assert scenario.game_day_id == gd.id
        assert scenario.name == "DB failover"
        assert scenario.complexity == ScenarioComplexity.ADVANCED
        assert scenario.id in gd.scenarios

    def test_add_to_nonexistent_game_day(self):
        eng = _engine()
        result = eng.add_scenario(
            game_day_id="nonexistent",
            name="orphan",
            complexity=ScenarioComplexity.BASIC,
        )
        assert result is None

    def test_multiple_scenarios(self):
        eng = _engine()
        gd = eng.create_game_day(name="multi-scenario-gd")
        eng.add_scenario(game_day_id=gd.id, name="s1", complexity=ScenarioComplexity.BASIC)
        eng.add_scenario(game_day_id=gd.id, name="s2", complexity=ScenarioComplexity.EXPERT)
        assert len(gd.scenarios) == 2


# ===========================================================================
# ScoreScenario
# ===========================================================================


class TestScoreScenario:
    """Test GameDayPlanner.score_scenario."""

    def test_score_existing(self):
        eng = _engine()
        gd = eng.create_game_day(name="scoring-gd")
        scenario = eng.add_scenario(
            game_day_id=gd.id, name="test-scenario", complexity=ScenarioComplexity.BASIC
        )
        result = eng.score_scenario(scenario.id, score=85.5, actual_outcome="Passed with delay")
        assert result is not None
        assert result.score == 85.5
        assert result.actual_outcome == "Passed with delay"

    def test_score_nonexistent(self):
        eng = _engine()
        result = eng.score_scenario("nonexistent", score=50.0)
        assert result is None


# ===========================================================================
# CalculateTeamReadiness
# ===========================================================================


class TestCalculateTeamReadiness:
    """Test GameDayPlanner.calculate_team_readiness."""

    def test_single_team(self):
        eng = _engine()
        gd = eng.create_game_day(name="readiness-gd", teams=["platform"])
        s1 = eng.add_scenario(game_day_id=gd.id, name="s1", complexity=ScenarioComplexity.BASIC)
        s2 = eng.add_scenario(game_day_id=gd.id, name="s2", complexity=ScenarioComplexity.BASIC)
        eng.score_scenario(s1.id, score=80.0)
        eng.score_scenario(s2.id, score=60.0)
        readiness = eng.calculate_team_readiness()
        assert readiness["team_scores"]["platform"] == 70.0
        assert readiness["overall_readiness"] == 70.0

    def test_multiple_teams(self):
        eng = _engine()
        gd = eng.create_game_day(name="multi-team", teams=["alpha", "beta"])
        s = eng.add_scenario(game_day_id=gd.id, name="s1", complexity=ScenarioComplexity.BASIC)
        eng.score_scenario(s.id, score=90.0)
        readiness = eng.calculate_team_readiness()
        assert readiness["team_scores"]["alpha"] == 90.0
        assert readiness["team_scores"]["beta"] == 90.0
        assert readiness["overall_readiness"] == 90.0

    def test_no_teams(self):
        eng = _engine()
        readiness = eng.calculate_team_readiness()
        assert readiness["team_scores"] == {}
        assert readiness["overall_readiness"] == 0.0


# ===========================================================================
# IdentifyCoverageGaps
# ===========================================================================


class TestIdentifyCoverageGaps:
    """Test GameDayPlanner.identify_coverage_gaps."""

    def test_insufficient_scenarios(self):
        eng = _engine(min_scenarios_per_day=3)
        gd = eng.create_game_day(name="sparse-gd")
        eng.add_scenario(game_day_id=gd.id, name="s1", complexity=ScenarioComplexity.BASIC)
        gaps = eng.identify_coverage_gaps()
        assert any("sparse-gd" in g for g in gaps)

    def test_no_advanced_scenarios(self):
        eng = _engine(min_scenarios_per_day=1)
        gd = eng.create_game_day(name="basic-gd", scheduled_date="2026-02-20")
        eng.add_scenario(game_day_id=gd.id, name="s1", complexity=ScenarioComplexity.BASIC)
        gaps = eng.identify_coverage_gaps()
        assert any("EXPERT" in g or "EXTREME" in g for g in gaps)

    def test_no_recent_game_day(self):
        eng = _engine(min_scenarios_per_day=0)
        gd = eng.create_game_day(name="old-gd", scheduled_date="2025-01-01")
        eng.add_scenario(
            game_day_id=gd.id,
            name="s1",
            complexity=ScenarioComplexity.EXPERT,
        )
        gaps = eng.identify_coverage_gaps()
        assert any("90 days" in g for g in gaps)


# ===========================================================================
# TrackActionItems
# ===========================================================================


class TestTrackActionItems:
    """Test GameDayPlanner.track_action_items."""

    def test_completed_with_lessons(self):
        eng = _engine()
        gd = eng.create_game_day(name="completed-gd")
        gd.status = GameDayStatus.COMPLETED
        gd.lessons_learned = ["Improve alert routing", "Update runbook for DB failover"]
        items = eng.track_action_items()
        assert len(items) == 2
        assert items[0]["game_day_name"] == "completed-gd"
        assert items[0]["action_item"] == "Improve alert routing"
        assert items[1]["action_item"] == "Update runbook for DB failover"

    def test_non_completed_excluded(self):
        eng = _engine()
        gd = eng.create_game_day(name="planning-gd")
        gd.lessons_learned = ["Should not appear"]
        items = eng.track_action_items()
        assert len(items) == 0


# ===========================================================================
# GenerateGameDayReport
# ===========================================================================


class TestGenerateGameDayReport:
    """Test GameDayPlanner.generate_game_day_report."""

    def test_basic_report(self):
        eng = _engine(min_scenarios_per_day=1)
        gd = eng.create_game_day(name="report-gd", scheduled_date="2026-02-20")
        s = eng.add_scenario(
            game_day_id=gd.id,
            name="s1",
            complexity=ScenarioComplexity.INTERMEDIATE,
        )
        eng.score_scenario(s.id, score=75.0)
        report = eng.generate_game_day_report()
        assert isinstance(report, GameDayReport)
        assert report.total_game_days == 1
        assert report.total_scenarios == 1
        assert report.avg_score == 75.0
        assert report.by_status["planning"] == 1
        assert report.by_complexity["intermediate"] == 1
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_game_day_report()
        assert report.total_game_days == 0
        assert report.total_scenarios == 0
        assert report.avg_score == 0.0
        assert len(report.recommendations) >= 1  # "No game days planned"


# ===========================================================================
# ClearData
# ===========================================================================


class TestClearData:
    """Test GameDayPlanner.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        gd = eng.create_game_day(name="temp")
        eng.add_scenario(game_day_id=gd.id, name="s1", complexity=ScenarioComplexity.BASIC)
        eng.clear_data()
        assert len(eng.list_game_days()) == 0
        stats = eng.get_stats()
        assert stats["total_game_days"] == 0
        assert stats["total_scenarios"] == 0


# ===========================================================================
# GetStats
# ===========================================================================


class TestGetStats:
    """Test GameDayPlanner.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_game_days"] == 0
        assert stats["total_scenarios"] == 0
        assert stats["unique_teams"] == 0
        assert stats["status_distribution"] == {}
        assert stats["complexity_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        gd = eng.create_game_day(name="stats-gd", teams=["alpha", "beta"])
        eng.add_scenario(game_day_id=gd.id, name="s1", complexity=ScenarioComplexity.BASIC)
        eng.add_scenario(game_day_id=gd.id, name="s2", complexity=ScenarioComplexity.EXPERT)
        stats = eng.get_stats()
        assert stats["total_game_days"] == 1
        assert stats["total_scenarios"] == 2
        assert stats["unique_teams"] == 2
        assert stats["status_distribution"]["planning"] == 1
        assert stats["complexity_distribution"]["basic"] == 1
        assert stats["complexity_distribution"]["expert"] == 1
