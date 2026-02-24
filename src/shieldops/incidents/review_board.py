"""Incident Review Board — structured review with action items and blameless scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReviewStatus(StrEnum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    ACTIONS_ASSIGNED = "actions_assigned"
    FOLLOW_UP = "follow_up"
    CLOSED = "closed"


class ActionPriority(StrEnum):
    IMMEDIATE = "immediate"
    NEXT_SPRINT = "next_sprint"
    QUARTERLY = "quarterly"
    BACKLOG = "backlog"
    WONT_FIX = "wont_fix"


class ReviewCategory(StrEnum):
    PROCESS_GAP = "process_gap"
    TOOLING_GAP = "tooling_gap"
    KNOWLEDGE_GAP = "knowledge_gap"
    COMMUNICATION_GAP = "communication_gap"
    MONITORING_GAP = "monitoring_gap"


# --- Models ---


class IncidentReview(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    title: str = ""
    status: ReviewStatus = ReviewStatus.PENDING
    category: ReviewCategory = ReviewCategory.PROCESS_GAP
    summary: str = ""
    root_cause: str = ""
    blameless_score: float = 0.0
    action_items: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class ReviewActionItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    review_id: str = ""
    description: str = ""
    priority: ActionPriority = ActionPriority.BACKLOG
    assignee: str = ""
    status: str = "open"
    due_date: str = ""
    completed_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ReviewBoardReport(BaseModel):
    total_reviews: int = 0
    total_action_items: int = 0
    completion_rate: float = 0.0
    avg_blameless_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    recurring_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentReviewBoard:
    """Structured incident review with action items and blameless culture scoring."""

    def __init__(
        self,
        max_reviews: int = 100000,
        action_sla_days: int = 14,
    ) -> None:
        self._max_reviews = max_reviews
        self._action_sla_days = action_sla_days
        self._reviews: list[IncidentReview] = []
        self._action_items: list[ReviewActionItem] = []
        logger.info(
            "review_board.initialized",
            max_reviews=max_reviews,
            action_sla_days=action_sla_days,
        )

    def create_review(
        self,
        incident_id: str = "",
        title: str = "",
        category: ReviewCategory = ReviewCategory.PROCESS_GAP,
        summary: str = "",
        root_cause: str = "",
    ) -> IncidentReview:
        """Create a new incident review."""
        review = IncidentReview(
            incident_id=incident_id,
            title=title,
            category=category,
            summary=summary,
            root_cause=root_cause,
        )
        self._reviews.append(review)
        if len(self._reviews) > self._max_reviews:
            self._reviews = self._reviews[-self._max_reviews :]
        logger.info(
            "review_board.review_created",
            review_id=review.id,
            incident_id=incident_id,
            category=category,
        )
        return review

    def get_review(self, review_id: str) -> IncidentReview | None:
        """Retrieve a review by ID."""
        for r in self._reviews:
            if r.id == review_id:
                return r
        return None

    def list_reviews(
        self,
        status: ReviewStatus | None = None,
        category: ReviewCategory | None = None,
        limit: int = 100,
    ) -> list[IncidentReview]:
        """List reviews with optional filtering."""
        results = list(self._reviews)
        if status is not None:
            results = [r for r in results if r.status == status]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def add_action_item(
        self,
        review_id: str,
        description: str = "",
        priority: ActionPriority = ActionPriority.BACKLOG,
        assignee: str = "",
        due_date: str = "",
    ) -> ReviewActionItem | None:
        """Add an action item to a review. Returns None if review not found."""
        review = self.get_review(review_id)
        if review is None:
            return None
        action = ReviewActionItem(
            review_id=review_id,
            description=description,
            priority=priority,
            assignee=assignee,
            due_date=due_date,
        )
        self._action_items.append(action)
        review.action_items.append(action.id)
        logger.info(
            "review_board.action_item_added",
            action_id=action.id,
            review_id=review_id,
            priority=priority,
        )
        return action

    def update_action_status(
        self,
        action_id: str,
        status: str = "open",
    ) -> ReviewActionItem | None:
        """Update action item status. Sets completed_at if status is 'completed'."""
        for action in self._action_items:
            if action.id == action_id:
                action.status = status
                if status == "completed":
                    action.completed_at = time.time()
                logger.info(
                    "review_board.action_status_updated",
                    action_id=action_id,
                    status=status,
                )
                return action
        return None

    def calculate_completion_rate(self) -> dict[str, Any]:
        """Calculate action item completion rate."""
        total = len(self._action_items)
        completed = sum(1 for a in self._action_items if a.status == "completed")
        rate = round(completed / total * 100, 2) if total > 0 else 0.0
        return {
            "total_actions": total,
            "completed": completed,
            "completion_rate_pct": rate,
        }

    def identify_recurring_gaps(self) -> list[dict[str, Any]]:
        """Count categories across reviews, return those with count > 1."""
        category_counts: dict[str, int] = {}
        for r in self._reviews:
            category_counts[r.category] = category_counts.get(r.category, 0) + 1
        recurring: list[dict[str, Any]] = []
        for category, count in category_counts.items():
            if count > 1:
                recurring.append({"category": category, "count": count})
        return recurring

    def score_blameless_culture(self, review_id: str) -> dict[str, Any]:
        """Score blameless culture for a review based on completeness."""
        review = self.get_review(review_id)
        if review is None:
            return {"review_id": review_id, "score": 0.0, "breakdown": {}}

        breakdown: dict[str, float] = {}
        score = 0.0

        # Has root_cause (+30)
        has_root_cause = bool(review.root_cause)
        breakdown["has_root_cause"] = 30.0 if has_root_cause else 0.0
        score += breakdown["has_root_cause"]

        # Has summary (+20)
        has_summary = bool(review.summary)
        breakdown["has_summary"] = 20.0 if has_summary else 0.0
        score += breakdown["has_summary"]

        # Has action_items (+25)
        has_actions = len(review.action_items) > 0
        breakdown["has_action_items"] = 25.0 if has_actions else 0.0
        score += breakdown["has_action_items"]

        # Status != PENDING (+25)
        not_pending = review.status != ReviewStatus.PENDING
        breakdown["status_progressed"] = 25.0 if not_pending else 0.0
        score += breakdown["status_progressed"]

        review.blameless_score = score
        logger.info(
            "review_board.blameless_scored",
            review_id=review_id,
            score=score,
        )
        return {
            "review_id": review_id,
            "score": score,
            "breakdown": breakdown,
        }

    def generate_review_report(self) -> ReviewBoardReport:
        """Generate a comprehensive review board report."""
        total_reviews = len(self._reviews)
        total_actions = len(self._action_items)

        # Completion rate
        completed = sum(1 for a in self._action_items if a.status == "completed")
        completion_rate = round(completed / total_actions * 100, 2) if total_actions > 0 else 0.0

        # Average blameless score
        scores = [r.blameless_score for r in self._reviews]
        avg_blameless = round(sum(scores) / len(scores), 2) if scores else 0.0

        # By status
        by_status: dict[str, int] = {}
        for r in self._reviews:
            by_status[r.status] = by_status.get(r.status, 0) + 1

        # By category
        by_category: dict[str, int] = {}
        for r in self._reviews:
            by_category[r.category] = by_category.get(r.category, 0) + 1

        # By priority
        by_priority: dict[str, int] = {}
        for a in self._action_items:
            by_priority[a.priority] = by_priority.get(a.priority, 0) + 1

        # Recurring gaps
        recurring = self.identify_recurring_gaps()
        recurring_gaps = [g["category"] for g in recurring]

        # Recommendations
        recommendations: list[str] = []
        if completion_rate < 50.0 and total_actions > 0:
            recommendations.append(
                "Action item completion rate is below 50% — prioritize outstanding items"
            )
        if avg_blameless < 50.0 and total_reviews > 0:
            recommendations.append(
                "Average blameless score is below 50 — improve review thoroughness"
            )
        if recurring_gaps:
            recommendations.append(
                f"Recurring gaps: {', '.join(recurring_gaps)} — invest in systemic fixes"
            )
        overdue_count = sum(
            1 for a in self._action_items if a.status != "completed" and a.due_date != ""
        )
        if overdue_count > 0:
            recommendations.append(
                f"{overdue_count} action item(s) with due dates still open — review SLA compliance"
            )

        logger.info(
            "review_board.report_generated",
            total_reviews=total_reviews,
            total_actions=total_actions,
            completion_rate=completion_rate,
        )
        return ReviewBoardReport(
            total_reviews=total_reviews,
            total_action_items=total_actions,
            completion_rate=completion_rate,
            avg_blameless_score=avg_blameless,
            by_status=by_status,
            by_category=by_category,
            by_priority=by_priority,
            recurring_gaps=recurring_gaps,
            recommendations=recommendations,
        )

    def clear_data(self) -> None:
        """Clear all stored data."""
        self._reviews.clear()
        self._action_items.clear()
        logger.info("review_board.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        status_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        for r in self._reviews:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
            category_counts[r.category] = category_counts.get(r.category, 0) + 1
        return {
            "total_reviews": len(self._reviews),
            "total_action_items": len(self._action_items),
            "completed_actions": sum(1 for a in self._action_items if a.status == "completed"),
            "status_distribution": status_counts,
            "category_distribution": category_counts,
        }
