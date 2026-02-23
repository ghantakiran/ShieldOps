"""Tests for shieldops.agents.investigation.readiness_review – OperationalReadinessReviewer."""

from __future__ import annotations

import time

import pytest

from shieldops.agents.investigation.readiness_review import (
    CheckCategory,
    ChecklistItem,
    OperationalReadinessReviewer,
    ReadinessChecklist,
    ReviewResult,
    ReviewStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reviewer(**kwargs) -> OperationalReadinessReviewer:
    return OperationalReadinessReviewer(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_review_status_values(self):
        assert ReviewStatus.DRAFT == "draft"
        assert ReviewStatus.IN_REVIEW == "in_review"
        assert ReviewStatus.PASSED == "passed"
        assert ReviewStatus.FAILED == "failed"
        assert ReviewStatus.WAIVED == "waived"

    def test_check_category_values(self):
        assert CheckCategory.OBSERVABILITY == "observability"
        assert CheckCategory.SECURITY == "security"
        assert CheckCategory.RELIABILITY == "reliability"
        assert CheckCategory.DOCUMENTATION == "documentation"
        assert CheckCategory.TESTING == "testing"
        assert CheckCategory.CAPACITY == "capacity"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_checklist_item_defaults(self):
        item = ChecklistItem(name="test-item", category=CheckCategory.SECURITY)
        assert item.id
        assert item.name == "test-item"
        assert item.description == ""
        assert item.required is True
        assert item.status == ReviewStatus.DRAFT
        assert item.evidence == ""
        assert item.reviewed_by == ""
        assert item.reviewed_at is None

    def test_readiness_checklist_defaults(self):
        cl = ReadinessChecklist(service="api-gateway")
        assert cl.id
        assert cl.service == "api-gateway"
        assert cl.version == ""
        assert cl.items == []
        assert cl.created_by == ""
        assert cl.metadata == {}
        assert cl.created_at > 0

    def test_review_result_defaults(self):
        rr = ReviewResult(checklist_id="cl-1", service="api", passed=False)
        assert rr.id
        assert rr.checklist_id == "cl-1"
        assert rr.service == "api"
        assert rr.passed is False
        assert rr.total_items == 0
        assert rr.passed_items == 0
        assert rr.failed_items == 0
        assert rr.waived_items == 0
        assert rr.score == 0.0
        assert rr.reviewed_at > 0


# ---------------------------------------------------------------------------
# Create checklist
# ---------------------------------------------------------------------------


class TestCreateChecklist:
    def test_basic(self):
        r = _reviewer()
        cl = r.create_checklist(service="payments")
        assert cl.service == "payments"
        assert cl.id

    def test_with_all_fields(self):
        r = _reviewer()
        cl = r.create_checklist(
            service="auth",
            version="2.1.0",
            created_by="sre-team",
            metadata={"tier": "critical"},
        )
        assert cl.version == "2.1.0"
        assert cl.created_by == "sre-team"
        assert cl.metadata["tier"] == "critical"

    def test_max_limit(self):
        r = _reviewer(max_checklists=2)
        r.create_checklist(service="s1")
        r.create_checklist(service="s2")
        with pytest.raises(ValueError, match="Maximum checklists"):
            r.create_checklist(service="s3")


# ---------------------------------------------------------------------------
# Add check item
# ---------------------------------------------------------------------------


class TestAddCheckItem:
    def test_basic(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        item = r.add_check_item(
            checklist_id=cl.id,
            name="has-alerts",
            category=CheckCategory.OBSERVABILITY,
        )
        assert item.name == "has-alerts"
        assert item.category == CheckCategory.OBSERVABILITY
        assert item.id

    def test_with_description_and_optional_flag(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        item = r.add_check_item(
            checklist_id=cl.id,
            name="load-test",
            category=CheckCategory.TESTING,
            description="Run k6 load test",
            required=False,
        )
        assert item.description == "Run k6 load test"
        assert item.required is False

    def test_checklist_not_found(self):
        r = _reviewer()
        with pytest.raises(ValueError, match="Checklist not found"):
            r.add_check_item(
                checklist_id="nonexistent",
                name="x",
                category=CheckCategory.SECURITY,
            )


# ---------------------------------------------------------------------------
# Evaluate item
# ---------------------------------------------------------------------------


class TestEvaluateItem:
    def test_success(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        item = r.add_check_item(cl.id, "check1", CheckCategory.SECURITY)
        result = r.evaluate_item(
            cl.id, item.id, ReviewStatus.PASSED, evidence="screenshot", reviewed_by="alice"
        )
        assert result is not None
        assert result.status == ReviewStatus.PASSED
        assert result.evidence == "screenshot"
        assert result.reviewed_by == "alice"
        assert result.reviewed_at is not None

    def test_item_not_found(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        result = r.evaluate_item(cl.id, "nonexistent", ReviewStatus.PASSED)
        assert result is None

    def test_checklist_not_found(self):
        r = _reviewer()
        result = r.evaluate_item("nonexistent", "item-1", ReviewStatus.PASSED)
        assert result is None


# ---------------------------------------------------------------------------
# Run review
# ---------------------------------------------------------------------------


class TestRunReview:
    def test_passes_when_score_above_threshold(self):
        r = _reviewer(passing_threshold=0.5)
        cl = r.create_checklist(service="api")
        i1 = r.add_check_item(cl.id, "c1", CheckCategory.SECURITY)
        i2 = r.add_check_item(cl.id, "c2", CheckCategory.RELIABILITY)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.PASSED)
        r.evaluate_item(cl.id, i2.id, ReviewStatus.PASSED)
        result = r.run_review(cl.id)
        assert result.passed is True
        assert result.score == 1.0
        assert result.passed_items == 2
        assert result.total_items == 2

    def test_fails_when_below_threshold(self):
        r = _reviewer(passing_threshold=0.8)
        cl = r.create_checklist(service="api")
        i1 = r.add_check_item(cl.id, "c1", CheckCategory.SECURITY)
        i2 = r.add_check_item(cl.id, "c2", CheckCategory.RELIABILITY)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.PASSED)
        r.evaluate_item(cl.id, i2.id, ReviewStatus.FAILED)
        result = r.run_review(cl.id)
        assert result.passed is False
        assert result.score == 0.5
        assert result.failed_items == 1

    def test_handles_waived_items(self):
        r = _reviewer(passing_threshold=0.8)
        cl = r.create_checklist(service="api")
        i1 = r.add_check_item(cl.id, "c1", CheckCategory.SECURITY)
        i2 = r.add_check_item(cl.id, "c2", CheckCategory.RELIABILITY)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.PASSED)
        r.evaluate_item(cl.id, i2.id, ReviewStatus.WAIVED)
        result = r.run_review(cl.id)
        # waived items excluded from score: 1/1 = 1.0
        assert result.passed is True
        assert result.score == 1.0
        assert result.waived_items == 1

    def test_empty_checklist(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        result = r.run_review(cl.id)
        # 0 items -> score 0.0 -> fails
        assert result.passed is False
        assert result.score == 0.0
        assert result.total_items == 0

    def test_checklist_not_found(self):
        r = _reviewer()
        with pytest.raises(ValueError, match="Checklist not found"):
            r.run_review("nonexistent")

    def test_mixed_statuses(self):
        r = _reviewer(passing_threshold=0.6)
        cl = r.create_checklist(service="api")
        items = []
        for i in range(5):
            items.append(r.add_check_item(cl.id, f"c{i}", CheckCategory.TESTING))
        r.evaluate_item(cl.id, items[0].id, ReviewStatus.PASSED)
        r.evaluate_item(cl.id, items[1].id, ReviewStatus.PASSED)
        r.evaluate_item(cl.id, items[2].id, ReviewStatus.PASSED)
        r.evaluate_item(cl.id, items[3].id, ReviewStatus.FAILED)
        r.evaluate_item(cl.id, items[4].id, ReviewStatus.WAIVED)
        result = r.run_review(cl.id)
        # scorable = 5 - 1 = 4, passed = 3, score = 0.75
        assert result.score == 0.75
        assert result.passed is True

    def test_review_result_has_service(self):
        r = _reviewer()
        cl = r.create_checklist(service="billing")
        result = r.run_review(cl.id)
        assert result.service == "billing"


# ---------------------------------------------------------------------------
# Get review
# ---------------------------------------------------------------------------


class TestGetReview:
    def test_found(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        result = r.run_review(cl.id)
        fetched = r.get_review(result.id)
        assert fetched is not None
        assert fetched.id == result.id

    def test_not_found(self):
        r = _reviewer()
        assert r.get_review("nonexistent") is None


# ---------------------------------------------------------------------------
# List reviews
# ---------------------------------------------------------------------------


class TestListReviews:
    def test_all(self):
        r = _reviewer()
        cl1 = r.create_checklist(service="api")
        cl2 = r.create_checklist(service="web")
        r.run_review(cl1.id)
        r.run_review(cl2.id)
        reviews = r.list_reviews()
        assert len(reviews) == 2

    def test_filter_by_service(self):
        r = _reviewer()
        cl1 = r.create_checklist(service="api")
        cl2 = r.create_checklist(service="web")
        r.run_review(cl1.id)
        r.run_review(cl2.id)
        reviews = r.list_reviews(service="api")
        assert len(reviews) == 1
        assert reviews[0].service == "api"

    def test_filter_no_match(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        r.run_review(cl.id)
        reviews = r.list_reviews(service="nonexistent")
        assert len(reviews) == 0


# ---------------------------------------------------------------------------
# Waive item
# ---------------------------------------------------------------------------


class TestWaiveItem:
    def test_success(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        item = r.add_check_item(cl.id, "optional-check", CheckCategory.DOCUMENTATION)
        waived = r.waive_item(cl.id, item.id, reason="Not applicable", waived_by="bob")
        assert waived is not None
        assert waived.status == ReviewStatus.WAIVED
        assert waived.evidence == "Not applicable"
        assert waived.reviewed_by == "bob"
        assert waived.reviewed_at is not None

    def test_item_not_found(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        result = r.waive_item(cl.id, "nonexistent", reason="n/a")
        assert result is None

    def test_checklist_not_found(self):
        r = _reviewer()
        result = r.waive_item("nonexistent", "item-1", reason="n/a")
        assert result is None


# ---------------------------------------------------------------------------
# Get checklist
# ---------------------------------------------------------------------------


class TestGetChecklist:
    def test_found(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        fetched = r.get_checklist(cl.id)
        assert fetched is not None
        assert fetched.id == cl.id

    def test_not_found(self):
        r = _reviewer()
        assert r.get_checklist("nonexistent") is None

    def test_checklist_contains_items(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        r.add_check_item(cl.id, "item1", CheckCategory.SECURITY)
        r.add_check_item(cl.id, "item2", CheckCategory.RELIABILITY)
        fetched = r.get_checklist(cl.id)
        assert fetched is not None
        assert len(fetched.items) == 2


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        r = _reviewer()
        s = r.get_stats()
        assert s["total_checklists"] == 0
        assert s["total_reviews"] == 0
        assert s["passed_reviews"] == 0
        assert s["failed_reviews"] == 0

    def test_with_data(self):
        r = _reviewer(passing_threshold=0.5)
        cl = r.create_checklist(service="api")
        i1 = r.add_check_item(cl.id, "c1", CheckCategory.SECURITY)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.PASSED)
        r.run_review(cl.id)
        s = r.get_stats()
        assert s["total_checklists"] == 1
        assert s["total_reviews"] == 1
        assert s["passed_reviews"] == 1
        assert s["failed_reviews"] == 0
        assert s["passing_threshold"] == 0.5

    def test_with_failed_review(self):
        r = _reviewer(passing_threshold=0.8)
        cl = r.create_checklist(service="api")
        i1 = r.add_check_item(cl.id, "c1", CheckCategory.SECURITY)
        i2 = r.add_check_item(cl.id, "c2", CheckCategory.RELIABILITY)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.PASSED)
        r.evaluate_item(cl.id, i2.id, ReviewStatus.FAILED)
        r.run_review(cl.id)
        s = r.get_stats()
        assert s["passed_reviews"] == 0
        assert s["failed_reviews"] == 1


# ---------------------------------------------------------------------------
# Additional coverage: checklist isolation and edge cases
# ---------------------------------------------------------------------------


class TestChecklistIsolation:
    def test_separate_checklists_have_unique_ids(self):
        r = _reviewer()
        cl1 = r.create_checklist(service="api")
        cl2 = r.create_checklist(service="web")
        assert cl1.id != cl2.id

    def test_items_belong_to_their_checklist(self):
        r = _reviewer()
        cl1 = r.create_checklist(service="api")
        cl2 = r.create_checklist(service="web")
        r.add_check_item(cl1.id, "item-a", CheckCategory.SECURITY)
        r.add_check_item(cl2.id, "item-b", CheckCategory.TESTING)
        assert len(r.get_checklist(cl1.id).items) == 1
        assert len(r.get_checklist(cl2.id).items) == 1

    def test_evaluate_wrong_checklist_returns_none(self):
        r = _reviewer()
        cl1 = r.create_checklist(service="api")
        cl2 = r.create_checklist(service="web")
        item = r.add_check_item(cl1.id, "item", CheckCategory.SECURITY)
        result = r.evaluate_item(cl2.id, item.id, ReviewStatus.PASSED)
        assert result is None

    def test_waive_wrong_checklist_returns_none(self):
        r = _reviewer()
        cl1 = r.create_checklist(service="api")
        cl2 = r.create_checklist(service="web")
        item = r.add_check_item(cl1.id, "item", CheckCategory.SECURITY)
        result = r.waive_item(cl2.id, item.id, reason="test")
        assert result is None


class TestReviewScoring:
    def test_all_failed_gives_zero_score(self):
        r = _reviewer(passing_threshold=0.5)
        cl = r.create_checklist(service="api")
        i1 = r.add_check_item(cl.id, "c1", CheckCategory.SECURITY)
        i2 = r.add_check_item(cl.id, "c2", CheckCategory.RELIABILITY)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.FAILED)
        r.evaluate_item(cl.id, i2.id, ReviewStatus.FAILED)
        result = r.run_review(cl.id)
        assert result.score == 0.0
        assert result.passed is False
        assert result.failed_items == 2

    def test_all_waived_gives_zero_score(self):
        r = _reviewer(passing_threshold=0.5)
        cl = r.create_checklist(service="api")
        i1 = r.add_check_item(cl.id, "c1", CheckCategory.SECURITY)
        i2 = r.add_check_item(cl.id, "c2", CheckCategory.RELIABILITY)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.WAIVED)
        r.evaluate_item(cl.id, i2.id, ReviewStatus.WAIVED)
        result = r.run_review(cl.id)
        # scorable = 0, score = 0.0
        assert result.score == 0.0
        assert result.waived_items == 2

    def test_threshold_boundary_exact_pass(self):
        r = _reviewer(passing_threshold=0.5)
        cl = r.create_checklist(service="api")
        i1 = r.add_check_item(cl.id, "c1", CheckCategory.SECURITY)
        i2 = r.add_check_item(cl.id, "c2", CheckCategory.RELIABILITY)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.PASSED)
        r.evaluate_item(cl.id, i2.id, ReviewStatus.FAILED)
        result = r.run_review(cl.id)
        assert result.score == 0.5
        assert result.passed is True  # score == threshold means pass

    def test_threshold_boundary_just_below(self):
        r = _reviewer(passing_threshold=0.51)
        cl = r.create_checklist(service="api")
        i1 = r.add_check_item(cl.id, "c1", CheckCategory.SECURITY)
        i2 = r.add_check_item(cl.id, "c2", CheckCategory.RELIABILITY)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.PASSED)
        r.evaluate_item(cl.id, i2.id, ReviewStatus.FAILED)
        result = r.run_review(cl.id)
        assert result.passed is False

    def test_unevaluated_items_count_as_not_passed(self):
        r = _reviewer(passing_threshold=0.5)
        cl = r.create_checklist(service="api")
        r.add_check_item(cl.id, "c1", CheckCategory.SECURITY)
        i2 = r.add_check_item(cl.id, "c2", CheckCategory.RELIABILITY)
        r.evaluate_item(cl.id, i2.id, ReviewStatus.PASSED)
        result = r.run_review(cl.id)
        assert result.score == 0.5
        assert result.passed_items == 1
        assert result.total_items == 2

    def test_single_item_passed(self):
        r = _reviewer(passing_threshold=1.0)
        cl = r.create_checklist(service="api")
        i1 = r.add_check_item(cl.id, "c1", CheckCategory.CAPACITY)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.PASSED)
        result = r.run_review(cl.id)
        assert result.score == 1.0
        assert result.passed is True

    def test_multiple_reviews_same_checklist(self):
        r = _reviewer(passing_threshold=0.5)
        cl = r.create_checklist(service="api")
        i1 = r.add_check_item(cl.id, "c1", CheckCategory.SECURITY)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.FAILED)
        result1 = r.run_review(cl.id)
        r.evaluate_item(cl.id, i1.id, ReviewStatus.PASSED)
        result2 = r.run_review(cl.id)
        assert result1.passed is False
        assert result2.passed is True
        assert len(r.list_reviews()) == 2


class TestChecklistMetadata:
    def test_empty_metadata(self):
        r = _reviewer()
        cl = r.create_checklist(service="api")
        assert cl.metadata == {}

    def test_metadata_persists(self):
        r = _reviewer()
        cl = r.create_checklist(service="api", metadata={"owner": "sre", "tier": "1"})
        fetched = r.get_checklist(cl.id)
        assert fetched is not None
        assert fetched.metadata["owner"] == "sre"
        assert fetched.metadata["tier"] == "1"

    def test_created_at_set(self):
        before = time.time()
        r = _reviewer()
        cl = r.create_checklist(service="api")
        after = time.time()
        assert before <= cl.created_at <= after

    def test_default_passing_threshold(self):
        r = _reviewer()
        s = r.get_stats()
        assert s["passing_threshold"] == 0.8

    def test_custom_passing_threshold(self):
        r = _reviewer(passing_threshold=0.9)
        s = r.get_stats()
        assert s["passing_threshold"] == 0.9
