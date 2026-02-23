"""Tests for shieldops.changes.release_manager — ReleaseManagementTracker."""

from __future__ import annotations

from shieldops.changes.release_manager import (
    ApprovalOutcome,
    Release,
    ReleaseApproval,
    ReleaseManagementTracker,
    ReleaseStats,
    ReleaseStatus,
    ReleaseType,
)


def _engine(**kw) -> ReleaseManagementTracker:
    return ReleaseManagementTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_draft(self):
        assert ReleaseStatus.DRAFT == "draft"

    def test_status_pending(self):
        assert ReleaseStatus.PENDING_APPROVAL == "pending_approval"

    def test_status_approved(self):
        assert ReleaseStatus.APPROVED == "approved"

    def test_status_deploying(self):
        assert ReleaseStatus.DEPLOYING == "deploying"

    def test_status_released(self):
        assert ReleaseStatus.RELEASED == "released"

    def test_status_rolled_back(self):
        assert ReleaseStatus.ROLLED_BACK == "rolled_back"

    def test_type_major(self):
        assert ReleaseType.MAJOR == "major"

    def test_type_minor(self):
        assert ReleaseType.MINOR == "minor"

    def test_type_patch(self):
        assert ReleaseType.PATCH == "patch"

    def test_type_hotfix(self):
        assert ReleaseType.HOTFIX == "hotfix"

    def test_approval_approved(self):
        assert ApprovalOutcome.APPROVED == "approved"

    def test_approval_rejected(self):
        assert ApprovalOutcome.REJECTED == "rejected"

    def test_approval_pending(self):
        assert ApprovalOutcome.PENDING == "pending"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_release_defaults(self):
        r = Release(version="1.0.0", service="svc-a")
        assert r.id
        assert r.status == ReleaseStatus.DRAFT
        assert r.release_type == ReleaseType.MINOR
        assert r.approvals == []
        assert r.rejections == []
        assert r.released_at is None
        assert r.rolled_back_at is None
        assert r.description == ""
        assert r.changes == []

    def test_approval_defaults(self):
        a = ReleaseApproval(release_id="r-1", approver="alice")
        assert a.outcome == ApprovalOutcome.PENDING
        assert a.comment == ""

    def test_stats_defaults(self):
        s = ReleaseStats()
        assert s.total_releases == 0
        assert s.avg_approval_count == 0.0


# ---------------------------------------------------------------------------
# create_release
# ---------------------------------------------------------------------------


class TestCreateRelease:
    def test_basic_create(self):
        eng = _engine()
        release = eng.create_release("1.0.0", "svc-a")
        assert release.version == "1.0.0"
        assert release.service == "svc-a"
        assert eng.get_release(release.id) is not None

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.create_release("1.0.0", "svc-a")
        r2 = eng.create_release("2.0.0", "svc-a")
        assert r1.id != r2.id

    def test_evicts_at_max(self):
        eng = _engine(max_releases=2)
        r1 = eng.create_release("1.0", "svc")
        eng.create_release("2.0", "svc")
        eng.create_release("3.0", "svc")
        assert eng.get_release(r1.id) is None

    def test_create_with_kwargs(self):
        eng = _engine()
        release = eng.create_release(
            "1.0",
            "svc-a",
            release_type=ReleaseType.HOTFIX,
            description="Emergency fix",
            changes=["Fixed auth bug"],
        )
        assert release.release_type == ReleaseType.HOTFIX
        assert release.description == "Emergency fix"
        assert len(release.changes) == 1

    def test_get_release_not_found(self):
        eng = _engine()
        assert eng.get_release("nonexistent") is None


# ---------------------------------------------------------------------------
# list_releases
# ---------------------------------------------------------------------------


