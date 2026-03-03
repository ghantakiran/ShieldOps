"""Team Collaboration Scorer — measure and improve team collaboration health."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CollaborationDimension(StrEnum):
    COMMUNICATION = "communication"
    CODE_REVIEW = "code_review"
    INCIDENT_RESPONSE = "incident_response"
    KNOWLEDGE_SHARING = "knowledge_sharing"
    PLANNING = "planning"


class HealthStatus(StrEnum):
    THRIVING = "thriving"
    HEALTHY = "healthy"
    DEVELOPING = "developing"
    STRUGGLING = "struggling"
    DYSFUNCTIONAL = "dysfunctional"


class InteractionType(StrEnum):
    SYNC = "sync"
    ASYNC = "async"
    PAIRING = "pairing"
    REVIEW = "review"
    HANDOFF = "handoff"


# --- Models ---


class CollaborationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team: str = ""
    participant: str = ""
    dimension: CollaborationDimension = CollaborationDimension.COMMUNICATION
    health_status: HealthStatus = HealthStatus.HEALTHY
    interaction_type: InteractionType = InteractionType.SYNC
    collaboration_score: float = 0.0
    interaction_count: int = 0
    created_at: float = Field(default_factory=time.time)


class CollaborationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team: str = ""
    dimension: CollaborationDimension = CollaborationDimension.COMMUNICATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CollaborationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_collaboration_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    by_interaction: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamCollaborationScorer:
    """Score and track team collaboration health across dimensions."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[CollaborationRecord] = []
        self._analyses: list[CollaborationAnalysis] = []
        logger.info(
            "team_collaboration_scorer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_collaboration(
        self,
        team: str,
        participant: str = "",
        dimension: CollaborationDimension = CollaborationDimension.COMMUNICATION,
        health_status: HealthStatus = HealthStatus.HEALTHY,
        interaction_type: InteractionType = InteractionType.SYNC,
        collaboration_score: float = 0.0,
        interaction_count: int = 0,
    ) -> CollaborationRecord:
        record = CollaborationRecord(
            team=team,
            participant=participant,
            dimension=dimension,
            health_status=health_status,
            interaction_type=interaction_type,
            collaboration_score=collaboration_score,
            interaction_count=interaction_count,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "team_collaboration_scorer.collaboration_recorded",
            record_id=record.id,
            team=team,
            dimension=dimension.value,
            health_status=health_status.value,
        )
        return record

    def get_collaboration(self, record_id: str) -> CollaborationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_collaborations(
        self,
        dimension: CollaborationDimension | None = None,
        health_status: HealthStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CollaborationRecord]:
        results = list(self._records)
        if dimension is not None:
            results = [r for r in results if r.dimension == dimension]
        if health_status is not None:
            results = [r for r in results if r.health_status == health_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        team: str,
        dimension: CollaborationDimension = CollaborationDimension.COMMUNICATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CollaborationAnalysis:
        analysis = CollaborationAnalysis(
            team=team,
            dimension=dimension,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "team_collaboration_scorer.analysis_added",
            team=team,
            dimension=dimension.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by dimension; return count and avg collaboration_score."""
        dim_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.dimension.value
            dim_data.setdefault(key, []).append(r.collaboration_score)
        result: dict[str, Any] = {}
        for dim, scores in dim_data.items():
            result[dim] = {
                "count": len(scores),
                "avg_collaboration_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_collaboration_gaps(self) -> list[dict[str, Any]]:
        """Return records where collaboration_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.collaboration_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "team": r.team,
                        "dimension": r.dimension.value,
                        "collaboration_score": r.collaboration_score,
                        "participant": r.participant,
                    }
                )
        return sorted(results, key=lambda x: x["collaboration_score"])

    def rank_by_collaboration(self) -> list[dict[str, Any]]:
        """Group by team, avg collaboration_score, sort ascending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.collaboration_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_collaboration_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_collaboration_score"])
        return results

    def detect_collaboration_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> CollaborationReport:
        by_dimension: dict[str, int] = {}
        by_health: dict[str, int] = {}
        by_interaction: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.dimension.value] = by_dimension.get(r.dimension.value, 0) + 1
            by_health[r.health_status.value] = by_health.get(r.health_status.value, 0) + 1
            by_interaction[r.interaction_type.value] = (
                by_interaction.get(r.interaction_type.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.collaboration_score < self._threshold)
        scores = [r.collaboration_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_collaboration_gaps()
        top_gaps = [o["team"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} team(s) below collaboration threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg collaboration score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Team collaboration is healthy")
        return CollaborationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_collaboration_score=avg_score,
            by_dimension=by_dimension,
            by_health=by_health,
            by_interaction=by_interaction,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("team_collaboration_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dim_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dimension.value
            dim_dist[key] = dim_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "dimension_distribution": dim_dist,
            "unique_teams": len({r.team for r in self._records}),
        }
