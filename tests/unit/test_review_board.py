"""Tests for shieldops.incidents.review_board — IncidentReviewBoard."""

from __future__ import annotations

from shieldops.incidents.review_board import (
    ActionPriority,
    IncidentReview,
    IncidentReviewBoard,
    ReviewActionItem,
    ReviewBoardReport,
    ReviewCategory,
    ReviewStatus,
)


def _engine(**kw) -> IncidentReviewBoard:
    return IncidentReviewBoard(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ReviewStatus (5)
    def test_status_pending(self):
        assert ReviewStatus.PENDING == "pending"

    def test_status_in_review(self):
        assert ReviewStatus.IN_REVIEW == "in_review"

    def test_status_actions_assigned(self):
        assert ReviewStatus.ACTIONS_ASSIGNED == "actions_assigned"

    def test_status_follow_up(self):
        assert ReviewStatus.FOLLOW_UP == "follow_up"

    def test_status_closed(self):
        assert ReviewStatus.CLOSED == "closed"

    # ActionPriority (5)
    def test_priority_immediate(self):
        assert ActionPriority.IMMEDIATE == "immediate"

    def test_priority_next_sprint(self):
        assert ActionPriority.NEXT_SPRINT == "next_sprint"

    def test_priority_quarterly(self):
        assert ActionPriority.QUARTERLY == "quarterly"

    def test_priority_backlog(self):
        assert ActionPriority.BACKLOG == "backlog"

    def test_priority_wont_fix(self):
        assert ActionPriority.WONT_FIX == "wont_fix"

    # ReviewCategory (5)
    def test_category_process_gap(self):
        assert ReviewCategory.PROCESS_GAP == "process_gap"

    def test_category_tooling_gap(self):
        assert ReviewCategory.TOOLING_GAP == "tooling_gap"

    def test_category_knowledge_gap(self):
        assert ReviewCategory.KNOWLEDGE_GAP == "knowledge_gap"

    def test_category_communication_gap(self):
        assert ReviewCategory.COMMUNICATION_GAP == "communication_gap"

    def test_category_monitoring_gap(self):
        assert ReviewCategory.MONITORING_GAP == "monitoring_gap"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_incident_review_defaults(self):
        r = IncidentReview()
        assert r.id
        assert r.incident_id == ""
        assert r.title == ""
        assert r.status == ReviewStatus.PENDING
        assert r.category == ReviewCategory.PROCESS_GAP
        assert r.blameless_score == 0.0
        assert r.action_items == []

    def test_review_action_item_defaults(self):
        a = ReviewActionItem()
        assert a.id
        assert a.review_id == ""
        assert a.priority == ActionPriority.BACKLOG
        assert a.status == "open"
        assert a.completed_at == 0.0

    def test_review_board_report_defaults(self):
        r = ReviewBoardReport()
        assert r.total_reviews == 0
        assert r.completion_rate == 0.0
        assert r.avg_blameless_score == 0.0
        assert r.recurring_gaps == []
        assert r.recommendations == []


# ---------------------------------------------------------------------------
# create_review
# ---------------------------------------------------------------------------


class TestCreateReview:
    def test_basic_create(self):
        eng = _engine()
        r = eng.create_review(
            incident_id="INC-001",
            title="DB outage",
            category=ReviewCategory.MONITORING_GAP,
            summary="Database went down",
            root_cause="Connection pool exhausted",
        )
        assert r.incident_id == "INC-001"
        assert r.title == "DB outage"
        assert r.category == ReviewCategory.MONITORING_GAP

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.create_review(title="Review A")
        r2 = eng.create_review(title="Review B")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_reviews=3)
        for i in range(5):
            eng.create_review(title=f"Review-{i}")
        assert len(eng._reviews) == 3


# ---------------------------------------------------------------------------
# get_review
# ---------------------------------------------------------------------------


