"""Comprehensive unit tests for PlaybookAutoApplier.

Tests cover:
- LearningRecommendation model creation and defaults
- AutoApplyResult model creation
- ApprovalPolicy classification logic (risk thresholds, type rules, confidence)
- Recommendation submission with auto-apply for low-risk items
- Approve/reject workflows including edge cases
- Listing and filtering recommendations
- Internal apply methods (threshold, playbook update, alert tuning, new playbook)
- Error handling and failure paths
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from shieldops.playbooks.auto_applier import (
    ApprovalPolicy,
    AutoApplyResult,
    LearningRecommendation,
    PlaybookAutoApplier,
    RecommendationStatus,
    RecommendationType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rec(
    rec_type: RecommendationType = RecommendationType.THRESHOLD_ADJUSTMENT,
    risk: float = 0.1,
    confidence: float = 0.9,
    title: str = "Test recommendation",
    description: str = "A test recommendation",
    target_playbook: str | None = None,
    changes: dict | None = None,
) -> LearningRecommendation:
    """Factory for creating LearningRecommendation instances with sensible defaults."""
    return LearningRecommendation(
        recommendation_type=rec_type,
        title=title,
        description=description,
        risk_score=risk,
        confidence=confidence,
        target_playbook=target_playbook,
        changes=changes or {},
    )


# ===========================================================================
# Model Tests
# ===========================================================================


class TestLearningRecommendationModel:
    """Tests for the LearningRecommendation Pydantic model."""

    def test_default_id_generated(self):
        rec = _make_rec()
        assert rec.id.startswith("rec-")
        assert len(rec.id) == 16  # "rec-" + 12 hex chars

    def test_unique_ids_across_instances(self):
        rec1 = _make_rec()
        rec2 = _make_rec()
        assert rec1.id != rec2.id

    def test_default_status_is_pending(self):
        rec = _make_rec()
        assert rec.status == RecommendationStatus.PENDING

    def test_default_approval_policy_is_require_review(self):
        rec = _make_rec()
        assert rec.approval_policy == ApprovalPolicy.REQUIRE_REVIEW

    def test_created_at_is_utc_datetime(self):
        rec = _make_rec()
        assert isinstance(rec.created_at, datetime)
        assert rec.created_at.tzinfo is not None

    def test_nullable_fields_default_to_none(self):
        rec = _make_rec()
        assert rec.target_playbook is None
        assert rec.applied_at is None
        assert rec.reviewed_by is None
        assert rec.rejection_reason is None

    def test_changes_default_to_empty_dict(self):
        rec = _make_rec()
        assert rec.changes == {}

    def test_custom_changes_preserved(self):
        changes = {"cpu_threshold": 0.8, "memory_threshold": 0.9}
        rec = _make_rec(changes=changes)
        assert rec.changes == changes


class TestAutoApplyResultModel:
    """Tests for the AutoApplyResult Pydantic model."""

    def test_creation_with_success(self):
        result = AutoApplyResult(
            recommendation_id="rec-abc123",
            success=True,
            applied_changes={"key": "value"},
        )
        assert result.success is True
        assert result.error is None
        assert result.applied_changes == {"key": "value"}

    def test_creation_with_failure(self):
        result = AutoApplyResult(
            recommendation_id="rec-abc123",
            success=False,
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_applied_at_auto_populated(self):
        result = AutoApplyResult(recommendation_id="rec-abc123", success=True)
        assert isinstance(result.applied_at, datetime)


# ===========================================================================
# Enum Tests
# ===========================================================================


class TestEnums:
    """Tests for StrEnum values to guard against accidental renames."""

    def test_approval_policy_values(self):
        assert ApprovalPolicy.AUTO_APPROVE == "auto_approve"
        assert ApprovalPolicy.REQUIRE_REVIEW == "require_review"
        assert ApprovalPolicy.MANUAL_ONLY == "manual_only"

    def test_recommendation_status_values(self):
        assert RecommendationStatus.PENDING == "pending"
        assert RecommendationStatus.APPROVED == "approved"
        assert RecommendationStatus.REJECTED == "rejected"
        assert RecommendationStatus.AUTO_APPLIED == "auto_applied"
        assert RecommendationStatus.FAILED == "failed"

    def test_recommendation_type_values(self):
        assert RecommendationType.THRESHOLD_ADJUSTMENT == "threshold_adjustment"
        assert RecommendationType.PLAYBOOK_UPDATE == "playbook_update"
        assert RecommendationType.NEW_PLAYBOOK == "new_playbook"
        assert RecommendationType.ALERT_TUNING == "alert_tuning"
        assert RecommendationType.PATTERN_RULE == "pattern_rule"


# ===========================================================================
# Policy Classification Tests
# ===========================================================================


class TestClassifyApprovalPolicy:
    """Tests for PlaybookAutoApplier.classify_approval_policy.

    Decision matrix:
    - risk > 0.7 => MANUAL_ONLY (regardless of type)
    - NEW_PLAYBOOK => MANUAL_ONLY (regardless of risk)
    - PLAYBOOK_UPDATE => REQUIRE_REVIEW (regardless of risk, if risk <= 0.7)
    - THRESHOLD_ADJUSTMENT + risk <= 0.3 + confidence >= 0.8 => AUTO_APPROVE
    - ALERT_TUNING + risk <= 0.3 => AUTO_APPROVE
    - Everything else => REQUIRE_REVIEW
    """

    def setup_method(self):
        self.applier = PlaybookAutoApplier()

    # -- High risk always becomes MANUAL_ONLY --

    def test_high_risk_threshold_adjustment_is_manual_only(self):
        rec = _make_rec(rec_type=RecommendationType.THRESHOLD_ADJUSTMENT, risk=0.8)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.MANUAL_ONLY

    def test_high_risk_playbook_update_is_manual_only(self):
        rec = _make_rec(rec_type=RecommendationType.PLAYBOOK_UPDATE, risk=0.75)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.MANUAL_ONLY

    def test_high_risk_alert_tuning_is_manual_only(self):
        rec = _make_rec(rec_type=RecommendationType.ALERT_TUNING, risk=0.9)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.MANUAL_ONLY

    def test_risk_exactly_at_review_max_is_not_manual_only(self):
        """Risk of exactly 0.7 should NOT trigger MANUAL_ONLY (> 0.7, not >=)."""
        rec = _make_rec(rec_type=RecommendationType.THRESHOLD_ADJUSTMENT, risk=0.7, confidence=0.5)
        policy = self.applier.classify_approval_policy(rec)
        assert policy != ApprovalPolicy.MANUAL_ONLY

    def test_risk_just_above_review_max_is_manual_only(self):
        rec = _make_rec(rec_type=RecommendationType.THRESHOLD_ADJUSTMENT, risk=0.71)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.MANUAL_ONLY

    # -- NEW_PLAYBOOK always MANUAL_ONLY (even low risk) --

    def test_new_playbook_low_risk_is_manual_only(self):
        rec = _make_rec(rec_type=RecommendationType.NEW_PLAYBOOK, risk=0.0)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.MANUAL_ONLY

    def test_new_playbook_medium_risk_is_manual_only(self):
        rec = _make_rec(rec_type=RecommendationType.NEW_PLAYBOOK, risk=0.5)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.MANUAL_ONLY

    # -- PLAYBOOK_UPDATE always REQUIRE_REVIEW (when risk <= 0.7) --

    def test_playbook_update_low_risk_is_require_review(self):
        rec = _make_rec(rec_type=RecommendationType.PLAYBOOK_UPDATE, risk=0.1)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.REQUIRE_REVIEW

    def test_playbook_update_medium_risk_is_require_review(self):
        rec = _make_rec(rec_type=RecommendationType.PLAYBOOK_UPDATE, risk=0.5)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.REQUIRE_REVIEW

    # -- THRESHOLD_ADJUSTMENT auto-approve conditions --

    def test_threshold_low_risk_high_confidence_auto_approves(self):
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.1,
            confidence=0.9,
        )
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.AUTO_APPROVE

    def test_threshold_at_risk_boundary_with_high_confidence_auto_approves(self):
        """Risk exactly at 0.3 should auto-approve (<= 0.3)."""
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.3,
            confidence=0.8,
        )
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.AUTO_APPROVE

    def test_threshold_at_confidence_boundary_auto_approves(self):
        """Confidence exactly at 0.8 should auto-approve (>= 0.8)."""
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.2,
            confidence=0.8,
        )
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.AUTO_APPROVE

    def test_threshold_low_risk_but_low_confidence_requires_review(self):
        """Low risk but confidence < 0.8 should fall through to REQUIRE_REVIEW."""
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.2,
            confidence=0.79,
        )
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.REQUIRE_REVIEW

    def test_threshold_risk_just_above_auto_approve_requires_review(self):
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.31,
            confidence=0.95,
        )
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.REQUIRE_REVIEW

    def test_threshold_medium_risk_requires_review(self):
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.5,
            confidence=0.95,
        )
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.REQUIRE_REVIEW

    # -- ALERT_TUNING auto-approve conditions --

    def test_alert_tuning_low_risk_auto_approves(self):
        rec = _make_rec(rec_type=RecommendationType.ALERT_TUNING, risk=0.1)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.AUTO_APPROVE

    def test_alert_tuning_at_risk_boundary_auto_approves(self):
        rec = _make_rec(rec_type=RecommendationType.ALERT_TUNING, risk=0.3)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.AUTO_APPROVE

    def test_alert_tuning_zero_risk_auto_approves(self):
        rec = _make_rec(rec_type=RecommendationType.ALERT_TUNING, risk=0.0)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.AUTO_APPROVE

    def test_alert_tuning_above_auto_approve_risk_requires_review(self):
        rec = _make_rec(rec_type=RecommendationType.ALERT_TUNING, risk=0.31)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.REQUIRE_REVIEW

    def test_alert_tuning_no_confidence_requirement(self):
        """ALERT_TUNING auto-approval does NOT check confidence (unlike THRESHOLD)."""
        rec = _make_rec(rec_type=RecommendationType.ALERT_TUNING, risk=0.2, confidence=0.0)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.AUTO_APPROVE

    # -- PATTERN_RULE fallback --

    def test_pattern_rule_low_risk_requires_review(self):
        rec = _make_rec(rec_type=RecommendationType.PATTERN_RULE, risk=0.1)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.REQUIRE_REVIEW

    def test_pattern_rule_high_risk_is_manual_only(self):
        rec = _make_rec(rec_type=RecommendationType.PATTERN_RULE, risk=0.8)
        assert self.applier.classify_approval_policy(rec) == ApprovalPolicy.MANUAL_ONLY


# ===========================================================================
# Submission Tests
# ===========================================================================


class TestSubmitRecommendation:
    """Tests for PlaybookAutoApplier.submit_recommendation."""

    def setup_method(self):
        self.applier = PlaybookAutoApplier()

    def test_submit_stores_recommendation(self):
        rec = _make_rec()
        result = self.applier.submit_recommendation(rec)
        assert self.applier.get_recommendation(result.id) is result

    def test_submit_sets_classified_policy(self):
        rec = _make_rec(rec_type=RecommendationType.PLAYBOOK_UPDATE, risk=0.2)
        result = self.applier.submit_recommendation(rec)
        assert result.approval_policy == ApprovalPolicy.REQUIRE_REVIEW

    def test_submit_auto_applies_low_risk_threshold_adjustment(self):
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.1,
            confidence=0.9,
            changes={"cpu_threshold": 80},
        )
        result = self.applier.submit_recommendation(rec)
        assert result.status == RecommendationStatus.AUTO_APPLIED
        assert result.applied_at is not None

    def test_submit_auto_applies_low_risk_alert_tuning(self):
        rec = _make_rec(
            rec_type=RecommendationType.ALERT_TUNING,
            risk=0.1,
            changes={"suppress": True},
        )
        result = self.applier.submit_recommendation(rec)
        assert result.status == RecommendationStatus.AUTO_APPLIED

    def test_submit_does_not_auto_apply_when_disabled(self):
        applier = PlaybookAutoApplier(auto_apply_enabled=False)
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.1,
            confidence=0.9,
        )
        result = applier.submit_recommendation(rec)
        assert result.status == RecommendationStatus.PENDING
        assert result.applied_at is None

    def test_submit_leaves_require_review_as_pending(self):
        rec = _make_rec(rec_type=RecommendationType.PLAYBOOK_UPDATE, risk=0.2)
        result = self.applier.submit_recommendation(rec)
        assert result.status == RecommendationStatus.PENDING

    def test_submit_leaves_manual_only_as_pending(self):
        rec = _make_rec(rec_type=RecommendationType.NEW_PLAYBOOK, risk=0.1)
        result = self.applier.submit_recommendation(rec)
        assert result.status == RecommendationStatus.PENDING

    def test_submit_auto_applied_adds_to_history(self):
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.1,
            confidence=0.9,
            changes={"threshold": 0.5},
        )
        self.applier.submit_recommendation(rec)
        history = self.applier.list_auto_applied()
        assert len(history) == 1
        assert history[0].recommendation_id == rec.id
        assert history[0].success is True

    def test_submit_multiple_recommendations(self):
        for i in range(5):
            rec = _make_rec(title=f"Rec #{i}")
            self.applier.submit_recommendation(rec)
        assert len(self.applier.list_recommendations()) == 5


# ===========================================================================
# Approve Workflow Tests
# ===========================================================================


class TestApproveRecommendation:
    """Tests for PlaybookAutoApplier.approve_recommendation."""

    def setup_method(self):
        self.applier = PlaybookAutoApplier()

    def test_approve_pending_recommendation_succeeds(self):
        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook="high-latency",
            changes={"timeout": 30},
        )
        self.applier.submit_recommendation(rec)

        result = self.applier.approve_recommendation(rec.id, reviewer="alice")
        assert result is not None
        assert result.status == RecommendationStatus.APPROVED
        assert result.reviewed_by == "alice"
        assert result.applied_at is not None

    def test_approve_nonexistent_returns_none(self):
        result = self.applier.approve_recommendation("rec-doesnotexist", reviewer="alice")
        assert result is None

    def test_approve_already_approved_returns_rec_unchanged(self):
        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook="disk-pressure",
            changes={"cleanup": True},
        )
        self.applier.submit_recommendation(rec)
        self.applier.approve_recommendation(rec.id, reviewer="alice")

        # Approve again
        result = self.applier.approve_recommendation(rec.id, reviewer="bob")
        assert result is not None
        assert result.status == RecommendationStatus.APPROVED
        assert result.reviewed_by == "alice", "Reviewer should remain the first approver"

    def test_approve_already_rejected_returns_rec_unchanged(self):
        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook="test",
            changes={"x": 1},
        )
        self.applier.submit_recommendation(rec)
        self.applier.reject_recommendation(rec.id, reviewer="alice", reason="Not needed")

        result = self.applier.approve_recommendation(rec.id, reviewer="bob")
        assert result is not None
        assert result.status == RecommendationStatus.REJECTED

    def test_approve_auto_applied_returns_rec_unchanged(self):
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.1,
            confidence=0.9,
            changes={"threshold": 0.5},
        )
        self.applier.submit_recommendation(rec)
        assert rec.status == RecommendationStatus.AUTO_APPLIED

        result = self.applier.approve_recommendation(rec.id, reviewer="alice")
        assert result is not None
        assert result.status == RecommendationStatus.AUTO_APPLIED

    def test_approve_adds_to_auto_applied_history(self):
        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook="oom-kill",
            changes={"memory_limit": "2Gi"},
        )
        self.applier.submit_recommendation(rec)
        self.applier.approve_recommendation(rec.id, reviewer="alice")

        history = self.applier.list_auto_applied()
        assert any(r.recommendation_id == rec.id for r in history)


# ===========================================================================
# Reject Workflow Tests
# ===========================================================================


class TestRejectRecommendation:
    """Tests for PlaybookAutoApplier.reject_recommendation."""

    def setup_method(self):
        self.applier = PlaybookAutoApplier()

    def test_reject_pending_recommendation(self):
        rec = _make_rec(rec_type=RecommendationType.NEW_PLAYBOOK, risk=0.5)
        self.applier.submit_recommendation(rec)

        result = self.applier.reject_recommendation(rec.id, reviewer="bob", reason="Too risky")
        assert result is not None
        assert result.status == RecommendationStatus.REJECTED
        assert result.reviewed_by == "bob"
        assert result.rejection_reason == "Too risky"

    def test_reject_nonexistent_returns_none(self):
        result = self.applier.reject_recommendation("rec-ghost", reviewer="bob")
        assert result is None

    def test_reject_already_approved_returns_rec_unchanged(self):
        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook="test",
            changes={"val": 1},
        )
        self.applier.submit_recommendation(rec)
        self.applier.approve_recommendation(rec.id, reviewer="alice")

        result = self.applier.reject_recommendation(rec.id, reviewer="bob", reason="Changed mind")
        assert result is not None
        assert result.status == RecommendationStatus.APPROVED
        assert result.rejection_reason is None

    def test_reject_with_empty_reason(self):
        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.3,
            target_playbook="test",
            changes={"a": 1},
        )
        self.applier.submit_recommendation(rec)

        result = self.applier.reject_recommendation(rec.id, reviewer="bob", reason="")
        assert result is not None
        assert result.status == RecommendationStatus.REJECTED
        assert result.rejection_reason == ""

    def test_reject_default_reason_is_empty_string(self):
        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.3,
            target_playbook="test",
            changes={"a": 1},
        )
        self.applier.submit_recommendation(rec)

        result = self.applier.reject_recommendation(rec.id, reviewer="bob")
        assert result is not None
        assert result.rejection_reason == ""


# ===========================================================================
# Get / List Tests
# ===========================================================================


class TestGetAndListRecommendations:
    """Tests for get_recommendation, list_recommendations, list_auto_applied."""

    def setup_method(self):
        self.applier = PlaybookAutoApplier()

    def test_get_existing_recommendation(self):
        rec = _make_rec()
        self.applier.submit_recommendation(rec)
        assert self.applier.get_recommendation(rec.id) is rec

    def test_get_nonexistent_returns_none(self):
        assert self.applier.get_recommendation("rec-nope") is None

    def test_list_empty_returns_empty(self):
        assert self.applier.list_recommendations() == []

    def test_list_all_without_filters(self):
        for _ in range(3):
            self.applier.submit_recommendation(
                _make_rec(
                    rec_type=RecommendationType.PLAYBOOK_UPDATE,
                    risk=0.2,
                    target_playbook="test",
                    changes={"a": 1},
                )
            )
        assert len(self.applier.list_recommendations()) == 3

    def test_list_filter_by_status_pending(self):
        # Submit one that will auto-apply and one that stays pending
        auto_rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.1,
            confidence=0.9,
            changes={"t": 1},
        )
        pending_rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.3,
            target_playbook="test",
            changes={"a": 1},
        )
        self.applier.submit_recommendation(auto_rec)
        self.applier.submit_recommendation(pending_rec)

        pending = self.applier.list_recommendations(status=RecommendationStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].id == pending_rec.id

    def test_list_filter_by_status_auto_applied(self):
        auto_rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.1,
            confidence=0.9,
            changes={"t": 1},
        )
        self.applier.submit_recommendation(auto_rec)

        auto_applied = self.applier.list_recommendations(
            status=RecommendationStatus.AUTO_APPLIED,
        )
        assert len(auto_applied) == 1

    def test_list_filter_by_recommendation_type(self):
        self.applier.submit_recommendation(
            _make_rec(
                rec_type=RecommendationType.PLAYBOOK_UPDATE,
                risk=0.2,
                target_playbook="t",
                changes={"a": 1},
            )
        )
        self.applier.submit_recommendation(
            _make_rec(rec_type=RecommendationType.NEW_PLAYBOOK, risk=0.2)
        )

        updates = self.applier.list_recommendations(
            recommendation_type=RecommendationType.PLAYBOOK_UPDATE,
        )
        assert len(updates) == 1
        assert updates[0].recommendation_type == RecommendationType.PLAYBOOK_UPDATE

    def test_list_filter_by_both_status_and_type(self):
        rec1 = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook="t",
            changes={"a": 1},
        )
        rec2 = _make_rec(rec_type=RecommendationType.NEW_PLAYBOOK, risk=0.2)
        self.applier.submit_recommendation(rec1)
        self.applier.submit_recommendation(rec2)
        self.applier.reject_recommendation(rec1.id, reviewer="alice", reason="No")

        result = self.applier.list_recommendations(
            status=RecommendationStatus.REJECTED,
            recommendation_type=RecommendationType.PLAYBOOK_UPDATE,
        )
        assert len(result) == 1
        assert result[0].id == rec1.id

    def test_list_filter_returns_empty_when_no_match(self):
        self.applier.submit_recommendation(_make_rec())
        result = self.applier.list_recommendations(status=RecommendationStatus.REJECTED)
        assert result == []

    def test_list_sorted_by_created_at_descending(self):
        """Most recent recommendation should be first."""
        recs = []
        for i in range(3):
            rec = _make_rec(title=f"Rec {i}")
            self.applier.submit_recommendation(rec)
            recs.append(rec)

        listed = self.applier.list_recommendations()
        # Verify descending order by created_at
        for i in range(len(listed) - 1):
            assert listed[i].created_at >= listed[i + 1].created_at

    def test_list_auto_applied_empty_initially(self):
        assert self.applier.list_auto_applied() == []

    def test_list_auto_applied_returns_copy(self):
        """Modifying the returned list should not affect internal state."""
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.1,
            confidence=0.9,
            changes={"t": 1},
        )
        self.applier.submit_recommendation(rec)
        history = self.applier.list_auto_applied()
        history.clear()
        assert len(self.applier.list_auto_applied()) == 1


# ===========================================================================
# Internal Apply Method Tests
# ===========================================================================


class TestApplyThresholdAdjustment:
    """Tests for _apply_threshold_adjustment via submission."""

    def setup_method(self):
        self.applier = PlaybookAutoApplier()

    def test_applies_changes_and_records_old_new(self):
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.1,
            confidence=0.9,
            changes={"cpu_threshold": 80, "memory_threshold": 90},
        )
        self.applier.submit_recommendation(rec)

        history = self.applier.list_auto_applied()
        assert len(history) == 1
        applied = history[0].applied_changes
        assert applied["cpu_threshold"] == {"old": None, "new": 80}
        assert applied["memory_threshold"] == {"old": None, "new": 90}

    def test_empty_changes_still_succeeds(self):
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.1,
            confidence=0.9,
            changes={},
        )
        self.applier.submit_recommendation(rec)
        assert rec.status == RecommendationStatus.AUTO_APPLIED


class TestApplyPlaybookUpdate:
    """Tests for _apply_playbook_update."""

    def setup_method(self):
        self.applier = PlaybookAutoApplier()

    def test_succeeds_with_target_playbook_no_loader(self):
        """Without a loader, playbook update succeeds (no lookup needed)."""
        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook="high-latency",
            changes={"timeout": 30},
        )
        self.applier.submit_recommendation(rec)
        result = self.applier.approve_recommendation(rec.id, reviewer="alice")
        assert result is not None
        assert result.status == RecommendationStatus.APPROVED

    def test_fails_without_target_playbook(self):
        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook=None,
            changes={"timeout": 30},
        )
        self.applier.submit_recommendation(rec)
        result = self.applier.approve_recommendation(rec.id, reviewer="alice")
        assert result is not None
        assert result.status == RecommendationStatus.FAILED

    def test_fails_when_loader_cannot_find_playbook(self):
        mock_loader = MagicMock()
        mock_loader.get.return_value = None
        applier = PlaybookAutoApplier(playbook_loader=mock_loader)

        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook="nonexistent-playbook",
            changes={"timeout": 30},
        )
        applier.submit_recommendation(rec)
        result = applier.approve_recommendation(rec.id, reviewer="alice")
        assert result is not None
        assert result.status == RecommendationStatus.FAILED

    def test_succeeds_when_loader_finds_playbook(self):
        mock_loader = MagicMock()
        mock_loader.get.return_value = MagicMock()  # Found
        applier = PlaybookAutoApplier(playbook_loader=mock_loader)

        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook="oom-kill",
            changes={"memory_limit": "2Gi"},
        )
        applier.submit_recommendation(rec)
        result = applier.approve_recommendation(rec.id, reviewer="alice")
        assert result is not None
        assert result.status == RecommendationStatus.APPROVED

    def test_applied_changes_include_playbook_name_and_updates(self):
        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook="cpu-throttling",
            changes={"cpu_limit": "4000m"},
        )
        self.applier.submit_recommendation(rec)
        self.applier.approve_recommendation(rec.id, reviewer="alice")

        history = self.applier.list_auto_applied()
        assert len(history) == 1
        assert history[0].applied_changes["playbook"] == "cpu-throttling"
        assert history[0].applied_changes["updates"] == {"cpu_limit": "4000m"}


class TestApplyAlertTuning:
    """Tests for _apply_alert_tuning."""

    def setup_method(self):
        self.applier = PlaybookAutoApplier()

    def test_auto_applies_low_risk_alert_tuning(self):
        rec = _make_rec(
            rec_type=RecommendationType.ALERT_TUNING,
            risk=0.1,
            changes={"suppress_noisy_alert": True},
        )
        self.applier.submit_recommendation(rec)
        assert rec.status == RecommendationStatus.AUTO_APPLIED

    def test_applied_changes_contain_alert_config(self):
        changes = {"alert_name": "CPUHighUsage", "new_threshold": 95}
        rec = _make_rec(
            rec_type=RecommendationType.ALERT_TUNING,
            risk=0.2,
            changes=changes,
        )
        self.applier.submit_recommendation(rec)

        history = self.applier.list_auto_applied()
        assert history[0].applied_changes == {"alert_config": changes}


class TestApplyNewPlaybook:
    """Tests for _apply_new_playbook."""

    def setup_method(self):
        self.applier = PlaybookAutoApplier()

    def test_new_playbook_requires_manual_approval_then_succeeds(self):
        rec = _make_rec(
            rec_type=RecommendationType.NEW_PLAYBOOK,
            risk=0.2,
            changes={"playbook_content": {"name": "new-pb", "steps": []}},
        )
        self.applier.submit_recommendation(rec)
        assert rec.status == RecommendationStatus.PENDING

        result = self.applier.approve_recommendation(rec.id, reviewer="admin")
        assert result is not None
        assert result.status == RecommendationStatus.APPROVED

    def test_new_playbook_fails_without_playbook_content(self):
        rec = _make_rec(
            rec_type=RecommendationType.NEW_PLAYBOOK,
            risk=0.2,
            changes={},
        )
        self.applier.submit_recommendation(rec)

        result = self.applier.approve_recommendation(rec.id, reviewer="admin")
        assert result is not None
        assert result.status == RecommendationStatus.FAILED

    def test_new_playbook_applied_changes(self):
        content = {"name": "new-pb", "steps": ["step1", "step2"]}
        rec = _make_rec(
            rec_type=RecommendationType.NEW_PLAYBOOK,
            risk=0.1,
            changes={"playbook_content": content},
        )
        self.applier.submit_recommendation(rec)
        self.applier.approve_recommendation(rec.id, reviewer="admin")

        history = self.applier.list_auto_applied()
        assert len(history) == 1
        assert history[0].applied_changes["new_playbook"]["playbook_content"] == content


# ===========================================================================
# Error Handling and Edge Cases
# ===========================================================================


class TestErrorHandling:
    """Tests for error paths and edge cases in apply logic."""

    def setup_method(self):
        self.applier = PlaybookAutoApplier()

    def test_apply_exception_results_in_failed_status(self):
        """If _apply_recommendation raises internally, the rec is marked FAILED."""
        rec = _make_rec(
            rec_type=RecommendationType.PLAYBOOK_UPDATE,
            risk=0.2,
            target_playbook="test",
            changes={"a": 1},
        )
        self.applier.submit_recommendation(rec)

        # Force an exception in the apply path
        self.applier._apply_playbook_update = MagicMock(side_effect=RuntimeError("boom"))
        result = self.applier.approve_recommendation(rec.id, reviewer="alice")

        assert result is not None
        assert result.status == RecommendationStatus.FAILED

    def test_submit_auto_apply_failure_marks_failed(self):
        """If auto-apply fails during submission, status becomes FAILED."""
        applier = PlaybookAutoApplier()
        applier._apply_threshold_adjustment = MagicMock(
            side_effect=RuntimeError("disk full"),
        )
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.1,
            confidence=0.9,
            changes={"t": 1},
        )
        result = applier.submit_recommendation(rec)
        assert result.status == RecommendationStatus.FAILED

    def test_risk_score_zero_threshold_adjustment_auto_approves(self):
        rec = _make_rec(
            rec_type=RecommendationType.THRESHOLD_ADJUSTMENT,
            risk=0.0,
            confidence=1.0,
            changes={"threshold": 50},
        )
        result = self.applier.submit_recommendation(rec)
        assert result.status == RecommendationStatus.AUTO_APPLIED

    def test_risk_score_one_is_manual_only(self):
        rec = _make_rec(risk=1.0)
        policy = self.applier.classify_approval_policy(rec)
        assert policy == ApprovalPolicy.MANUAL_ONLY


# ===========================================================================
# Constructor Configuration Tests
# ===========================================================================


class TestPlaybookAutoApplierInit:
    """Tests for PlaybookAutoApplier initialization and configuration."""

    def test_default_auto_apply_enabled(self):
        applier = PlaybookAutoApplier()
        assert applier._auto_apply_enabled is True

    def test_auto_apply_disabled(self):
        applier = PlaybookAutoApplier(auto_apply_enabled=False)
        assert applier._auto_apply_enabled is False

    def test_default_loader_is_none(self):
        applier = PlaybookAutoApplier()
        assert applier._loader is None

    def test_custom_loader_stored(self):
        mock_loader = MagicMock()
        applier = PlaybookAutoApplier(playbook_loader=mock_loader)
        assert applier._loader is mock_loader

    def test_class_level_risk_thresholds(self):
        assert pytest.approx(0.3) == PlaybookAutoApplier.AUTO_APPROVE_MAX_RISK
        assert pytest.approx(0.7) == PlaybookAutoApplier.REVIEW_MAX_RISK

    def test_starts_with_empty_recommendations(self):
        applier = PlaybookAutoApplier()
        assert applier.list_recommendations() == []
        assert applier.list_auto_applied() == []
