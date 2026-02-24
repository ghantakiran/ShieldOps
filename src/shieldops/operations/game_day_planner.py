"""Game Day Planner — plan and manage resilience game days with scenarios, teams, and scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GameDayStatus(StrEnum):
    PLANNING = "planning"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ScenarioComplexity(StrEnum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"
    EXTREME = "extreme"


class ObjectiveType(StrEnum):
    DETECTION_TIME = "detection_time"
    RECOVERY_TIME = "recovery_time"
    COMMUNICATION = "communication"
    ESCALATION = "escalation"
    DOCUMENTATION = "documentation"


# --- Models ---


class GameDayPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    status: GameDayStatus = GameDayStatus.PLANNING
    scheduled_date: str = ""
    teams: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    lessons_learned: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class GameDayScenario(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    game_day_id: str = ""
    name: str = ""
    complexity: ScenarioComplexity = ScenarioComplexity.BASIC
    description: str = ""
    target_service: str = ""
    expected_outcome: str = ""
    actual_outcome: str = ""
    score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class GameDayReport(BaseModel):
    total_game_days: int = 0
    total_scenarios: int = 0
    avg_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_complexity: dict[str, int] = Field(default_factory=dict)
    coverage_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class GameDayPlanner:
    """Plan and manage resilience game days with scenarios, teams, and scoring."""

    def __init__(
        self,
        max_game_days: int = 10000,
        min_scenarios_per_day: int = 3,
    ) -> None:
        self._max_game_days = max_game_days
        self._min_scenarios_per_day = min_scenarios_per_day
        self._game_days: list[GameDayPlan] = []
        self._scenarios: list[GameDayScenario] = []
        logger.info(
            "game_day_planner.initialized",
            max_game_days=max_game_days,
            min_scenarios_per_day=min_scenarios_per_day,
        )

    def create_game_day(
        self,
        name: str,
        scheduled_date: str = "",
        teams: list[str] | None = None,
        objectives: list[str] | None = None,
    ) -> GameDayPlan:
        """Create and store a new game day plan."""
        plan = GameDayPlan(
            name=name,
            scheduled_date=scheduled_date,
            teams=teams or [],
            objectives=objectives or [],
        )
        self._game_days.append(plan)
        if len(self._game_days) > self._max_game_days:
            self._game_days = self._game_days[-self._max_game_days :]
        logger.info(
            "game_day_planner.game_day_created",
            gd_id=plan.id,
            name=name,
            scheduled_date=scheduled_date,
        )
        return plan

    def get_game_day(self, gd_id: str) -> GameDayPlan | None:
        """Retrieve a single game day plan by ID."""
        for gd in self._game_days:
            if gd.id == gd_id:
                return gd
        return None

    def list_game_days(
        self,
        status: GameDayStatus | None = None,
        limit: int = 100,
    ) -> list[GameDayPlan]:
        """List game days with optional status filtering."""
        results = list(self._game_days)
        if status is not None:
            results = [gd for gd in results if gd.status == status]
        return results[-limit:]

    def add_scenario(
        self,
        game_day_id: str,
        name: str,
        complexity: ScenarioComplexity = ScenarioComplexity.BASIC,
        description: str = "",
        target_service: str = "",
        expected_outcome: str = "",
    ) -> GameDayScenario | None:
        """Add a scenario to a game day. Returns None if game day not found."""
        game_day = self.get_game_day(game_day_id)
        if game_day is None:
            return None
        scenario = GameDayScenario(
            game_day_id=game_day_id,
            name=name,
            complexity=complexity,
            description=description,
            target_service=target_service,
            expected_outcome=expected_outcome,
        )
        self._scenarios.append(scenario)
        game_day.scenarios.append(scenario.id)
        logger.info(
            "game_day_planner.scenario_added",
            scenario_id=scenario.id,
            game_day_id=game_day_id,
            name=name,
            complexity=complexity,
        )
        return scenario

    def score_scenario(
        self,
        scenario_id: str,
        score: float,
        actual_outcome: str = "",
    ) -> GameDayScenario | None:
        """Update a scenario's score and actual outcome."""
        for s in self._scenarios:
            if s.id == scenario_id:
                s.score = score
                s.actual_outcome = actual_outcome
                logger.info(
                    "game_day_planner.scenario_scored",
                    scenario_id=scenario_id,
                    score=score,
                )
                return s
        return None

    def calculate_team_readiness(self) -> dict[str, Any]:
        """Calculate readiness scores per team based on associated scenario scores."""
        team_scores: dict[str, list[float]] = {}
        for gd in self._game_days:
            gd_scenarios = [s for s in self._scenarios if s.id in gd.scenarios]
            for team in gd.teams:
                if team not in team_scores:
                    team_scores[team] = []
                for s in gd_scenarios:
                    team_scores[team].append(s.score)

        result_scores: dict[str, float] = {}
        for team, scores in team_scores.items():
            result_scores[team] = round(sum(scores) / len(scores), 2) if scores else 0.0

        all_scores = list(result_scores.values())
        overall_readiness = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0

        logger.info(
            "game_day_planner.team_readiness_calculated",
            team_count=len(result_scores),
            overall_readiness=overall_readiness,
        )
        return {
            "team_scores": result_scores,
            "overall_readiness": overall_readiness,
        }

    def identify_coverage_gaps(self) -> list[str]:
        """Identify coverage gaps in game day planning."""
        gaps: list[str] = []

        # Check if any game day has fewer scenarios than minimum
        for gd in self._game_days:
            if len(gd.scenarios) < self._min_scenarios_per_day:
                gaps.append(
                    f"Game day '{gd.name}' has {len(gd.scenarios)} scenarios "
                    f"(minimum: {self._min_scenarios_per_day})"
                )

        # Check if no EXPERT or EXTREME scenarios exist
        has_advanced = any(
            s.complexity in (ScenarioComplexity.EXPERT, ScenarioComplexity.EXTREME)
            for s in self._scenarios
        )
        if not has_advanced:
            gaps.append("No EXPERT or EXTREME complexity scenarios — add advanced scenarios")

        # Check if no game day in last 90 days
        now = time.time()
        ninety_days_ago = now - (90 * 24 * 3600)
        has_recent = False
        for gd in self._game_days:
            if gd.scheduled_date:
                try:
                    # Parse ISO date string
                    from datetime import datetime

                    dt = datetime.fromisoformat(gd.scheduled_date)
                    if dt.timestamp() >= ninety_days_ago:
                        has_recent = True
                        break
                except (ValueError, TypeError):
                    pass
        if not has_recent and self._game_days:
            gaps.append("No game day scheduled in the last 90 days — plan a new game day")

        logger.info(
            "game_day_planner.coverage_gaps_identified",
            gap_count=len(gaps),
        )
        return gaps

    def track_action_items(self) -> list[dict[str, Any]]:
        """Return action items from lessons learned of completed game days."""
        items: list[dict[str, Any]] = []
        for gd in self._game_days:
            if gd.status == GameDayStatus.COMPLETED:
                for lesson in gd.lessons_learned:
                    items.append(
                        {
                            "game_day_id": gd.id,
                            "game_day_name": gd.name,
                            "action_item": lesson,
                        }
                    )
        logger.info(
            "game_day_planner.action_items_tracked",
            item_count=len(items),
        )
        return items

    def generate_game_day_report(self) -> GameDayReport:
        """Generate a comprehensive game day report."""
        total_game_days = len(self._game_days)
        total_scenarios = len(self._scenarios)

        by_status: dict[str, int] = {}
        for gd in self._game_days:
            key = gd.status.value
            by_status[key] = by_status.get(key, 0) + 1

        by_complexity: dict[str, int] = {}
        score_sum = 0.0
        scored_count = 0
        for s in self._scenarios:
            key = s.complexity.value
            by_complexity[key] = by_complexity.get(key, 0) + 1
            if s.score > 0:
                score_sum += s.score
                scored_count += 1

        avg_score = round(score_sum / scored_count, 2) if scored_count > 0 else 0.0

        coverage_gaps = self.identify_coverage_gaps()

        recommendations: list[str] = []
        if total_game_days == 0:
            recommendations.append("No game days planned — create your first game day")
        if total_scenarios == 0 and total_game_days > 0:
            recommendations.append("No scenarios defined — add scenarios to game days")
        if avg_score < 50.0 and scored_count > 0:
            recommendations.append(
                f"Average score is {avg_score}% — focus on improving team performance"
            )
        if coverage_gaps:
            recommendations.append(
                f"{len(coverage_gaps)} coverage gap(s) identified — review and address"
            )

        report = GameDayReport(
            total_game_days=total_game_days,
            total_scenarios=total_scenarios,
            avg_score=avg_score,
            by_status=by_status,
            by_complexity=by_complexity,
            coverage_gaps=coverage_gaps,
            recommendations=recommendations,
        )
        logger.info(
            "game_day_planner.report_generated",
            total_game_days=total_game_days,
            total_scenarios=total_scenarios,
            avg_score=avg_score,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored game days and scenarios."""
        self._game_days.clear()
        self._scenarios.clear()
        logger.info("game_day_planner.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about stored game days."""
        statuses: dict[str, int] = {}
        complexities: dict[str, int] = {}
        teams: set[str] = set()
        for gd in self._game_days:
            statuses[gd.status.value] = statuses.get(gd.status.value, 0) + 1
            for t in gd.teams:
                teams.add(t)
        for s in self._scenarios:
            complexities[s.complexity.value] = complexities.get(s.complexity.value, 0) + 1
        return {
            "total_game_days": len(self._game_days),
            "total_scenarios": len(self._scenarios),
            "unique_teams": len(teams),
            "status_distribution": statuses,
            "complexity_distribution": complexities,
        }
