"""Team Velocity Intelligence Engine —
track team velocity, detect anomalies,
rank teams by delivery consistency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VelocityMetric(StrEnum):
    STORY_POINTS = "story_points"
    TASKS_COMPLETED = "tasks_completed"
    DEPLOYMENTS = "deployments"
    INCIDENTS_RESOLVED = "incidents_resolved"


class TrendDirection(StrEnum):
    ACCELERATING = "accelerating"
    STABLE = "stable"
    DECELERATING = "decelerating"
    VOLATILE = "volatile"


class TeamSize(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    DISTRIBUTED = "distributed"


# --- Models ---


class TeamVelocityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    metric: VelocityMetric = VelocityMetric.STORY_POINTS
    trend: TrendDirection = TrendDirection.STABLE
    team_size: TeamSize = TeamSize.MEDIUM
    velocity_value: float = 0.0
    sprint_number: int = 0
    capacity: float = 1.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TeamVelocityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    avg_velocity: float = 0.0
    trend: TrendDirection = TrendDirection.STABLE
    consistency_score: float = 0.0
    sprint_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TeamVelocityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_velocity: float = 0.0
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    by_team_size: dict[str, int] = Field(default_factory=dict)
    top_teams: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamVelocityIntelligence:
    """Track team velocity, detect anomalies,
    rank teams by delivery consistency."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TeamVelocityRecord] = []
        self._analyses: dict[str, TeamVelocityAnalysis] = {}
        logger.info(
            "team_velocity_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        team_id: str = "",
        metric: VelocityMetric = (VelocityMetric.STORY_POINTS),
        trend: TrendDirection = TrendDirection.STABLE,
        team_size: TeamSize = TeamSize.MEDIUM,
        velocity_value: float = 0.0,
        sprint_number: int = 0,
        capacity: float = 1.0,
        description: str = "",
    ) -> TeamVelocityRecord:
        record = TeamVelocityRecord(
            team_id=team_id,
            metric=metric,
            trend=trend,
            team_size=team_size,
            velocity_value=velocity_value,
            sprint_number=sprint_number,
            capacity=capacity,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "team_velocity.record_added",
            record_id=record.id,
            team_id=team_id,
        )
        return record

    def process(self, key: str) -> TeamVelocityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        team_recs = [r for r in self._records if r.team_id == rec.team_id]
        vals = [r.velocity_value for r in team_recs]
        avg = round(sum(vals) / len(vals), 2) if vals else 0.0
        std = 0.0
        if len(vals) > 1:
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            std = var**0.5
        consistency = round(max(0.0, 100.0 - std), 2)
        analysis = TeamVelocityAnalysis(
            team_id=rec.team_id,
            avg_velocity=avg,
            trend=rec.trend,
            consistency_score=consistency,
            sprint_count=len(team_recs),
            description=(f"Team {rec.team_id} avg {avg}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TeamVelocityReport:
        by_m: dict[str, int] = {}
        by_t: dict[str, int] = {}
        by_s: dict[str, int] = {}
        vals: list[float] = []
        for r in self._records:
            k = r.metric.value
            by_m[k] = by_m.get(k, 0) + 1
            k2 = r.trend.value
            by_t[k2] = by_t.get(k2, 0) + 1
            k3 = r.team_size.value
            by_s[k3] = by_s.get(k3, 0) + 1
            vals.append(r.velocity_value)
        avg = round(sum(vals) / len(vals), 2) if vals else 0.0
        team_totals: dict[str, float] = {}
        for r in self._records:
            team_totals[r.team_id] = team_totals.get(r.team_id, 0.0) + r.velocity_value
        ranked = sorted(
            team_totals,
            key=lambda x: team_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        dec = by_t.get("decelerating", 0)
        if dec > 0:
            recs.append(f"{dec} decelerating trends detected")
        if not recs:
            recs.append("Velocity trends are healthy")
        return TeamVelocityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_velocity=avg,
            by_metric=by_m,
            by_trend=by_t,
            by_team_size=by_s,
            top_teams=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        m_dist: dict[str, int] = {}
        for r in self._records:
            k = r.metric.value
            m_dist[k] = m_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "metric_distribution": m_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("team_velocity_intelligence.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_velocity_trends(
        self,
    ) -> list[dict[str, Any]]:
        """Compute velocity trends per team."""
        team_vals: dict[str, list[float]] = {}
        for r in self._records:
            team_vals.setdefault(r.team_id, []).append(r.velocity_value)
        results: list[dict[str, Any]] = []
        for tid, vals in team_vals.items():
            avg = round(sum(vals) / len(vals), 2)
            trend = "stable"
            if len(vals) >= 2:
                if vals[-1] > vals[0] * 1.1:
                    trend = "accelerating"
                elif vals[-1] < vals[0] * 0.9:
                    trend = "decelerating"
            results.append(
                {
                    "team_id": tid,
                    "avg_velocity": avg,
                    "trend": trend,
                    "data_points": len(vals),
                }
            )
        results.sort(
            key=lambda x: x["avg_velocity"],
            reverse=True,
        )
        return results

    def detect_velocity_anomalies(
        self,
    ) -> list[dict[str, Any]]:
        """Detect anomalous velocity changes."""
        team_vals: dict[str, list[float]] = {}
        for r in self._records:
            team_vals.setdefault(r.team_id, []).append(r.velocity_value)
        results: list[dict[str, Any]] = []
        for tid, vals in team_vals.items():
            if len(vals) < 2:
                continue
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            std = var**0.5
            if std == 0:
                continue
            for v in vals:
                if abs(v - mean) > 2 * std:
                    results.append(
                        {
                            "team_id": tid,
                            "value": v,
                            "mean": round(mean, 2),
                            "std_dev": round(std, 2),
                            "deviation": round(
                                abs(v - mean) / std,
                                2,
                            ),
                        }
                    )
        results.sort(
            key=lambda x: x["deviation"],
            reverse=True,
        )
        return results

    def rank_teams_by_delivery_consistency(
        self,
    ) -> list[dict[str, Any]]:
        """Rank teams by consistency of delivery."""
        team_vals: dict[str, list[float]] = {}
        for r in self._records:
            team_vals.setdefault(r.team_id, []).append(r.velocity_value)
        results: list[dict[str, Any]] = []
        for tid, vals in team_vals.items():
            mean = sum(vals) / len(vals) if vals else 0
            var = sum((v - mean) ** 2 for v in vals) / len(vals) if vals else 0
            std = var**0.5
            consistency = round(max(0.0, 100.0 - std), 2)
            results.append(
                {
                    "team_id": tid,
                    "consistency_score": consistency,
                    "avg_velocity": round(mean, 2),
                    "sprints": len(vals),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["consistency_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