class TestGetReview:
    def test_found(self):
        eng = _engine()
        r = eng.create_review(title="Test")
        assert eng.get_review(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_review("nonexistent") is None


# ---------------------------------------------------------------------------
# list_reviews
# ---------------------------------------------------------------------------


class TestListReviews:
    def test_list_all(self):
        eng = _engine()
        eng.create_review(title="A")
        eng.create_review(title="B")
        assert len(eng.list_reviews()) == 2

    def test_filter_status(self):
        eng = _engine()
        eng.create_review(title="A")
        review_b = eng.create_review(title="B")
        review_b.status = ReviewStatus.CLOSED
        results = eng.list_reviews(status=ReviewStatus.PENDING)
        assert len(results) == 1

    def test_filter_category(self):
        eng = _engine()
        eng.create_review(title="A", category=ReviewCategory.PROCESS_GAP)
        eng.create_review(title="B", category=ReviewCategory.TOOLING_GAP)
        results = eng.list_reviews(category=ReviewCategory.TOOLING_GAP)
        assert len(results) == 1
        assert results[0].category == ReviewCategory.TOOLING_GAP


# ---------------------------------------------------------------------------
# add_action_item
# ---------------------------------------------------------------------------


class TestAddActionItem:
    def test_success(self):
        eng = _engine()
        r = eng.create_review(title="Test")
        action = eng.add_action_item(
            review_id=r.id,
            description="Add monitoring alerts",
            priority=ActionPriority.IMMEDIATE,
            assignee="alice",
        )
        assert action is not None
        assert action.description == "Add monitoring alerts"
        assert action.priority == ActionPriority.IMMEDIATE
        assert action.id in r.action_items

    def test_review_not_found(self):
        eng = _engine()
        result = eng.add_action_item(review_id="bad-id", description="test")
        assert result is None

    def test_multiple_items(self):
        eng = _engine()
        r = eng.create_review(title="Test")
        eng.add_action_item(review_id=r.id, description="Item 1")
        eng.add_action_item(review_id=r.id, description="Item 2")
        assert len(r.action_items) == 2


# ---------------------------------------------------------------------------
# update_action_status
# ---------------------------------------------------------------------------


class TestUpdateActionStatus:
    def test_to_completed(self):
        eng = _engine()
        r = eng.create_review(title="Test")
        action = eng.add_action_item(review_id=r.id, description="Fix it")
        result = eng.update_action_status(action.id, status="completed")
        assert result is not None
        assert result.status == "completed"
        assert result.completed_at > 0.0

    def test_to_in_progress(self):
        eng = _engine()
        r = eng.create_review(title="Test")
        action = eng.add_action_item(review_id=r.id, description="Fix it")
        result = eng.update_action_status(action.id, status="in_progress")
        assert result is not None
        assert result.status == "in_progress"
        assert result.completed_at == 0.0  # Not completed

    def test_not_found(self):
        eng = _engine()
        assert eng.update_action_status("bad-id", status="completed") is None


# ---------------------------------------------------------------------------
# calculate_completion_rate
# ---------------------------------------------------------------------------


class TestCalculateCompletionRate:
    def test_no_actions(self):
        eng = _engine()
        result = eng.calculate_completion_rate()
        assert result["total_actions"] == 0
        assert result["completion_rate_pct"] == 0.0

    def test_with_data(self):
        eng = _engine()
        r = eng.create_review(title="Test")
        action1 = eng.add_action_item(review_id=r.id, description="Task 1")
        eng.add_action_item(review_id=r.id, description="Task 2")
        eng.update_action_status(action1.id, status="completed")
        result = eng.calculate_completion_rate()
        assert result["total_actions"] == 2
        assert result["completed"] == 1
        assert result["completion_rate_pct"] == 50.0


# ---------------------------------------------------------------------------
# identify_recurring_gaps
# ---------------------------------------------------------------------------


class TestIdentifyRecurringGaps:
    def test_no_recurring(self):
        eng = _engine()
        eng.create_review(title="A", category=ReviewCategory.PROCESS_GAP)
        eng.create_review(title="B", category=ReviewCategory.TOOLING_GAP)
        result = eng.identify_recurring_gaps()
        assert len(result) == 0

    def test_with_recurring(self):
        eng = _engine()
        eng.create_review(title="A", category=ReviewCategory.MONITORING_GAP)
        eng.create_review(title="B", category=ReviewCategory.MONITORING_GAP)
        eng.create_review(title="C", category=ReviewCategory.TOOLING_GAP)
        result = eng.identify_recurring_gaps()
        assert len(result) == 1
        assert result[0]["category"] == ReviewCategory.MONITORING_GAP
        assert result[0]["count"] == 2


# ---------------------------------------------------------------------------
# score_blameless_culture
# ---------------------------------------------------------------------------


class TestScoreBlamelessCulture:
    def test_review_not_found(self):
        eng = _engine()
        result = eng.score_blameless_culture("bad-id")
        assert result["score"] == 0.0

    def test_minimal_review(self):
        eng = _engine()
        r = eng.create_review(title="Test")
        # No root_cause, no summary, no actions, status=PENDING => score = 0
        result = eng.score_blameless_culture(r.id)
        assert result["score"] == 0.0

    def test_full_review(self):
        eng = _engine()
        r = eng.create_review(
            title="Test",
            summary="Something happened",
            root_cause="Connection pool limit",
        )
        r.status = ReviewStatus.IN_REVIEW
        eng.add_action_item(review_id=r.id, description="Fix pool")
        result = eng.score_blameless_culture(r.id)
        # root_cause=30, summary=20, action_items=25, not_pending=25 => 100
        assert result["score"] == 100.0
        assert r.blameless_score == 100.0

    def test_partial_review(self):
        eng = _engine()
        r = eng.create_review(
            title="Test",
            root_cause="Bad deploy",
        )
        # root_cause=30, no summary=0, no actions=0, status=PENDING=0 => 30
        result = eng.score_blameless_culture(r.id)
        assert result["score"] == 30.0


# ---------------------------------------------------------------------------
# generate_review_report
# ---------------------------------------------------------------------------


class TestGenerateReviewReport:
    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_review_report()
        assert report.total_reviews == 0
        assert report.total_action_items == 0

    def test_with_data(self):
        eng = _engine()
        r = eng.create_review(
            title="Outage review",
            category=ReviewCategory.MONITORING_GAP,
        )
        eng.add_action_item(review_id=r.id, description="Add alerts")
        report = eng.generate_review_report()
        assert report.total_reviews == 1
        assert report.total_action_items == 1
        assert ReviewStatus.PENDING in report.by_status


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        r = eng.create_review(title="Test")
        eng.add_action_item(review_id=r.id, description="Fix")
        eng.clear_data()
        assert len(eng._reviews) == 0
        assert len(eng._action_items) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_reviews"] == 0
        assert stats["total_action_items"] == 0

    def test_populated(self):
        eng = _engine()
        r = eng.create_review(title="Test", category=ReviewCategory.PROCESS_GAP)
        a = eng.add_action_item(review_id=r.id, description="Fix")
        eng.update_action_status(a.id, status="completed")
        stats = eng.get_stats()
        assert stats["total_reviews"] == 1
        assert stats["total_action_items"] == 1
        assert stats["completed_actions"] == 1
        assert ReviewCategory.PROCESS_GAP in stats["category_distribution"]
