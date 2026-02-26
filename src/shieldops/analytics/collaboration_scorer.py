"""Cross-Team Collaboration Scorer — measure and score collaboration across teams."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CollaborationType(StrEnum):
    INCIDENT_RESPONSE = "incident_response"
    DEPLOYMENT_SUPPORT = "deployment_support"
    KNOWLEDGE_SHARING = "knowledge_sharing"
    CODE_REVIEW = "code_review"
    JOINT_PLANNING = "joint_planning"


class CollaborationQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    NONE = "none"


class CollaborationFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    RARE = "rare"


# --- Models ---


class CollaborationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_name: str = ""
    collab_type: CollaborationType = CollaborationType.INCIDENT_RESPONSE
    quality: CollaborationQuality = CollaborationQuality.ADEQUATE
    frequency: CollaborationFrequency = CollaborationFrequency.WEEKLY
    collab_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CollaborationMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    collab_type: CollaborationType = CollaborationType.INCIDENT_RESPONSE
    quality: CollaborationQuality = CollaborationQuality.ADEQUATE
    score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CollaborationScorerReport(BaseModel):
    total_collaborations: int = 0
    total_metrics: int = 0
    avg_collab_score_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    siloed_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CrossTeamCollaborationScorer:
    """Measure and score collaboration across teams."""

    def __init__(
        self,
        max_records: int = 200000,
        min_score: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_score = min_score
        self._records: list[CollaborationRecord] = []
        self._metrics: list[CollaborationMetric] = []
        logger.info(
            "collaboration_scorer.initialized",
            max_records=max_records,
            min_score=min_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_collaboration(
        self,
        team_name: str,
        collab_type: CollaborationType = CollaborationType.INCIDENT_RESPONSE,
        quality: CollaborationQuality = CollaborationQuality.ADEQUATE,
        frequency: CollaborationFrequency = CollaborationFrequency.WEEKLY,
        collab_score: float = 0.0,
        details: str = "",
    ) -> CollaborationRecord:
        record = CollaborationRecord(
            team_name=team_name,
            collab_type=collab_type,
            quality=quality,
            frequency=frequency,
            collab_score=collab_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "collaboration_scorer.recorded",
            record_id=record.id,
            team_name=team_name,
            quality=quality.value,
        )
        return record

    def get_collaboration(self, record_id: str) -> CollaborationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_collaborations(
        self,
        team_name: str | None = None,
        collab_type: CollaborationType | None = None,
        limit: int = 50,
    ) -> list[CollaborationRecord]:
        results = list(self._records)
        if team_name is not None:
            results = [r for r in results if r.team_name == team_name]
        if collab_type is not None:
            results = [r for r in results if r.collab_type == collab_type]
        return results[-limit:]

    def add_metric(
        self,
        metric_name: str,
        collab_type: CollaborationType = CollaborationType.INCIDENT_RESPONSE,
        quality: CollaborationQuality = CollaborationQuality.ADEQUATE,
        score: float = 0.0,
        description: str = "",
    ) -> CollaborationMetric:
        metric = CollaborationMetric(
            metric_name=metric_name,
            collab_type=collab_type,
            quality=quality,
            score=score,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "collaboration_scorer.metric_added",
            metric_name=metric_name,
            score=score,
        )
        return metric

    # -- domain operations -----------------------------------------------

    def analyze_team_collaboration(self, team_name: str) -> dict[str, Any]:
        """Analyze collaboration for a specific team."""
        records = [r for r in self._records if r.team_name == team_name]
        if not records:
            return {"team_name": team_name, "status": "no_data"}
        avg_score = round(sum(r.collab_score for r in records) / len(records), 2)
        return {
            "team_name": team_name,
            "total": len(records),
            "avg_score": avg_score,
            "meets_threshold": avg_score >= self._min_score,
        }

    def identify_siloed_teams(self) -> list[dict[str, Any]]:
        """Find teams with poor or no collaboration quality."""
        siloed = {CollaborationQuality.POOR, CollaborationQuality.NONE}
        team_counts: dict[str, int] = {}
        for r in self._records:
            if r.quality in siloed:
                team_counts[r.team_name] = team_counts.get(r.team_name, 0) + 1
        results: list[dict[str, Any]] = []
        for team, count in team_counts.items():
            if count > 1:
                results.append({"team_name": team, "siloed_count": count})
        results.sort(key=lambda x: x["siloed_count"], reverse=True)
        return results

    def rank_by_collaboration_score(self) -> list[dict[str, Any]]:
        """Rank teams by average collaboration score descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team_name, []).append(r.collab_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append({"team_name": team, "avg_collab_score": avg})
        results.sort(key=lambda x: x["avg_collab_score"], reverse=True)
        return results

    def detect_collaboration_trends(self) -> list[dict[str, Any]]:
        """Detect trends for teams with sufficient data."""
        team_records: dict[str, list[CollaborationRecord]] = {}
        for r in self._records:
            team_records.setdefault(r.team_name, []).append(r)
        results: list[dict[str, Any]] = []
        for team, records in team_records.items():
            if len(records) > 3:
                scores = [r.collab_score for r in records]
                trend = "improving" if scores[-1] > scores[0] else "declining"
                results.append(
                    {
                        "team_name": team,
                        "record_count": len(records),
                        "trend": trend,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CollaborationScorerReport:
        by_type: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        for r in self._records:
            by_type[r.collab_type.value] = by_type.get(r.collab_type.value, 0) + 1
            by_quality[r.quality.value] = by_quality.get(r.quality.value, 0) + 1
        avg_score = (
            round(
                sum(r.collab_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        siloed = {CollaborationQuality.POOR, CollaborationQuality.NONE}
        siloed_count = sum(1 for r in self._records if r.quality in siloed)
        recs: list[str] = []
        if siloed_count > 0:
            recs.append(f"{siloed_count} collaboration(s) with poor/none quality")
        low_score = sum(1 for r in self._records if r.collab_score < self._min_score)
        if low_score > 0:
            recs.append(f"{low_score} collaboration(s) below minimum score")
        if not recs:
            recs.append("Collaboration scores within acceptable limits")
        return CollaborationScorerReport(
            total_collaborations=len(self._records),
            total_metrics=len(self._metrics),
            avg_collab_score_pct=avg_score,
            by_type=by_type,
            by_quality=by_quality,
            siloed_count=siloed_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("collaboration_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.collab_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_collaborations": len(self._records),
            "total_metrics": len(self._metrics),
            "min_score": self._min_score,
            "type_distribution": type_dist,
            "unique_teams": len({r.team_name for r in self._records}),
        }
