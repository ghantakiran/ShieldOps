"""Tests for shieldops.changes.change_advisory — ChangeAdvisoryBoard."""

from __future__ import annotations

import pytest

from shieldops.changes.change_advisory import (
    ChangeAdvisoryBoard,
    ChangeCategory,
    ChangeRequest,
    ReviewDecision,
    ReviewVote,
)


def _board(**kw) -> ChangeAdvisoryBoard:
    return ChangeAdvisoryBoard(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ChangeCategory (4 values)

    def test_category_standard(self):
        assert ChangeCategory.STANDARD == "standard"

    def test_category_normal(self):
        assert ChangeCategory.NORMAL == "normal"

    def test_category_emergency(self):
        assert ChangeCategory.EMERGENCY == "emergency"

    def test_category_expedited(self):
        assert ChangeCategory.EXPEDITED == "expedited"

    # ReviewDecision (5 values)

    def test_decision_pending(self):
        assert ReviewDecision.PENDING == "pending"

    def test_decision_approved(self):
        assert ReviewDecision.APPROVED == "approved"

    def test_decision_rejected(self):
        assert ReviewDecision.REJECTED == "rejected"

    def test_decision_deferred(self):
        assert ReviewDecision.DEFERRED == "deferred"

    def test_decision_more_info(self):
        assert ReviewDecision.MORE_INFO == "more_info"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_change_request_defaults(self):
        cr = ChangeRequest(title="Deploy v2")
        assert cr.id
        assert cr.title == "Deploy v2"
        assert cr.description == ""
        assert cr.category == ChangeCategory.NORMAL
        assert cr.service == ""
        assert cr.risk_score == 0.0
        assert cr.requester == ""
        assert cr.reviewers == []
        assert cr.decision == ReviewDecision.PENDING
        assert cr.decision_reason == ""
        assert cr.submitted_at > 0
        assert cr.decided_at is None

    def test_review_vote_defaults(self):
        rv = ReviewVote(
            request_id="req-1",
            reviewer="alice",
            decision=ReviewDecision.APPROVED,
        )
        assert rv.id
        assert rv.request_id == "req-1"
        assert rv.reviewer == "alice"
        assert rv.decision == ReviewDecision.APPROVED
        assert rv.comment == ""
        assert rv.voted_at > 0


# ---------------------------------------------------------------------------
# submit_request
# ---------------------------------------------------------------------------


class TestSubmitRequest:
    def test_basic_submit(self):
        b = _board()
        req = b.submit_request("Deploy v2")
        assert req.title == "Deploy v2"
        assert req.decision == ReviewDecision.PENDING
        assert req.id in b._requests

    def test_submit_with_all_fields(self):
        b = _board()
        req = b.submit_request(
            "Scale DB",
            category=ChangeCategory.EMERGENCY,
            service="postgres",
            risk_score=0.8,
            requester="bob",
        )
        assert req.category == ChangeCategory.EMERGENCY
        assert req.service == "postgres"
        assert req.risk_score == pytest.approx(0.8)
        assert req.requester == "bob"

    def test_evicts_at_max_requests(self):
        b = _board(max_requests=2)
        r1 = b.submit_request("First")
        b.submit_request("Second")
        b.submit_request("Third")
        assert len(b._requests) == 2
        assert b.get_request(r1.id) is None


# ---------------------------------------------------------------------------
# add_reviewer
# ---------------------------------------------------------------------------


class TestAddReviewer:
    def test_adds_reviewer_to_list(self):
        b = _board()
        req = b.submit_request("Deploy")
        result = b.add_reviewer(req.id, "alice")
        assert result is not None
        assert "alice" in result.reviewers

    def test_no_duplicate_reviewer(self):
        b = _board()
        req = b.submit_request("Deploy")
        b.add_reviewer(req.id, "alice")
        b.add_reviewer(req.id, "alice")
        assert req.reviewers.count("alice") == 1

    def test_add_multiple_reviewers(self):
        b = _board()
        req = b.submit_request("Deploy")
        b.add_reviewer(req.id, "alice")
        b.add_reviewer(req.id, "bob")
        assert len(req.reviewers) == 2

    def test_add_reviewer_not_found(self):
        b = _board()
        result = b.add_reviewer("nonexistent", "alice")
        assert result is None


# ---------------------------------------------------------------------------
# cast_vote
# ---------------------------------------------------------------------------


class TestCastVote:
    def test_basic_vote(self):
        b = _board()
        req = b.submit_request("Deploy")
        b.add_reviewer(req.id, "alice")
        vote = b.cast_vote(req.id, "alice", ReviewDecision.APPROVED)
        assert vote.request_id == req.id
        assert vote.reviewer == "alice"
        assert vote.decision == ReviewDecision.APPROVED

    def test_vote_with_comment(self):
        b = _board()
        req = b.submit_request("Deploy")
        vote = b.cast_vote(
            req.id,
            "bob",
            ReviewDecision.REJECTED,
            comment="Too risky",
        )
        assert vote.comment == "Too risky"

    def test_raises_for_unknown_request(self):
        b = _board()
        with pytest.raises(ValueError, match="Change request not found"):
            b.cast_vote(
                "nonexistent",
                "alice",
                ReviewDecision.APPROVED,
            )

    def test_auto_adds_reviewer(self):
        b = _board()
        req = b.submit_request("Deploy")
        b.cast_vote(req.id, "carol", ReviewDecision.APPROVED)
        assert "carol" in req.reviewers

    def test_get_votes_for_request(self):
        b = _board()
        req = b.submit_request("Deploy")
        b.cast_vote(req.id, "alice", ReviewDecision.APPROVED)
        b.cast_vote(req.id, "bob", ReviewDecision.REJECTED)
        votes = b.get_votes(req.id)
        assert len(votes) == 2


# ---------------------------------------------------------------------------
# auto_decide
# ---------------------------------------------------------------------------


class TestAutoDecide:
    def test_auto_approves_low_risk_standard(self):
        b = _board(auto_approve_threshold=0.3)
        req = b.submit_request(
            "Minor config",
            category=ChangeCategory.STANDARD,
            risk_score=0.1,
        )
        result = b.auto_decide(req.id)
        assert result is not None
        assert result.decision == ReviewDecision.APPROVED
        assert "Auto-approved" in result.decision_reason
        assert result.decided_at is not None

    def test_no_auto_approve_high_risk(self):
        b = _board(auto_approve_threshold=0.3)
        req = b.submit_request(
            "Big change",
            category=ChangeCategory.STANDARD,
            risk_score=0.5,
        )
        result = b.auto_decide(req.id)
        assert result is None

    def test_no_auto_approve_non_standard(self):
        b = _board(auto_approve_threshold=0.3)
        req = b.submit_request(
            "Normal change",
            category=ChangeCategory.NORMAL,
            risk_score=0.1,
        )
        result = b.auto_decide(req.id)
        # Not standard category, so no auto-approve
        assert result is None

    def test_majority_wins_after_all_vote(self):
        b = _board()
        req = b.submit_request("Deploy")
        b.add_reviewer(req.id, "alice")
        b.add_reviewer(req.id, "bob")
        b.add_reviewer(req.id, "carol")
        b.cast_vote(req.id, "alice", ReviewDecision.APPROVED)
        b.cast_vote(req.id, "bob", ReviewDecision.APPROVED)
        b.cast_vote(req.id, "carol", ReviewDecision.REJECTED)
        result = b.auto_decide(req.id)
        assert result is not None
        assert result.decision == ReviewDecision.APPROVED
        assert result.decided_at is not None

    def test_returns_none_if_not_all_voted(self):
        b = _board()
        req = b.submit_request("Deploy")
        b.add_reviewer(req.id, "alice")
        b.add_reviewer(req.id, "bob")
        b.cast_vote(req.id, "alice", ReviewDecision.APPROVED)
        result = b.auto_decide(req.id)
        assert result is None

    def test_not_found_returns_none(self):
        b = _board()
        result = b.auto_decide("nonexistent")
        assert result is None

    def test_already_decided_returns_request(self):
        b = _board(auto_approve_threshold=0.3)
        req = b.submit_request(
            "Config",
            category=ChangeCategory.STANDARD,
            risk_score=0.1,
        )
        b.auto_decide(req.id)
        # Calling again should return same decision
        result = b.auto_decide(req.id)
        assert result is not None
        assert result.decision == ReviewDecision.APPROVED


# ---------------------------------------------------------------------------
# get_pending_reviews
# ---------------------------------------------------------------------------


class TestPendingReviews:
    def test_lists_pending(self):
        b = _board()
        b.submit_request("Deploy A")
        b.submit_request("Deploy B")
        pending = b.get_pending_reviews()
        assert len(pending) == 2

    def test_filter_by_reviewer(self):
        b = _board()
        r1 = b.submit_request("Deploy A")
        r2 = b.submit_request("Deploy B")
        b.add_reviewer(r1.id, "alice")
        b.add_reviewer(r2.id, "bob")
        alice_pending = b.get_pending_reviews(reviewer="alice")
        assert len(alice_pending) == 1
        assert alice_pending[0].id == r1.id

    def test_excludes_decided(self):
        b = _board(auto_approve_threshold=0.5)
        r1 = b.submit_request(
            "Auto",
            category=ChangeCategory.STANDARD,
            risk_score=0.1,
        )
        b.submit_request("Manual")
        b.auto_decide(r1.id)
        pending = b.get_pending_reviews()
        assert len(pending) == 1


# ---------------------------------------------------------------------------
# list_requests
# ---------------------------------------------------------------------------


class TestListRequests:
    def test_filter_by_category(self):
        b = _board()
        b.submit_request("Std", category=ChangeCategory.STANDARD)
        b.submit_request("Emrg", category=ChangeCategory.EMERGENCY)
        std = b.list_requests(category=ChangeCategory.STANDARD)
        assert len(std) == 1
        assert std[0].category == ChangeCategory.STANDARD

    def test_filter_by_decision(self):
        b = _board(auto_approve_threshold=0.5)
        r1 = b.submit_request(
            "Auto",
            category=ChangeCategory.STANDARD,
            risk_score=0.1,
        )
        b.submit_request("Manual")
        b.auto_decide(r1.id)
        approved = b.list_requests(decision=ReviewDecision.APPROVED)
        pending = b.list_requests(decision=ReviewDecision.PENDING)
        assert len(approved) == 1
        assert len(pending) == 1

    def test_list_all(self):
        b = _board()
        b.submit_request("A")
        b.submit_request("B")
        assert len(b.list_requests()) == 2


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        b = _board()
        stats = b.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_votes"] == 0
        assert stats["avg_risk_score"] == 0.0

    def test_populated_stats(self):
        b = _board(auto_approve_threshold=0.5)
        r1 = b.submit_request(
            "Std",
            category=ChangeCategory.STANDARD,
            risk_score=0.2,
        )
        b.submit_request(
            "Emrg",
            category=ChangeCategory.EMERGENCY,
            risk_score=0.8,
        )
        b.auto_decide(r1.id)
        b.cast_vote(r1.id, "alice", ReviewDecision.APPROVED)
        stats = b.get_stats()
        assert stats["total_requests"] == 2
        assert stats["total_votes"] == 1
        by_cat = stats["requests_by_category"]
        assert by_cat["standard"] == 1
        assert by_cat["emergency"] == 1
        by_dec = stats["requests_by_decision"]
        assert by_dec["approved"] == 1
        assert by_dec["pending"] == 1
        assert stats["avg_risk_score"] == pytest.approx(0.5, abs=0.01)
