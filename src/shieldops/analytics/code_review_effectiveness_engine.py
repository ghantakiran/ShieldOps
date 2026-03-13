"""Code Review Effectiveness Engine —
compute review quality score, detect bottlenecks,
rank reviewers by effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReviewOutcome(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    ABANDONED = "abandoned"


class ReviewDepth(StrEnum):
    THOROUGH = "thorough"
    ADEQUATE = "adequate"
    SUPERFICIAL = "superficial"
    RUBBER_STAMP = "rubber_stamp"


class BottleneckType(StrEnum):
    QUEUE_TIME = "queue_time"
    REVIEWER_AVAILABILITY = "reviewer_availability"
    SCOPE_CREEP = "scope_creep"
    REWORK = "rework"


# --- Models ---


class CodeReviewRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    review_id: str = ""
    reviewer_id: str = ""
    outcome: ReviewOutcome = ReviewOutcome.APPROVED
    depth: ReviewDepth = ReviewDepth.ADEQUATE
    bottleneck: BottleneckType = BottleneckType.QUEUE_TIME
    quality_score: float = 0.0
    review_time_hours: float = 0.0
    comments_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CodeReviewAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reviewer_id: str = ""
    avg_quality: float = 0.0
    depth: ReviewDepth = ReviewDepth.ADEQUATE
    reviews_completed: int = 0
    avg_review_time: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CodeReviewReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_quality: float = 0.0
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_depth: dict[str, int] = Field(default_factory=dict)
    by_bottleneck: dict[str, int] = Field(default_factory=dict)
    top_reviewers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CodeReviewEffectivenessEngine:
    """Compute review quality score, detect bottlenecks,
    rank reviewers by effectiveness."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CodeReviewRecord] = []
        self._analyses: dict[str, CodeReviewAnalysis] = {}
        logger.info(
            "code_review_effectiveness_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        review_id: str = "",
        reviewer_id: str = "",
        outcome: ReviewOutcome = ReviewOutcome.APPROVED,
        depth: ReviewDepth = ReviewDepth.ADEQUATE,
        bottleneck: BottleneckType = (BottleneckType.QUEUE_TIME),
        quality_score: float = 0.0,
        review_time_hours: float = 0.0,
        comments_count: int = 0,
        description: str = "",
    ) -> CodeReviewRecord:
        record = CodeReviewRecord(
            review_id=review_id,
            reviewer_id=reviewer_id,
            outcome=outcome,
            depth=depth,
            bottleneck=bottleneck,
            quality_score=quality_score,
            review_time_hours=review_time_hours,
            comments_count=comments_count,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "code_review_effectiveness.record_added",
            record_id=record.id,
            review_id=review_id,
        )
        return record

    def process(self, key: str) -> CodeReviewAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        rev_recs = [r for r in self._records if r.reviewer_id == rec.reviewer_id]
        scores = [r.quality_score for r in rev_recs]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        times = [r.review_time_hours for r in rev_recs]
        avg_time = round(sum(times) / len(times), 2) if times else 0.0
        analysis = CodeReviewAnalysis(
            reviewer_id=rec.reviewer_id,
            avg_quality=avg,
            depth=rec.depth,
            reviews_completed=len(rev_recs),
            avg_review_time=avg_time,
            description=(f"Reviewer {rec.reviewer_id} q={avg}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CodeReviewReport:
        by_o: dict[str, int] = {}
        by_d: dict[str, int] = {}
        by_b: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.outcome.value
            by_o[k] = by_o.get(k, 0) + 1
            k2 = r.depth.value
            by_d[k2] = by_d.get(k2, 0) + 1
            k3 = r.bottleneck.value
            by_b[k3] = by_b.get(k3, 0) + 1
            scores.append(r.quality_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        rev_scores: dict[str, list[float]] = {}
        for r in self._records:
            rev_scores.setdefault(r.reviewer_id, []).append(r.quality_score)
        rev_avgs = {rid: sum(s) / len(s) for rid, s in rev_scores.items()}
        top = sorted(
            rev_avgs,
            key=lambda x: rev_avgs[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        rubber = by_d.get("rubber_stamp", 0)
        if rubber > 0:
            recs.append(f"{rubber} rubber-stamp reviews found")
        if not recs:
            recs.append("Review quality is adequate")
        return CodeReviewReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_quality=avg,
            by_outcome=by_o,
            by_depth=by_d,
            by_bottleneck=by_b,
            top_reviewers=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        o_dist: dict[str, int] = {}
        for r in self._records:
            k = r.outcome.value
            o_dist[k] = o_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "outcome_distribution": o_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("code_review_effectiveness_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_review_quality_score(
        self,
    ) -> list[dict[str, Any]]:
        """Compute review quality per reviewer."""
        rev_scores: dict[str, list[float]] = {}
        rev_comments: dict[str, int] = {}
        for r in self._records:
            rev_scores.setdefault(r.reviewer_id, []).append(r.quality_score)
            rev_comments[r.reviewer_id] = rev_comments.get(r.reviewer_id, 0) + r.comments_count
        results: list[dict[str, Any]] = []
        for rid, scores in rev_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "reviewer_id": rid,
                    "quality_score": avg,
                    "total_comments": (rev_comments.get(rid, 0)),
                    "reviews": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["quality_score"],
            reverse=True,
        )
        return results

    def detect_review_bottlenecks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect review bottlenecks by type."""
        bn_hours: dict[str, float] = {}
        bn_counts: dict[str, int] = {}
        for r in self._records:
            bt = r.bottleneck.value
            bn_hours[bt] = bn_hours.get(bt, 0.0) + r.review_time_hours
            bn_counts[bt] = bn_counts.get(bt, 0) + 1
        results: list[dict[str, Any]] = []
        for bt, hours in bn_hours.items():
            results.append(
                {
                    "bottleneck_type": bt,
                    "total_hours": round(hours, 2),
                    "occurrences": bn_counts.get(bt, 0),
                }
            )
        results.sort(
            key=lambda x: x["total_hours"],
            reverse=True,
        )
        return results

    def rank_reviewers_by_effectiveness(
        self,
    ) -> list[dict[str, Any]]:
        """Rank reviewers by effectiveness."""
        rev_scores: dict[str, list[float]] = {}
        for r in self._records:
            rev_scores.setdefault(r.reviewer_id, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for rid, scores in rev_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "reviewer_id": rid,
                    "effectiveness_score": avg,
                    "reviews": len(scores),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["effectiveness_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
