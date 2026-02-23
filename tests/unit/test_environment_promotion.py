"""Tests for shieldops.config.environment_promotion – PromotionManager."""

from __future__ import annotations

import pytest

from shieldops.config.environment_promotion import (
    PromotableType,
    PromotionEnvironment,
    PromotionManager,
    PromotionStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seeded_manager() -> PromotionManager:
    """Return a manager with divergent dev/staging/prod snapshots."""
    mgr = PromotionManager()
    mgr.set_resource("development", "config", "timeout", {"value": 30, "unit": "s"})
    mgr.set_resource("staging", "config", "timeout", {"value": 20, "unit": "s"})
    mgr.set_resource("production", "config", "timeout", {"value": 10, "unit": "s"})
    mgr.set_resource("development", "feature_flag", "dark_mode", {"enabled": True})
    mgr.set_resource("staging", "feature_flag", "dark_mode", {"enabled": False})
    return mgr


# ---------------------------------------------------------------------------
# Snapshot management
# ---------------------------------------------------------------------------


class TestSnapshotManagement:
    def test_set_and_get_resource(self):
        mgr = PromotionManager()
        mgr.set_resource("development", "config", "timeout", {"value": 30})
        result = mgr.get_resource("development", "config", "timeout")
        assert result == {"value": 30}

    def test_get_resource_missing_returns_none(self):
        mgr = PromotionManager()
        assert mgr.get_resource("development", "config", "nonexistent") is None

    def test_get_snapshot_returns_full_env(self):
        mgr = _seeded_manager()
        snap = mgr.get_snapshot("development")
        assert "config" in snap
        assert "feature_flag" in snap
        assert "timeout" in snap["config"]

    def test_get_snapshot_empty_env(self):
        mgr = PromotionManager()
        snap = mgr.get_snapshot("production")
        assert snap == {}  # initialized but empty by default

    def test_overwrite_resource(self):
        mgr = PromotionManager()
        mgr.set_resource("development", "config", "key", {"v": 1})
        mgr.set_resource("development", "config", "key", {"v": 2})
        assert mgr.get_resource("development", "config", "key") == {"v": 2}


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------


class TestDiffComputation:
    def test_compute_diffs_finds_differences(self):
        mgr = _seeded_manager()
        diffs = mgr.compute_diffs("development", "staging")
        assert len(diffs) >= 1
        config_diff = [d for d in diffs if d.resource_name == "timeout"]
        assert len(config_diff) == 1
        assert any(c.field == "value" for c in config_diff[0].changes)

    def test_compute_diffs_detects_new_resources(self):
        mgr = PromotionManager()
        mgr.set_resource("development", "config", "new_key", {"value": 42})
        # staging has no resources at all
        diffs = mgr.compute_diffs("development", "staging")
        assert len(diffs) == 1
        assert diffs[0].is_new is True
        assert diffs[0].resource_name == "new_key"

    def test_compute_diffs_no_differences(self):
        mgr = PromotionManager()
        mgr.set_resource("development", "config", "k", {"v": 1})
        mgr.set_resource("staging", "config", "k", {"v": 1})
        diffs = mgr.compute_diffs("development", "staging")
        assert len(diffs) == 0

    def test_compute_diffs_includes_all_changed_fields(self):
        mgr = PromotionManager()
        mgr.set_resource("development", "config", "db", {"host": "new-host", "port": 5433})
        mgr.set_resource("staging", "config", "db", {"host": "old-host", "port": 5432})
        diffs = mgr.compute_diffs("development", "staging")
        assert len(diffs) == 1
        fields = {c.field for c in diffs[0].changes}
        assert "host" in fields
        assert "port" in fields

    def test_compute_diffs_records_source_and_target_values(self):
        mgr = PromotionManager()
        mgr.set_resource("development", "config", "x", {"a": 1})
        mgr.set_resource("staging", "config", "x", {"a": 2})
        diffs = mgr.compute_diffs("development", "staging")
        assert diffs[0].source_value == {"a": 1}
        assert diffs[0].target_value == {"a": 2}


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


class TestPreview:
    def test_preview_returns_diffs_without_creating_request(self):
        mgr = _seeded_manager()
        diffs = mgr.preview("development", "staging")
        assert len(diffs) >= 1
        # No request should be stored
        assert mgr.list_requests() == []

    def test_preview_matches_compute_diffs(self):
        mgr = _seeded_manager()
        assert mgr.preview("development", "staging") == mgr.compute_diffs("development", "staging")


# ---------------------------------------------------------------------------
# Request creation
# ---------------------------------------------------------------------------


class TestCreateRequest:
    def test_create_request_with_computed_diffs(self):
        mgr = _seeded_manager()
        req = mgr.create_request("development", "staging", requested_by="alice")
        assert req.source_env == PromotionEnvironment.DEVELOPMENT
        assert req.target_env == PromotionEnvironment.STAGING
        assert req.requested_by == "alice"
        assert len(req.diffs) >= 1

    def test_auto_approve_for_non_production_targets(self):
        mgr = _seeded_manager()
        req = mgr.create_request("development", "staging")
        assert req.status == PromotionStatus.APPROVED

    def test_require_approval_for_production(self):
        mgr = _seeded_manager()
        req = mgr.create_request("staging", "production")
        assert req.status == PromotionStatus.PENDING_REVIEW

    def test_skip_approval_when_disabled(self):
        mgr = PromotionManager(require_approval_for_prod=False)
        mgr.set_resource("staging", "config", "k", {"v": 1})
        req = mgr.create_request("staging", "production")
        assert req.status == PromotionStatus.APPROVED

    def test_invalid_source_env_raises_valueerror(self):
        mgr = PromotionManager()
        with pytest.raises(ValueError, match="not in allowed"):
            mgr.create_request("production", "staging")

    def test_resource_type_filtering_on_create(self):
        mgr = _seeded_manager()
        req = mgr.create_request("development", "staging", resource_types=["feature_flag"])
        for diff in req.diffs:
            assert diff.resource_type == PromotableType.FEATURE_FLAG


# ---------------------------------------------------------------------------
# Approve / Reject lifecycle
# ---------------------------------------------------------------------------


class TestApproveReject:
    def test_approve_pending_request(self):
        mgr = _seeded_manager()
        req = mgr.create_request("staging", "production")
        assert req.status == PromotionStatus.PENDING_REVIEW
        approved = mgr.approve(req.id, reviewed_by="bob", comment="LGTM")
        assert approved is not None
        assert approved.status == PromotionStatus.APPROVED
        assert approved.reviewed_by == "bob"
        assert approved.review_comment == "LGTM"

    def test_approve_non_pending_returns_none(self):
        mgr = _seeded_manager()
        req = mgr.create_request("development", "staging")  # auto-approved
        assert mgr.approve(req.id) is None

    def test_reject_pending_request(self):
        mgr = _seeded_manager()
        req = mgr.create_request("staging", "production")
        rejected = mgr.reject(req.id, reviewed_by="carol", comment="Needs work")
        assert rejected is not None
        assert rejected.status == PromotionStatus.REJECTED
        assert rejected.review_comment == "Needs work"

    def test_reject_non_pending_returns_none(self):
        mgr = _seeded_manager()
        req = mgr.create_request("development", "staging")
        assert mgr.reject(req.id) is None

    def test_approve_unknown_id_returns_none(self):
        mgr = PromotionManager()
        assert mgr.approve("no-such-id") is None


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


class TestApply:
    def test_apply_copies_source_value_to_target(self):
        mgr = _seeded_manager()
        req = mgr.create_request("development", "staging")
        mgr.apply(req.id)
        # timeout in staging should now match development
        assert mgr.get_resource("staging", "config", "timeout") == {"value": 30, "unit": "s"}

    def test_apply_sets_status_applied(self):
        mgr = _seeded_manager()
        req = mgr.create_request("development", "staging")
        applied = mgr.apply(req.id)
        assert applied is not None
        assert applied.status == PromotionStatus.APPLIED
        assert applied.applied_at is not None

    def test_apply_unapproved_returns_none(self):
        mgr = _seeded_manager()
        req = mgr.create_request("staging", "production")  # pending
        assert mgr.apply(req.id) is None

    def test_apply_unknown_id_returns_none(self):
        mgr = PromotionManager()
        assert mgr.apply("no-such-id") is None

    def test_apply_new_resource_creates_in_target(self):
        mgr = PromotionManager()
        mgr.set_resource("development", "config", "brand_new", {"enabled": True})
        req = mgr.create_request("development", "staging")
        mgr.apply(req.id)
        assert mgr.get_resource("staging", "config", "brand_new") == {"enabled": True}


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


class TestRollback:
    def test_rollback_restores_target_value(self):
        mgr = _seeded_manager()
        original = mgr.get_resource("staging", "config", "timeout")
        req = mgr.create_request("development", "staging")
        mgr.apply(req.id)
        mgr.rollback(req.id)
        assert mgr.get_resource("staging", "config", "timeout") == original

    def test_rollback_removes_new_resources(self):
        mgr = PromotionManager()
        mgr.set_resource("development", "config", "new_key", {"v": 1})
        req = mgr.create_request("development", "staging")
        mgr.apply(req.id)
        assert mgr.get_resource("staging", "config", "new_key") is not None
        mgr.rollback(req.id)
        assert mgr.get_resource("staging", "config", "new_key") is None

    def test_rollback_sets_status_rolled_back(self):
        mgr = _seeded_manager()
        req = mgr.create_request("development", "staging")
        mgr.apply(req.id)
        rolled = mgr.rollback(req.id)
        assert rolled is not None
        assert rolled.status == PromotionStatus.ROLLED_BACK
        assert rolled.rolled_back_at is not None

    def test_rollback_unapplied_returns_none(self):
        mgr = _seeded_manager()
        req = mgr.create_request("development", "staging")
        # Not applied yet
        assert mgr.rollback(req.id) is None

    def test_rollback_unknown_id_returns_none(self):
        mgr = PromotionManager()
        assert mgr.rollback("no-such-id") is None


# ---------------------------------------------------------------------------
# List requests
# ---------------------------------------------------------------------------


class TestListRequests:
    def test_list_requests_returns_all(self):
        mgr = _seeded_manager()
        mgr.create_request("development", "staging")
        mgr.create_request("staging", "production")
        reqs = mgr.list_requests()
        assert len(reqs) == 2

    def test_list_requests_with_status_filter(self):
        mgr = _seeded_manager()
        mgr.create_request("development", "staging")  # auto-approved
        mgr.create_request("staging", "production")  # pending
        approved = mgr.list_requests(status=PromotionStatus.APPROVED)
        assert all(r.status == PromotionStatus.APPROVED for r in approved)
        pending = mgr.list_requests(status=PromotionStatus.PENDING_REVIEW)
        assert all(r.status == PromotionStatus.PENDING_REVIEW for r in pending)

    def test_list_requests_ordered_by_created_at_desc(self):
        mgr = _seeded_manager()
        mgr.create_request("development", "staging")
        mgr.create_request("development", "staging")
        reqs = mgr.list_requests()
        assert reqs[0].created_at >= reqs[1].created_at

    def test_list_requests_respects_limit(self):
        mgr = _seeded_manager()
        for _ in range(5):
            mgr.create_request("development", "staging")
        reqs = mgr.list_requests(limit=2)
        assert len(reqs) == 2


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_by_status(self):
        mgr = _seeded_manager()
        mgr.create_request("development", "staging")  # approved
        mgr.create_request("staging", "production")  # pending
        stats = mgr.get_stats()
        assert stats["total_requests"] == 2
        assert "approved" in stats["by_status"]
        assert "pending_review" in stats["by_status"]

    def test_stats_environments(self):
        mgr = PromotionManager()
        stats = mgr.get_stats()
        assert "development" in stats["environments"]
        assert "staging" in stats["environments"]
        assert "production" in stats["environments"]

    def test_stats_empty(self):
        mgr = PromotionManager()
        stats = mgr.get_stats()
        assert stats["total_requests"] == 0
        assert stats["by_status"] == {}
