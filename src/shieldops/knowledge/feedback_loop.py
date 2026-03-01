"""Knowledge Feedback Analyzer — analyze feedback on knowledge articles, identify poor content."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FeedbackType(StrEnum):
    HELPFUL = "helpful"
    OUTDATED = "outdated"
    INACCURATE = "inaccurate"
    INCOMPLETE = "incomplete"
    CONFUSING = "confusing"


class FeedbackSource(StrEnum):
    INCIDENT_RESPONSE = "incident_response"
    TRAINING = "training"
    ONBOARDING = "onboarding"
    SELF_SERVICE = "self_service"
    REVIEW = "review"


class ContentQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    NEEDS_REWRITE = "needs_rewrite"


# --- Models ---


class FeedbackRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    article_id: str = ""
    feedback_type: FeedbackType = FeedbackType.HELPFUL
    feedback_source: FeedbackSource = FeedbackSource.SELF_SERVICE
    content_quality: ContentQuality = ContentQuality.ADEQUATE
    satisfaction_score: float = 0.0
    reviewer: str = ""
    created_at: float = Field(default_factory=time.time)


class FeedbackSummary(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    summary_name: str = ""
    feedback_type: FeedbackType = FeedbackType.HELPFUL
    avg_satisfaction: float = 0.0
    total_feedbacks: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeFeedbackReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_summaries: int = 0
    reviewed_articles: int = 0
    avg_satisfaction_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    poor_articles: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeFeedbackAnalyzer:
    """Analyze feedback on knowledge articles, identify poor content, track satisfaction."""

    def __init__(
        self,
        max_records: int = 200000,
        min_satisfaction_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_satisfaction_score = min_satisfaction_score
        self._records: list[FeedbackRecord] = []
        self._summaries: list[FeedbackSummary] = []
        logger.info(
            "feedback_loop.initialized",
            max_records=max_records,
            min_satisfaction_score=min_satisfaction_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_feedback(
        self,
        article_id: str,
        feedback_type: FeedbackType = FeedbackType.HELPFUL,
        feedback_source: FeedbackSource = FeedbackSource.SELF_SERVICE,
        content_quality: ContentQuality = ContentQuality.ADEQUATE,
        satisfaction_score: float = 0.0,
        reviewer: str = "",
    ) -> FeedbackRecord:
        record = FeedbackRecord(
            article_id=article_id,
            feedback_type=feedback_type,
            feedback_source=feedback_source,
            content_quality=content_quality,
            satisfaction_score=satisfaction_score,
            reviewer=reviewer,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "feedback_loop.feedback_recorded",
            record_id=record.id,
            article_id=article_id,
            feedback_type=feedback_type.value,
            satisfaction_score=satisfaction_score,
        )
        return record

    def get_feedback(self, record_id: str) -> FeedbackRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_feedbacks(
        self,
        feedback_type: FeedbackType | None = None,
        feedback_source: FeedbackSource | None = None,
        reviewer: str | None = None,
        limit: int = 50,
    ) -> list[FeedbackRecord]:
        results = list(self._records)
        if feedback_type is not None:
            results = [r for r in results if r.feedback_type == feedback_type]
        if feedback_source is not None:
            results = [r for r in results if r.feedback_source == feedback_source]
        if reviewer is not None:
            results = [r for r in results if r.reviewer == reviewer]
        return results[-limit:]

    def add_summary(
        self,
        summary_name: str,
        feedback_type: FeedbackType = FeedbackType.HELPFUL,
        avg_satisfaction: float = 0.0,
        total_feedbacks: int = 0,
        description: str = "",
    ) -> FeedbackSummary:
        summary = FeedbackSummary(
            summary_name=summary_name,
            feedback_type=feedback_type,
            avg_satisfaction=avg_satisfaction,
            total_feedbacks=total_feedbacks,
            description=description,
        )
        self._summaries.append(summary)
        if len(self._summaries) > self._max_records:
            self._summaries = self._summaries[-self._max_records :]
        logger.info(
            "feedback_loop.summary_added",
            summary_name=summary_name,
            feedback_type=feedback_type.value,
            avg_satisfaction=avg_satisfaction,
        )
        return summary

    # -- domain operations --------------------------------------------------

    def analyze_feedback_patterns(self) -> dict[str, Any]:
        """Group by feedback_type; return count and avg satisfaction_score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.feedback_type.value
            type_data.setdefault(key, []).append(r.satisfaction_score)
        result: dict[str, Any] = {}
        for ftype, scores in type_data.items():
            result[ftype] = {
                "count": len(scores),
                "avg_satisfaction_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_poor_articles(self) -> list[dict[str, Any]]:
        """Return records where satisfaction_score < min_satisfaction_score."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.satisfaction_score < self._min_satisfaction_score:
                results.append(
                    {
                        "record_id": r.id,
                        "article_id": r.article_id,
                        "satisfaction_score": r.satisfaction_score,
                        "feedback_type": r.feedback_type.value,
                        "reviewer": r.reviewer,
                    }
                )
        return results

    def rank_by_satisfaction(self) -> list[dict[str, Any]]:
        """Group by article_id, total satisfaction_score, sort descending."""
        article_scores: dict[str, float] = {}
        for r in self._records:
            article_scores[r.article_id] = (
                article_scores.get(r.article_id, 0) + r.satisfaction_score
            )
        results: list[dict[str, Any]] = []
        for article_id, total in article_scores.items():
            results.append(
                {
                    "article_id": article_id,
                    "total_satisfaction": total,
                }
            )
        results.sort(key=lambda x: x["total_satisfaction"], reverse=True)
        return results

    def detect_feedback_trends(self) -> dict[str, Any]:
        """Split-half on satisfaction_score; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [r.satisfaction_score for r in self._records]
        mid = len(counts) // 2
        first_half = counts[:mid]
        second_half = counts[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> KnowledgeFeedbackReport:
        by_type: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        for r in self._records:
            by_type[r.feedback_type.value] = by_type.get(r.feedback_type.value, 0) + 1
            by_source[r.feedback_source.value] = by_source.get(r.feedback_source.value, 0) + 1
            by_quality[r.content_quality.value] = by_quality.get(r.content_quality.value, 0) + 1
        poor_count = sum(
            1 for r in self._records if r.satisfaction_score < self._min_satisfaction_score
        )
        reviewed_articles = len({r.article_id for r in self._records if r.satisfaction_score > 0})
        avg_sat = (
            round(sum(r.satisfaction_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        poor_article_ids = [
            r.article_id
            for r in self._records
            if r.satisfaction_score < self._min_satisfaction_score
        ][:5]
        recs: list[str] = []
        if poor_count > 0:
            recs.append(
                f"{poor_count} article(s) below minimum satisfaction"
                f" ({self._min_satisfaction_score}%)"
            )
        if self._records and avg_sat < self._min_satisfaction_score:
            recs.append(
                f"Average satisfaction {avg_sat}% is below threshold"
                f" ({self._min_satisfaction_score}%)"
            )
        if not recs:
            recs.append("Knowledge feedback satisfaction levels are healthy")
        return KnowledgeFeedbackReport(
            total_records=len(self._records),
            total_summaries=len(self._summaries),
            reviewed_articles=reviewed_articles,
            avg_satisfaction_score=avg_sat,
            by_type=by_type,
            by_source=by_source,
            by_quality=by_quality,
            poor_articles=poor_article_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._summaries.clear()
        logger.info("feedback_loop.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.feedback_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_summaries": len(self._summaries),
            "min_satisfaction_score": self._min_satisfaction_score,
            "type_distribution": type_dist,
            "unique_articles": len({r.article_id for r in self._records}),
            "unique_reviewers": len({r.reviewer for r in self._records}),
        }
