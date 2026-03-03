"""Blameless Postmortem Enforcer — enforce quality blameless postmortems."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PostmortemQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    MISSING = "missing"


class ActionItemStatus(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    OVERDUE = "overdue"
    BLOCKED = "blocked"
    NOT_STARTED = "not_started"


class LearningCategory(StrEnum):
    PROCESS = "process"
    TECHNICAL = "technical"
    COMMUNICATION = "communication"
    TOOLING = "tooling"
    CULTURE = "culture"


# --- Models ---


class PostmortemRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    team: str = ""
    quality: PostmortemQuality = PostmortemQuality.ADEQUATE
    action_item_status: ActionItemStatus = ActionItemStatus.NOT_STARTED
    learning_category: LearningCategory = LearningCategory.PROCESS
    quality_score: float = 0.0
    action_items_count: int = 0
    created_at: float = Field(default_factory=time.time)


class PostmortemAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    learning_category: LearningCategory = LearningCategory.PROCESS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PostmortemReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_quality_score: float = 0.0
    by_quality: dict[str, int] = Field(default_factory=dict)
    by_action_status: dict[str, int] = Field(default_factory=dict)
    by_learning: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class BlamelessPostmortemEnforcer:
    """Enforce blameless postmortem standards and track action item completion."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[PostmortemRecord] = []
        self._analyses: list[PostmortemAnalysis] = []
        logger.info(
            "blameless_postmortem_enforcer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_postmortem(
        self,
        incident_id: str,
        team: str = "",
        quality: PostmortemQuality = PostmortemQuality.ADEQUATE,
        action_item_status: ActionItemStatus = ActionItemStatus.NOT_STARTED,
        learning_category: LearningCategory = LearningCategory.PROCESS,
        quality_score: float = 0.0,
        action_items_count: int = 0,
    ) -> PostmortemRecord:
        record = PostmortemRecord(
            incident_id=incident_id,
            team=team,
            quality=quality,
            action_item_status=action_item_status,
            learning_category=learning_category,
            quality_score=quality_score,
            action_items_count=action_items_count,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "blameless_postmortem_enforcer.postmortem_recorded",
            record_id=record.id,
            incident_id=incident_id,
            quality=quality.value,
            learning_category=learning_category.value,
        )
        return record

    def get_postmortem(self, record_id: str) -> PostmortemRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_postmortems(
        self,
        quality: PostmortemQuality | None = None,
        action_item_status: ActionItemStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PostmortemRecord]:
        results = list(self._records)
        if quality is not None:
            results = [r for r in results if r.quality == quality]
        if action_item_status is not None:
            results = [r for r in results if r.action_item_status == action_item_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        incident_id: str,
        learning_category: LearningCategory = LearningCategory.PROCESS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PostmortemAnalysis:
        analysis = PostmortemAnalysis(
            incident_id=incident_id,
            learning_category=learning_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "blameless_postmortem_enforcer.analysis_added",
            incident_id=incident_id,
            learning_category=learning_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by quality; return count and avg quality_score."""
        quality_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.quality.value
            quality_data.setdefault(key, []).append(r.quality_score)
        result: dict[str, Any] = {}
        for quality, scores in quality_data.items():
            result[quality] = {
                "count": len(scores),
                "avg_quality_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_postmortem_gaps(self) -> list[dict[str, Any]]:
        """Return records where quality_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.quality_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "quality": r.quality.value,
                        "quality_score": r.quality_score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["quality_score"])

    def rank_by_quality(self) -> list[dict[str, Any]]:
        """Group by team, avg quality_score, sort ascending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_quality_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_quality_score"])
        return results

    def detect_postmortem_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> PostmortemReport:
        by_quality: dict[str, int] = {}
        by_action_status: dict[str, int] = {}
        by_learning: dict[str, int] = {}
        for r in self._records:
            by_quality[r.quality.value] = by_quality.get(r.quality.value, 0) + 1
            by_action_status[r.action_item_status.value] = (
                by_action_status.get(r.action_item_status.value, 0) + 1
            )
            by_learning[r.learning_category.value] = (
                by_learning.get(r.learning_category.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.quality_score < self._threshold)
        scores = [r.quality_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_postmortem_gaps()
        top_gaps = [o["incident_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} postmortem(s) below quality threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg quality score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Postmortem quality is healthy")
        return PostmortemReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_quality_score=avg_score,
            by_quality=by_quality,
            by_action_status=by_action_status,
            by_learning=by_learning,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("blameless_postmortem_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        quality_dist: dict[str, int] = {}
        for r in self._records:
            key = r.quality.value
            quality_dist[key] = quality_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "quality_distribution": quality_dist,
            "unique_teams": len({r.team for r in self._records}),
        }
