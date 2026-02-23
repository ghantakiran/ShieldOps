"""Operational readiness review system for production launch validation.

Validates that services meet operational readiness criteria across observability,
security, reliability, documentation, testing, and capacity before production
launches. Supports configurable checklists, scoring, and item waivers.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class ReviewStatus(enum.StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"


class CheckCategory(enum.StrEnum):
    OBSERVABILITY = "observability"
    SECURITY = "security"
    RELIABILITY = "reliability"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    CAPACITY = "capacity"


# -- Models --------------------------------------------------------------------


class ChecklistItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    description: str = ""
    category: CheckCategory
    required: bool = True
    status: ReviewStatus = ReviewStatus.DRAFT
    evidence: str = ""
    reviewed_by: str = ""
    reviewed_at: float | None = None


class ReadinessChecklist(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    version: str = ""
    items: list[ChecklistItem] = Field(default_factory=list)
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class ReviewResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    checklist_id: str
    service: str
    passed: bool
    total_items: int = 0
    passed_items: int = 0
    failed_items: int = 0
    waived_items: int = 0
    score: float = 0.0
    reviewed_at: float = Field(default_factory=time.time)


# -- Engine --------------------------------------------------------------------


class OperationalReadinessReviewer:
    """Manage operational readiness checklists and reviews.

    Parameters
    ----------
    max_checklists:
        Maximum checklists to store.
    passing_threshold:
        Minimum score (0.0-1.0) to pass a review.
    """

    def __init__(
        self,
        max_checklists: int = 200,
        passing_threshold: float = 0.8,
    ) -> None:
        self._checklists: dict[str, ReadinessChecklist] = {}
        self._reviews: dict[str, ReviewResult] = {}
        self._max_checklists = max_checklists
        self._passing_threshold = passing_threshold

    def create_checklist(
        self,
        service: str,
        version: str = "",
        created_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ReadinessChecklist:
        if len(self._checklists) >= self._max_checklists:
            raise ValueError(f"Maximum checklists limit reached: {self._max_checklists}")
        checklist = ReadinessChecklist(
            service=service,
            version=version,
            created_by=created_by,
            metadata=metadata or {},
        )
        self._checklists[checklist.id] = checklist
        logger.info(
            "readiness_checklist_created",
            checklist_id=checklist.id,
            service=service,
        )
        return checklist

    def add_check_item(
        self,
        checklist_id: str,
        name: str,
        category: CheckCategory,
        description: str = "",
        required: bool = True,
    ) -> ChecklistItem:
        checklist = self._checklists.get(checklist_id)
        if checklist is None:
            raise ValueError(f"Checklist not found: {checklist_id}")
        item = ChecklistItem(
            name=name,
            category=category,
            description=description,
            required=required,
        )
        checklist.items.append(item)
        logger.info(
            "check_item_added",
            checklist_id=checklist_id,
            item_id=item.id,
            name=name,
        )
        return item

    def evaluate_item(
        self,
        checklist_id: str,
        item_id: str,
        status: ReviewStatus,
        evidence: str = "",
        reviewed_by: str = "",
    ) -> ChecklistItem | None:
        checklist = self._checklists.get(checklist_id)
        if checklist is None:
            return None
        for item in checklist.items:
            if item.id == item_id:
                item.status = status
                item.evidence = evidence
                item.reviewed_by = reviewed_by
                item.reviewed_at = time.time()
                logger.info(
                    "check_item_evaluated",
                    checklist_id=checklist_id,
                    item_id=item_id,
                    status=status,
                )
                return item
        return None

    def run_review(self, checklist_id: str) -> ReviewResult:
        checklist = self._checklists.get(checklist_id)
        if checklist is None:
            raise ValueError(f"Checklist not found: {checklist_id}")

        total = len(checklist.items)
        passed_count = sum(1 for i in checklist.items if i.status == ReviewStatus.PASSED)
        failed_count = sum(1 for i in checklist.items if i.status == ReviewStatus.FAILED)
        waived_count = sum(1 for i in checklist.items if i.status == ReviewStatus.WAIVED)

        scorable = total - waived_count
        score = passed_count / scorable if scorable > 0 else 0.0
        passed = score >= self._passing_threshold

        result = ReviewResult(
            checklist_id=checklist_id,
            service=checklist.service,
            passed=passed,
            total_items=total,
            passed_items=passed_count,
            failed_items=failed_count,
            waived_items=waived_count,
            score=round(score, 4),
        )
        self._reviews[result.id] = result
        logger.info(
            "readiness_review_completed",
            review_id=result.id,
            service=checklist.service,
            passed=passed,
            score=result.score,
        )
        return result

    def get_review(self, review_id: str) -> ReviewResult | None:
        return self._reviews.get(review_id)

    def list_reviews(
        self,
        service: str | None = None,
    ) -> list[ReviewResult]:
        reviews = list(self._reviews.values())
        if service:
            reviews = [r for r in reviews if r.service == service]
        return reviews

    def waive_item(
        self,
        checklist_id: str,
        item_id: str,
        reason: str = "",
        waived_by: str = "",
    ) -> ChecklistItem | None:
        checklist = self._checklists.get(checklist_id)
        if checklist is None:
            return None
        for item in checklist.items:
            if item.id == item_id:
                item.status = ReviewStatus.WAIVED
                item.evidence = reason
                item.reviewed_by = waived_by
                item.reviewed_at = time.time()
                logger.info(
                    "check_item_waived",
                    checklist_id=checklist_id,
                    item_id=item_id,
                    reason=reason,
                )
                return item
        return None

    def get_checklist(self, checklist_id: str) -> ReadinessChecklist | None:
        return self._checklists.get(checklist_id)

    def get_stats(self) -> dict[str, Any]:
        total_reviews = len(self._reviews)
        passed_reviews = sum(1 for r in self._reviews.values() if r.passed)
        return {
            "total_checklists": len(self._checklists),
            "total_reviews": total_reviews,
            "passed_reviews": passed_reviews,
            "failed_reviews": total_reviews - passed_reviews,
            "passing_threshold": self._passing_threshold,
        }