class TestListReleases:
    def test_list_all(self):
        eng = _engine()
        eng.create_release("1.0", "svc-a")
        eng.create_release("2.0", "svc-b")
        assert len(eng.list_releases()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.create_release("1.0", "svc-a")
        eng.create_release("2.0", "svc-b")
        results = eng.list_releases(service="svc-a")
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.create_release("1.0", "svc-a")
        r2 = eng.create_release("2.0", "svc-b")
        eng.submit_for_approval(r2.id)
        results = eng.list_releases(status=ReleaseStatus.PENDING_APPROVAL)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# approval workflow
# ---------------------------------------------------------------------------


class TestApprovalWorkflow:
    def test_submit_for_approval(self):
        eng = _engine()
        release = eng.create_release("1.0", "svc-a")
        result = eng.submit_for_approval(release.id)
        assert result is not None
        assert result.status == ReleaseStatus.PENDING_APPROVAL

    def test_submit_not_found(self):
        eng = _engine()
        assert eng.submit_for_approval("nonexistent") is None

    def test_approve(self):
        eng = _engine()
        release = eng.create_release("1.0", "svc-a")
        approval = eng.approve_release(release.id, "alice")
        assert approval is not None
        assert approval.outcome == ApprovalOutcome.APPROVED
        assert eng.get_release(release.id).status == ReleaseStatus.APPROVED

    def test_approve_adds_approver(self):
        eng = _engine()
        release = eng.create_release("1.0", "svc-a")
        eng.approve_release(release.id, "alice")
        assert "alice" in eng.get_release(release.id).approvals

    def test_reject(self):
        eng = _engine()
        release = eng.create_release("1.0", "svc-a")
        rejection = eng.reject_release(release.id, "bob", comment="Not ready")
        assert rejection is not None
        assert rejection.outcome == ApprovalOutcome.REJECTED
        assert rejection.comment == "Not ready"
        assert eng.get_release(release.id).status == ReleaseStatus.DRAFT

    def test_reject_adds_rejector(self):
        eng = _engine()
        release = eng.create_release("1.0", "svc-a")
        eng.reject_release(release.id, "bob")
        assert "bob" in eng.get_release(release.id).rejections

    def test_approve_not_found(self):
        eng = _engine()
        assert eng.approve_release("nonexistent", "alice") is None

    def test_reject_not_found(self):
        eng = _engine()
        assert eng.reject_release("nonexistent", "alice") is None


# ---------------------------------------------------------------------------
# mark_released / rollback
# ---------------------------------------------------------------------------


class TestMarkReleased:
    def test_release_after_approval(self):
        eng = _engine()
        release = eng.create_release("1.0", "svc-a")
        eng.approve_release(release.id, "alice")
        result = eng.mark_released(release.id)
        assert result is not None
        assert result.status == ReleaseStatus.RELEASED
        assert result.released_at is not None

    def test_release_without_approval_blocked(self):
        eng = _engine(require_approval=True)
        release = eng.create_release("1.0", "svc-a")
        result = eng.mark_released(release.id)
        assert result is None

    def test_release_no_approval_required(self):
        eng = _engine(require_approval=False)
        release = eng.create_release("1.0", "svc-a")
        result = eng.mark_released(release.id)
        assert result is not None
        assert result.status == ReleaseStatus.RELEASED

    def test_release_not_found(self):
        eng = _engine()
        assert eng.mark_released("nonexistent") is None


class TestRollback:
    def test_rollback(self):
        eng = _engine()
        release = eng.create_release("1.0", "svc-a")
        eng.approve_release(release.id, "alice")
        eng.mark_released(release.id)
        result = eng.rollback_release(release.id)
        assert result is not None
        assert result.status == ReleaseStatus.ROLLED_BACK
        assert result.rolled_back_at is not None

    def test_rollback_not_found(self):
        eng = _engine()
        assert eng.rollback_release("nonexistent") is None

    def test_rollback_draft(self):
        eng = _engine()
        release = eng.create_release("1.0", "svc-a")
        result = eng.rollback_release(release.id)
        assert result is not None
        assert result.status == ReleaseStatus.ROLLED_BACK


# ---------------------------------------------------------------------------
# release notes / stats
# ---------------------------------------------------------------------------


class TestReleaseNotes:
    def test_generate_notes(self):
        eng = _engine()
        release = eng.create_release(
            "1.0",
            "svc-a",
            description="Initial release",
            changes=["Added auth", "Added billing"],
        )
        notes = eng.generate_release_notes(release.id)
        assert notes["version"] == "1.0"
        assert len(notes["changes"]) == 2
        assert notes["description"] == "Initial release"
        assert notes["service"] == "svc-a"

    def test_notes_not_found(self):
        eng = _engine()
        assert eng.generate_release_notes("nonexistent") == {}

    def test_notes_include_approvals(self):
        eng = _engine()
        release = eng.create_release("1.0", "svc-a")
        eng.approve_release(release.id, "alice")
        notes = eng.generate_release_notes(release.id)
        assert "alice" in notes["approvals"]


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_releases"] == 0
        assert stats["total_approvals"] == 0
        assert stats["avg_approval_count"] == 0.0

    def test_populated_stats(self):
        eng = _engine()
        r = eng.create_release("1.0", "svc-a")
        eng.approve_release(r.id, "alice")
        stats = eng.get_stats()
        assert stats["total_releases"] == 1
        assert stats["total_approvals"] == 1

    def test_status_distribution(self):
        eng = _engine()
        eng.create_release("1.0", "svc-a")
        eng.create_release("2.0", "svc-b")
        stats = eng.get_stats()
        assert stats["status_distribution"][ReleaseStatus.DRAFT] == 2

    def test_type_distribution(self):
        eng = _engine()
        eng.create_release("1.0", "svc-a", release_type=ReleaseType.MAJOR)
        eng.create_release("2.0", "svc-b", release_type=ReleaseType.PATCH)
        stats = eng.get_stats()
        assert stats["type_distribution"][ReleaseType.MAJOR] == 1
        assert stats["type_distribution"][ReleaseType.PATCH] == 1
