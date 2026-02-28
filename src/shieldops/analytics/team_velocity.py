"""Team Velocity Tracker — measure and track engineering team velocity metrics."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VelocityMetric(StrEnum):
    STORY_POINTS = "story_points"
    TASKS_COMPLETED = "tasks_completed"
    DEPLOYMENTS = "deployments"
    INCIDENTS_RESOLVED = "incidents_resolved"
    PULL_REQUESTS = "pull_requests"


class VelocityTrend(StrEnum):
    ACCELERATING = "accelerating"
    STABLE = "stable"
    DECELERATING = "decelerating"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


class SprintHealth(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    STRUGGLING = "struggling"
    CRITICAL = "critical"


# --- Models ---


class VelocityRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    team_name: str = ""
    metric: VelocityMetric = VelocityMetric.STORY_POINTS
    trend: VelocityTrend = VelocityTrend.STABLE
    sprint_health: SprintHealth = SprintHealth.ADEQUATE
    velocity_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class VelocityDataPoint(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    team_name: str = ""
    metric: VelocityMetric = VelocityMetric.STORY_POINTS
    sprint_health: SprintHealth = SprintHealth.ADEQUATE
    value: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TeamVelocityReport(BaseModel):
    total_records: int = 0
    total_data_points: int = 0
    avg_velocity_score: float = 0.0
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    underperforming_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamVelocityTracker:
    """Measure and track engineering team velocity metrics."""

    def __init__(
        self,
        max_records: int = 200000,
        min_velocity_score: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_velocity_score = min_velocity_score
        self._records: list[VelocityRecord] = []
        self._data_points: list[VelocityDataPoint] = []
        logger.info(
            "team_velocity_tracker.initialized",
            max_records=max_records,
            min_velocity_score=min_velocity_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_velocity(
        self,
        team_name: str,
        metric: VelocityMetric = VelocityMetric.STORY_POINTS,
        trend: VelocityTrend = VelocityTrend.STABLE,
        sprint_health: SprintHealth = SprintHealth.ADEQUATE,
        velocity_score: float = 0.0,
        details: str = "",
    ) -> VelocityRecord:
        record = VelocityRecord(
            team_name=team_name,
            metric=metric,
            trend=trend,
            sprint_health=sprint_health,
            velocity_score=velocity_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "team_velocity_tracker.recorded",
            record_id=record.id,
            team_name=team_name,
            velocity_score=velocity_score,
        )
        return record

    def get_velocity(self, record_id: str) -> VelocityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_velocities(
        self,
        team_name: str | None = None,
        metric: VelocityMetric | None = None,
        limit: int = 50,
    ) -> list[VelocityRecord]:
        results = list(self._records)
        if team_name is not None:
            results = [r for r in results if r.team_name == team_name]
        if metric is not None:
            results = [r for r in results if r.metric == metric]
        return results[-limit:]

    def add_data_point(
        self,
        team_name: str,
        metric: VelocityMetric = VelocityMetric.STORY_POINTS,
        sprint_health: SprintHealth = SprintHealth.ADEQUATE,
        value: float = 0.0,
        description: str = "",
    ) -> VelocityDataPoint:
        data_point = VelocityDataPoint(
            team_name=team_name,
            metric=metric,
            sprint_health=sprint_health,
            value=value,
            description=description,
        )
        self._data_points.append(data_point)
        if len(self._data_points) > self._max_records:
            self._data_points = self._data_points[-self._max_records :]
        logger.info(
            "team_velocity_tracker.data_point_added",
            team_name=team_name,
            value=value,
        )
        return data_point

    # -- domain operations -----------------------------------------------

    def analyze_velocity_by_team(self, team_name: str) -> dict[str, Any]:
        """Analyze velocity metrics for a specific team."""
        records = [r for r in self._records if r.team_name == team_name]
        if not records:
            return {"team_name": team_name, "status": "no_data"}
        avg_score = round(sum(r.velocity_score for r in records) / len(records), 2)
        return {
            "team_name": team_name,
            "total": len(records),
            "avg_velocity_score": avg_score,
            "meets_threshold": avg_score >= self._min_velocity_score,
        }

    def identify_underperforming_teams(self) -> list[dict[str, Any]]:
        """Find teams with velocity scores below the minimum threshold."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team_name, []).append(r.velocity_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            if avg < self._min_velocity_score:
                results.append({"team_name": team, "avg_velocity_score": avg})
        results.sort(key=lambda x: x["avg_velocity_score"])
        return results

    def rank_by_velocity_score(self) -> list[dict[str, Any]]:
        """Rank teams by average velocity score descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team_name, []).append(r.velocity_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append({"team_name": team, "avg_velocity_score": avg})
        results.sort(key=lambda x: x["avg_velocity_score"], reverse=True)
        return results

    def detect_velocity_trends(self) -> list[dict[str, Any]]:
        """Detect velocity trends for teams with sufficient data."""
        team_records: dict[str, list[VelocityRecord]] = {}
        for r in self._records:
            team_records.setdefault(r.team_name, []).append(r)
        results: list[dict[str, Any]] = []
        for team, records in team_records.items():
            if len(records) > 3:
                scores = [r.velocity_score for r in records]
                trend = "accelerating" if scores[-1] > scores[0] else "decelerating"
                results.append(
                    {
                        "team_name": team,
                        "record_count": len(records),
                        "trend": trend,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> TeamVelocityReport:
        by_metric: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        for r in self._records:
            by_metric[r.metric.value] = by_metric.get(r.metric.value, 0) + 1
            by_trend[r.trend.value] = by_trend.get(r.trend.value, 0) + 1
        avg_score = (
            round(
                sum(r.velocity_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        underperforming = sum(
            1 for r in self._records if r.velocity_score < self._min_velocity_score
        )
        recs: list[str] = []
        if underperforming > 0:
            recs.append(f"{underperforming} record(s) below minimum velocity score")
        struggling = {SprintHealth.STRUGGLING, SprintHealth.CRITICAL}
        struggling_count = sum(1 for r in self._records if r.sprint_health in struggling)
        if struggling_count > 0:
            recs.append(f"{struggling_count} sprint(s) in struggling/critical health")
        if not recs:
            recs.append("Team velocity within acceptable limits")
        return TeamVelocityReport(
            total_records=len(self._records),
            total_data_points=len(self._data_points),
            avg_velocity_score=avg_score,
            by_metric=by_metric,
            by_trend=by_trend,
            underperforming_count=underperforming,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._data_points.clear()
        logger.info("team_velocity_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        metric_dist: dict[str, int] = {}
        for r in self._records:
            key = r.metric.value
            metric_dist[key] = metric_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_data_points": len(self._data_points),
            "min_velocity_score": self._min_velocity_score,
            "metric_distribution": metric_dist,
            "unique_teams": len({r.team_name for r in self._records}),
        }
