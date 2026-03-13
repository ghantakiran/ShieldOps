"""Collaboration Pattern Analyzer —
analyze collaboration density, detect gaps,
rank teams by cross-team engagement."""

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
    CODE_REVIEW = "code_review"
    PAIRING = "pairing"
    INCIDENT_RESPONSE = "incident_response"
    PLANNING = "planning"


class PatternHealth(StrEnum):
    THRIVING = "thriving"
    ADEQUATE = "adequate"
    FRAGMENTED = "fragmented"
    SILOED = "siloed"


class EngagementLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


# --- Models ---


class CollaborationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    partner_team_id: str = ""
    collab_type: CollaborationType = CollaborationType.CODE_REVIEW
    health: PatternHealth = PatternHealth.ADEQUATE
    engagement: EngagementLevel = EngagementLevel.MEDIUM
    interaction_count: int = 0
    quality_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CollaborationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    density_score: float = 0.0
    health: PatternHealth = PatternHealth.ADEQUATE
    partner_count: int = 0
    total_interactions: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CollaborationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_quality: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    by_engagement: dict[str, int] = Field(default_factory=dict)
    top_collaborators: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CollaborationPatternAnalyzer:
    """Analyze collaboration density, detect gaps,
    rank teams by cross-team engagement."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CollaborationRecord] = []
        self._analyses: dict[str, CollaborationAnalysis] = {}
        logger.info(
            "collaboration_pattern_analyzer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        team_id: str = "",
        partner_team_id: str = "",
        collab_type: CollaborationType = (CollaborationType.CODE_REVIEW),
        health: PatternHealth = PatternHealth.ADEQUATE,
        engagement: EngagementLevel = (EngagementLevel.MEDIUM),
        interaction_count: int = 0,
        quality_score: float = 0.0,
        description: str = "",
    ) -> CollaborationRecord:
        record = CollaborationRecord(
            team_id=team_id,
            partner_team_id=partner_team_id,
            collab_type=collab_type,
            health=health,
            engagement=engagement,
            interaction_count=interaction_count,
            quality_score=quality_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "collaboration_pattern.record_added",
            record_id=record.id,
            team_id=team_id,
        )
        return record

    def process(self, key: str) -> CollaborationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        team_recs = [r for r in self._records if r.team_id == rec.team_id]
        partners = {r.partner_team_id for r in team_recs}
        total = sum(r.interaction_count for r in team_recs)
        density = round(total / max(len(partners), 1), 2)
        analysis = CollaborationAnalysis(
            team_id=rec.team_id,
            density_score=density,
            health=rec.health,
            partner_count=len(partners),
            total_interactions=total,
            description=(f"Team {rec.team_id} density={density}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CollaborationReport:
        by_t: dict[str, int] = {}
        by_h: dict[str, int] = {}
        by_e: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.collab_type.value
            by_t[k] = by_t.get(k, 0) + 1
            k2 = r.health.value
            by_h[k2] = by_h.get(k2, 0) + 1
            k3 = r.engagement.value
            by_e[k3] = by_e.get(k3, 0) + 1
            scores.append(r.quality_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        team_counts: dict[str, int] = {}
        for r in self._records:
            team_counts[r.team_id] = team_counts.get(r.team_id, 0) + r.interaction_count
        top = sorted(
            team_counts,
            key=lambda x: team_counts[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        siloed = by_h.get("siloed", 0)
        if siloed > 0:
            recs.append(f"{siloed} siloed patterns detected")
        if not recs:
            recs.append("Collaboration patterns are healthy")
        return CollaborationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_quality=avg,
            by_type=by_t,
            by_health=by_h,
            by_engagement=by_e,
            top_collaborators=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        t_dist: dict[str, int] = {}
        for r in self._records:
            k = r.collab_type.value
            t_dist[k] = t_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "type_distribution": t_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("collaboration_pattern_analyzer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def analyze_collaboration_density(
        self,
    ) -> list[dict[str, Any]]:
        """Compute collaboration density per team."""
        team_partners: dict[str, set[str]] = {}
        team_interactions: dict[str, int] = {}
        for r in self._records:
            team_partners.setdefault(r.team_id, set()).add(r.partner_team_id)
            team_interactions[r.team_id] = team_interactions.get(r.team_id, 0) + r.interaction_count
        results: list[dict[str, Any]] = []
        for tid, partners in team_partners.items():
            total = team_interactions.get(tid, 0)
            density = round(total / max(len(partners), 1), 2)
            results.append(
                {
                    "team_id": tid,
                    "density": density,
                    "partners": len(partners),
                    "interactions": total,
                }
            )
        results.sort(
            key=lambda x: x["density"],
            reverse=True,
        )
        return results

    def detect_collaboration_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Detect teams with collaboration gaps."""
        team_engagement: dict[str, list[str]] = {}
        for r in self._records:
            team_engagement.setdefault(r.team_id, []).append(r.engagement.value)
        results: list[dict[str, Any]] = []
        for tid, levels in team_engagement.items():
            low_count = sum(1 for lv in levels if lv in ("low", "none"))
            ratio = round(low_count / len(levels), 2)
            if ratio > 0.3:
                results.append(
                    {
                        "team_id": tid,
                        "gap_ratio": ratio,
                        "low_engagements": low_count,
                        "total": len(levels),
                    }
                )
        results.sort(
            key=lambda x: x["gap_ratio"],
            reverse=True,
        )
        return results

    def rank_teams_by_cross_team_engagement(
        self,
    ) -> list[dict[str, Any]]:
        """Rank teams by cross-team engagement."""
        team_partners: dict[str, set[str]] = {}
        team_interactions: dict[str, int] = {}
        for r in self._records:
            team_partners.setdefault(r.team_id, set()).add(r.partner_team_id)
            team_interactions[r.team_id] = team_interactions.get(r.team_id, 0) + r.interaction_count
        results: list[dict[str, Any]] = []
        for tid, partners in team_partners.items():
            score = round(
                len(partners) * team_interactions.get(tid, 0),
                2,
            )
            results.append(
                {
                    "team_id": tid,
                    "engagement_score": score,
                    "partner_count": len(partners),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["engagement_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
