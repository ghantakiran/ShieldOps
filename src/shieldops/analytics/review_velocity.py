"""Code Review Velocity Tracker — track PR review cycle times, reviewer load, bottlenecks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReviewStage(StrEnum):
    AWAITING_REVIEW = "awaiting_review"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    MERGED = "merged"


class ReviewSize(StrEnum):
    TRIVIAL = "trivial"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXTRA_LARGE = "extra_large"


class ReviewBottleneck(StrEnum):
    REVIEWER_AVAILABILITY = "reviewer_availability"
    LARGE_DIFF = "large_diff"
    MISSING_CONTEXT = "missing_context"
    CI_FAILURE = "ci_failure"
    APPROVAL_POLICY = "approval_policy"


# --- Models ---


class ReviewCycleRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pr_number: str = ""
    author: str = ""
    reviewer: str = ""
    stage: ReviewStage = ReviewStage.AWAITING_REVIEW
    size: ReviewSize = ReviewSize.MEDIUM
    cycle_time_hours: float = 0.0
    lines_changed: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ReviewerLoad(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reviewer: str = ""
    active_reviews: int = 0
    avg_turnaround_hours: float = 0.0
    bottleneck: ReviewBottleneck = ReviewBottleneck.REVIEWER_AVAILABILITY
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ReviewVelocityReport(BaseModel):
    total_reviews: int = 0
    total_reviewer_loads: int = 0
    avg_cycle_time_hours: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_size: dict[str, int] = Field(default_factory=dict)
    slow_review_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CodeReviewVelocityTracker:
    """Track PR review cycle times, reviewer load, and bottlenecks."""

    def __init__(
        self,
        max_records: int = 200000,
        max_cycle_hours: float = 48.0,
    ) -> None:
        self._max_records = max_records
        self._max_cycle_hours = max_cycle_hours
        self._records: list[ReviewCycleRecord] = []
        self._loads: list[ReviewerLoad] = []
        logger.info(
            "review_velocity.initialized",
            max_records=max_records,
            max_cycle_hours=max_cycle_hours,
        )

    # -- record / get / list -------------------------------------------------

    def record_review_cycle(
        self,
        pr_number: str,
        author: str = "",
        reviewer: str = "",
        stage: ReviewStage = ReviewStage.AWAITING_REVIEW,
        size: ReviewSize = ReviewSize.MEDIUM,
        cycle_time_hours: float = 0.0,
        lines_changed: int = 0,
        details: str = "",
    ) -> ReviewCycleRecord:
        record = ReviewCycleRecord(
            pr_number=pr_number,
            author=author,
            reviewer=reviewer,
            stage=stage,
            size=size,
            cycle_time_hours=cycle_time_hours,
            lines_changed=lines_changed,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "review_velocity.cycle_recorded",
            record_id=record.id,
            pr_number=pr_number,
            stage=stage.value,
        )
        return record

    def get_review(self, record_id: str) -> ReviewCycleRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_reviews(
        self,
        author: str | None = None,
        stage: ReviewStage | None = None,
        limit: int = 50,
    ) -> list[ReviewCycleRecord]:
        results = list(self._records)
        if author is not None:
            results = [r for r in results if r.author == author]
        if stage is not None:
            results = [r for r in results if r.stage == stage]
        return results[-limit:]

    def record_reviewer_load(
        self,
        reviewer: str,
        active_reviews: int = 0,
        avg_turnaround_hours: float = 0.0,
        bottleneck: ReviewBottleneck = ReviewBottleneck.REVIEWER_AVAILABILITY,
        details: str = "",
    ) -> ReviewerLoad:
        load = ReviewerLoad(
            reviewer=reviewer,
            active_reviews=active_reviews,
            avg_turnaround_hours=avg_turnaround_hours,
            bottleneck=bottleneck,
            details=details,
        )
        self._loads.append(load)
        if len(self._loads) > self._max_records:
            self._loads = self._loads[-self._max_records :]
        logger.info(
            "review_velocity.load_recorded",
            reviewer=reviewer,
            active_reviews=active_reviews,
        )
        return load

    # -- domain operations ---------------------------------------------------

    def analyze_review_velocity(self, author: str) -> dict[str, Any]:
        """Analyze review velocity for a specific author."""
        records = [r for r in self._records if r.author == author]
        if not records:
            return {"author": author, "status": "no_data"}
        total = len(records)
        avg_cycle = round(sum(r.cycle_time_hours for r in records) / total, 2)
        merged = sum(1 for r in records if r.stage == ReviewStage.MERGED)
        return {
            "author": author,
            "total_reviews": total,
            "avg_cycle_time_hours": avg_cycle,
            "merged_count": merged,
            "merge_rate_pct": round(merged / total * 100, 2),
        }

    def identify_slow_reviews(self) -> list[dict[str, Any]]:
        """Find reviews exceeding max_cycle_hours threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.cycle_time_hours > self._max_cycle_hours:
                results.append(
                    {
                        "pr_number": r.pr_number,
                        "author": r.author,
                        "reviewer": r.reviewer,
                        "cycle_time_hours": r.cycle_time_hours,
                        "stage": r.stage.value,
                        "size": r.size.value,
                    }
                )
        results.sort(key=lambda x: x["cycle_time_hours"], reverse=True)
        return results

    def rank_reviewers_by_load(self) -> list[dict[str, Any]]:
        """Rank reviewers by their active review load."""
        load_map: dict[str, list[int]] = {}
        for ld in self._loads:
            load_map.setdefault(ld.reviewer, []).append(ld.active_reviews)
        results: list[dict[str, Any]] = []
        for reviewer, loads in load_map.items():
            results.append(
                {
                    "reviewer": reviewer,
                    "avg_active_reviews": round(sum(loads) / len(loads), 2),
                    "load_snapshots": len(loads),
                }
            )
        results.sort(key=lambda x: x["avg_active_reviews"], reverse=True)
        return results

    def detect_bottlenecks(self) -> list[dict[str, Any]]:
        """Detect bottlenecks from reviewer load records."""
        bottleneck_counts: dict[str, int] = {}
        for ld in self._loads:
            key = ld.bottleneck.value
            bottleneck_counts[key] = bottleneck_counts.get(key, 0) + 1
        results: list[dict[str, Any]] = []
        for bn, count in bottleneck_counts.items():
            results.append({"bottleneck": bn, "count": count})
        results.sort(key=lambda x: x["count"], reverse=True)
        return results

    # -- report / stats ------------------------------------------------------

    def generate_report(self) -> ReviewVelocityReport:
        by_stage: dict[str, int] = {}
        by_size: dict[str, int] = {}
        for r in self._records:
            by_stage[r.stage.value] = by_stage.get(r.stage.value, 0) + 1
            by_size[r.size.value] = by_size.get(r.size.value, 0) + 1
        total = len(self._records)
        avg_cycle = (
            round(sum(r.cycle_time_hours for r in self._records) / total, 2) if total else 0.0
        )
        slow_count = sum(1 for r in self._records if r.cycle_time_hours > self._max_cycle_hours)
        recs: list[str] = []
        if slow_count > 0:
            recs.append(f"{slow_count} review(s) exceed {self._max_cycle_hours}h cycle threshold")
        if avg_cycle > self._max_cycle_hours:
            recs.append(f"Average cycle time {avg_cycle}h exceeds {self._max_cycle_hours}h target")
        if not recs:
            recs.append("Review velocity meets targets")
        return ReviewVelocityReport(
            total_reviews=total,
            total_reviewer_loads=len(self._loads),
            avg_cycle_time_hours=avg_cycle,
            by_stage=by_stage,
            by_size=by_size,
            slow_review_count=slow_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._loads.clear()
        logger.info("review_velocity.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_reviews": len(self._records),
            "total_reviewer_loads": len(self._loads),
            "max_cycle_hours": self._max_cycle_hours,
            "stage_distribution": stage_dist,
            "unique_authors": len({r.author for r in self._records}),
        }
