"""Knowledge Contribution Tracker — track and analyze knowledge contributions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ContributionType(StrEnum):
    RUNBOOK = "runbook"
    PLAYBOOK = "playbook"
    DOCUMENTATION = "documentation"
    POSTMORTEM = "postmortem"
    TRAINING_MATERIAL = "training_material"


class ContributionQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    NEEDS_IMPROVEMENT = "needs_improvement"
    POOR = "poor"


class ContributionImpact(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"
    UNKNOWN = "unknown"


# --- Models ---


class ContributionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contributor_name: str = ""
    contribution_type: ContributionType = ContributionType.DOCUMENTATION
    quality: ContributionQuality = ContributionQuality.ADEQUATE
    impact: ContributionImpact = ContributionImpact.UNKNOWN
    quality_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ContributorProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile_name: str = ""
    contribution_type: ContributionType = ContributionType.DOCUMENTATION
    quality: ContributionQuality = ContributionQuality.ADEQUATE
    total_contributions: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContributionTrackerReport(BaseModel):
    total_contributions: int = 0
    total_profiles: int = 0
    avg_quality_score_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    top_contributor_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeContributionTracker:
    """Track and analyze knowledge contributions."""

    def __init__(
        self,
        max_records: int = 200000,
        min_quality_score: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_quality_score = min_quality_score
        self._records: list[ContributionRecord] = []
        self._profiles: list[ContributorProfile] = []
        logger.info(
            "contribution_tracker.initialized",
            max_records=max_records,
            min_quality_score=min_quality_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_contribution(
        self,
        contributor_name: str,
        contribution_type: ContributionType = ContributionType.DOCUMENTATION,
        quality: ContributionQuality = ContributionQuality.ADEQUATE,
        impact: ContributionImpact = ContributionImpact.UNKNOWN,
        quality_score: float = 0.0,
        details: str = "",
    ) -> ContributionRecord:
        record = ContributionRecord(
            contributor_name=contributor_name,
            contribution_type=contribution_type,
            quality=quality,
            impact=impact,
            quality_score=quality_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "contribution_tracker.recorded",
            record_id=record.id,
            contributor_name=contributor_name,
            quality=quality.value,
        )
        return record

    def get_contribution(self, record_id: str) -> ContributionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_contributions(
        self,
        contributor_name: str | None = None,
        contribution_type: ContributionType | None = None,
        limit: int = 50,
    ) -> list[ContributionRecord]:
        results = list(self._records)
        if contributor_name is not None:
            results = [r for r in results if r.contributor_name == contributor_name]
        if contribution_type is not None:
            results = [r for r in results if r.contribution_type == contribution_type]
        return results[-limit:]

    def add_contributor_profile(
        self,
        profile_name: str,
        contribution_type: ContributionType = ContributionType.DOCUMENTATION,
        quality: ContributionQuality = ContributionQuality.ADEQUATE,
        total_contributions: int = 0,
        description: str = "",
    ) -> ContributorProfile:
        profile = ContributorProfile(
            profile_name=profile_name,
            contribution_type=contribution_type,
            quality=quality,
            total_contributions=total_contributions,
            description=description,
        )
        self._profiles.append(profile)
        if len(self._profiles) > self._max_records:
            self._profiles = self._profiles[-self._max_records :]
        logger.info(
            "contribution_tracker.profile_added",
            profile_name=profile_name,
            total_contributions=total_contributions,
        )
        return profile

    # -- domain operations -----------------------------------------------

    def analyze_contribution_patterns(self, contributor_name: str) -> dict[str, Any]:
        """Analyze contribution patterns for a specific contributor."""
        records = [r for r in self._records if r.contributor_name == contributor_name]
        if not records:
            return {"contributor_name": contributor_name, "status": "no_data"}
        avg_score = round(sum(r.quality_score for r in records) / len(records), 2)
        return {
            "contributor_name": contributor_name,
            "total": len(records),
            "avg_score": avg_score,
            "meets_threshold": avg_score >= self._min_quality_score,
        }

    def identify_top_contributors(self) -> list[dict[str, Any]]:
        """Find contributors with excellent or good quality records."""
        top = {ContributionQuality.EXCELLENT, ContributionQuality.GOOD}
        contributor_counts: dict[str, int] = {}
        for r in self._records:
            if r.quality in top:
                contributor_counts[r.contributor_name] = (
                    contributor_counts.get(r.contributor_name, 0) + 1
                )
        results: list[dict[str, Any]] = []
        for name, count in contributor_counts.items():
            if count > 1:
                results.append({"contributor_name": name, "top_count": count})
        results.sort(key=lambda x: x["top_count"], reverse=True)
        return results

    def rank_by_impact(self) -> list[dict[str, Any]]:
        """Rank contributors by average quality score descending."""
        contributor_scores: dict[str, list[float]] = {}
        for r in self._records:
            contributor_scores.setdefault(r.contributor_name, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for name, scores in contributor_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append({"contributor_name": name, "avg_quality_score": avg})
        results.sort(key=lambda x: x["avg_quality_score"], reverse=True)
        return results

    def detect_knowledge_gaps(self) -> list[dict[str, Any]]:
        """Detect knowledge gaps for contributors with sufficient data."""
        contributor_records: dict[str, list[ContributionRecord]] = {}
        for r in self._records:
            contributor_records.setdefault(r.contributor_name, []).append(r)
        results: list[dict[str, Any]] = []
        for name, records in contributor_records.items():
            if len(records) > 3:
                scores = [r.quality_score for r in records]
                gap = "widening" if scores[-1] < scores[0] else "narrowing"
                results.append(
                    {
                        "contributor_name": name,
                        "record_count": len(records),
                        "gap": gap,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ContributionTrackerReport:
        by_type: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        for r in self._records:
            by_type[r.contribution_type.value] = by_type.get(r.contribution_type.value, 0) + 1
            by_quality[r.quality.value] = by_quality.get(r.quality.value, 0) + 1
        avg_score = (
            round(
                sum(r.quality_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        top = {ContributionQuality.EXCELLENT, ContributionQuality.GOOD}
        top_count = sum(1 for r in self._records if r.quality in top)
        recs: list[str] = []
        low_quality = sum(1 for r in self._records if r.quality_score < self._min_quality_score)
        if low_quality > 0:
            recs.append(f"{low_quality} contribution(s) below minimum quality score")
        poor = sum(1 for r in self._records if r.quality == ContributionQuality.POOR)
        if poor > 0:
            recs.append(f"{poor} contribution(s) with poor quality")
        if not recs:
            recs.append("Knowledge contributions within acceptable limits")
        return ContributionTrackerReport(
            total_contributions=len(self._records),
            total_profiles=len(self._profiles),
            avg_quality_score_pct=avg_score,
            by_type=by_type,
            by_quality=by_quality,
            top_contributor_count=top_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._profiles.clear()
        logger.info("contribution_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.contribution_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_contributions": len(self._records),
            "total_profiles": len(self._profiles),
            "min_quality_score": self._min_quality_score,
            "type_distribution": type_dist,
            "unique_contributors": len({r.contributor_name for r in self._records}),
        }
