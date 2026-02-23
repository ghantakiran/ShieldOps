"""Change Advisory Board automation for infra changes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────────────


class ChangeCategory(StrEnum):
    """Category of infrastructure change."""

    STANDARD = "standard"
    NORMAL = "normal"
    EMERGENCY = "emergency"
    EXPEDITED = "expedited"


class ReviewDecision(StrEnum):
    """Decision outcome for a change review."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    MORE_INFO = "more_info"


# ── Models ───────────────────────────────────────────────────────────────────


class ChangeRequest(BaseModel):
    """A change request submitted for CAB review."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    category: ChangeCategory = ChangeCategory.NORMAL
    service: str = ""
    risk_score: float = 0.0
    requester: str = ""
    reviewers: list[str] = Field(default_factory=list)
    decision: ReviewDecision = ReviewDecision.PENDING
    decision_reason: str = ""
    submitted_at: float = Field(default_factory=time.time)
    decided_at: float | None = None


class ReviewVote(BaseModel):
    """A single reviewer vote on a change request."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = ""
    reviewer: str = ""
    decision: ReviewDecision = ReviewDecision.PENDING
    comment: str = ""
    voted_at: float = Field(default_factory=time.time)


# ── Engine ───────────────────────────────────────────────────────────────────


class ChangeAdvisoryBoard:
    """Automates CAB review for infrastructure changes."""

    def __init__(
        self,
        max_requests: int = 10000,
        max_votes: int = 50000,
        auto_approve_threshold: float = 0.3,
    ) -> None:
        self.max_requests = max_requests
        self.max_votes = max_votes
        self.auto_approve_threshold = auto_approve_threshold

        self._requests: dict[str, ChangeRequest] = {}
        self._votes: dict[str, ReviewVote] = {}

        logger.info(
            "change_advisory.init",
            max_requests=max_requests,
            max_votes=max_votes,
            auto_approve_threshold=auto_approve_threshold,
        )

    # ── Request management ───────────────────────────────────────────

    def submit_request(self, title: str, **kw: Any) -> ChangeRequest:
        """Submit a new change request for review."""
        if len(self._requests) >= self.max_requests:
            oldest = next(iter(self._requests))
            del self._requests[oldest]

        request = ChangeRequest(title=title, **kw)
        self._requests[request.id] = request
        logger.info(
            "change_advisory.submit",
            request_id=request.id,
            title=title,
            category=request.category.value,
        )
        return request

    def add_reviewer(self, request_id: str, reviewer: str) -> ChangeRequest | None:
        """Add a reviewer to a change request."""
        request = self._requests.get(request_id)
        if request is None:
            return None
        if reviewer not in request.reviewers:
            request.reviewers.append(reviewer)
            logger.info(
                "change_advisory.add_reviewer",
                request_id=request_id,
                reviewer=reviewer,
            )
        return request

    def get_request(self, request_id: str) -> ChangeRequest | None:
        """Get a change request by ID."""
        return self._requests.get(request_id)

    def list_requests(
        self,
        category: ChangeCategory | None = None,
        decision: ReviewDecision | None = None,
    ) -> list[ChangeRequest]:
        """List requests with optional filters."""
        results = list(self._requests.values())
        if category is not None:
            results = [r for r in results if r.category == category]
        if decision is not None:
            results = [r for r in results if r.decision == decision]
        return results

    # ── Voting ───────────────────────────────────────────────────────

    def cast_vote(
        self,
        request_id: str,
        reviewer: str,
        decision: ReviewDecision,
        comment: str = "",
    ) -> ReviewVote:
        """Cast a review vote on a change request."""
        request = self._requests.get(request_id)
        if request is None:
            raise ValueError(f"Change request not found: {request_id}")

        if len(self._votes) >= self.max_votes:
            oldest = next(iter(self._votes))
            del self._votes[oldest]

        # Ensure reviewer is listed
        if reviewer not in request.reviewers:
            request.reviewers.append(reviewer)

        vote = ReviewVote(
            request_id=request_id,
            reviewer=reviewer,
            decision=decision,
            comment=comment,
        )
        self._votes[vote.id] = vote
        logger.info(
            "change_advisory.vote",
            request_id=request_id,
            reviewer=reviewer,
            decision=decision.value,
        )
        return vote

    def get_votes(self, request_id: str) -> list[ReviewVote]:
        """Get all votes for a change request."""
        return [v for v in self._votes.values() if v.request_id == request_id]

    # ── Decision automation ──────────────────────────────────────────

    def auto_decide(self, request_id: str) -> ChangeRequest | None:
        """Auto-decide a request based on rules and votes."""
        request = self._requests.get(request_id)
        if request is None:
            return None

        if request.decision != ReviewDecision.PENDING:
            return request

        # Auto-approve low-risk standard changes
        if (
            request.risk_score <= self.auto_approve_threshold
            and request.category == ChangeCategory.STANDARD
        ):
            request.decision = ReviewDecision.APPROVED
            request.decision_reason = "Auto-approved: low risk standard change"
            request.decided_at = time.time()
            logger.info(
                "change_advisory.auto_approve",
                request_id=request_id,
            )
            return request

        # Check if all reviewers have voted
        votes = self.get_votes(request_id)
        if not request.reviewers or not votes:
            return None

        # Get latest vote per reviewer
        latest: dict[str, ReviewVote] = {}
        for v in votes:
            existing = latest.get(v.reviewer)
            if existing is None or v.voted_at > existing.voted_at:
                latest[v.reviewer] = v

        voted_reviewers = set(latest.keys())
        all_reviewers = set(request.reviewers)
        if not all_reviewers.issubset(voted_reviewers):
            return None

        # Majority decision
        counts: dict[str, int] = {}
        for v in latest.values():
            key = v.decision.value
            counts[key] = counts.get(key, 0) + 1

        majority_decision = max(counts, key=lambda k: counts[k])
        request.decision = ReviewDecision(majority_decision)
        request.decision_reason = f"Majority decision: {counts}"
        request.decided_at = time.time()
        logger.info(
            "change_advisory.decided",
            request_id=request_id,
            decision=request.decision.value,
        )
        return request

    # ── Queries ──────────────────────────────────────────────────────

    def get_pending_reviews(self, reviewer: str | None = None) -> list[ChangeRequest]:
        """Get pending change requests, optionally for a reviewer."""
        pending = [r for r in self._requests.values() if r.decision == ReviewDecision.PENDING]
        if reviewer is not None:
            pending = [r for r in pending if reviewer in r.reviewers]
        return pending

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        requests = list(self._requests.values())
        return {
            "total_requests": len(requests),
            "total_votes": len(self._votes),
            "requests_by_category": {
                c.value: sum(1 for r in requests if r.category == c) for c in ChangeCategory
            },
            "requests_by_decision": {
                d.value: sum(1 for r in requests if r.decision == d) for d in ReviewDecision
            },
            "avg_risk_score": (
                round(
                    sum(r.risk_score for r in requests) / len(requests),
                    4,
                )
                if requests
                else 0.0
            ),
        }
