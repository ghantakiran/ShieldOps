"""Tests for shieldops.operations.runbook_versioner — RunbookVersionManager."""

from __future__ import annotations

from shieldops.operations.runbook_versioner import (
    ChangeType,
    RunbookCategory,
    RunbookDiff,
    RunbookVersion,
    RunbookVersionManager,
    VersionReport,
    VersionStatus,
)


def _engine(**kw) -> RunbookVersionManager:
    return RunbookVersionManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # VersionStatus (5)
    def test_status_draft(self):
        assert VersionStatus.DRAFT == "draft"

    def test_status_pending_review(self):
        assert VersionStatus.PENDING_REVIEW == "pending_review"

    def test_status_approved(self):
        assert VersionStatus.APPROVED == "approved"

    def test_status_published(self):
        assert VersionStatus.PUBLISHED == "published"

    def test_status_deprecated(self):
        assert VersionStatus.DEPRECATED == "deprecated"

    # ChangeType (5)
    def test_change_step_added(self):
        assert ChangeType.STEP_ADDED == "step_added"

    def test_change_step_removed(self):
        assert ChangeType.STEP_REMOVED == "step_removed"

    def test_change_step_modified(self):
        assert ChangeType.STEP_MODIFIED == "step_modified"

    def test_change_parameter_changed(self):
        assert ChangeType.PARAMETER_CHANGED == "parameter_changed"

    def test_change_reordered(self):
        assert ChangeType.REORDERED == "reordered"

    # RunbookCategory (5)
    def test_category_incident_response(self):
        assert RunbookCategory.INCIDENT_RESPONSE == "incident_response"

    def test_category_deployment(self):
        assert RunbookCategory.DEPLOYMENT == "deployment"

    def test_category_maintenance(self):
        assert RunbookCategory.MAINTENANCE == "maintenance"

    def test_category_security(self):
        assert RunbookCategory.SECURITY == "security"

    def test_category_recovery(self):
        assert RunbookCategory.RECOVERY == "recovery"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_runbook_version_defaults(self):
        v = RunbookVersion()
        assert v.id
        assert v.runbook_id == ""
        assert v.version_number == 1
        assert v.status == VersionStatus.DRAFT
        assert v.category == RunbookCategory.INCIDENT_RESPONSE
        assert v.author == ""
        assert v.change_type == ChangeType.STEP_ADDED
        assert v.change_summary == ""
        assert v.content_hash == ""
        assert v.steps == []
        assert v.created_at > 0

    def test_runbook_diff_defaults(self):
        d = RunbookDiff()
        assert d.id
        assert d.runbook_id == ""
        assert d.from_version == 0
        assert d.to_version == 0
        assert d.changes == []
        assert d.additions == 0
        assert d.deletions == 0
        assert d.created_at > 0

    def test_version_report_defaults(self):
        r = VersionReport()
        assert r.total_runbooks == 0
        assert r.total_versions == 0
        assert r.avg_versions_per_runbook == 0.0
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.stale_runbooks == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# create_version
# ---------------------------------------------------------------------------


class TestCreateVersion:
    def test_basic_creation(self):
        eng = _engine()
        v = eng.create_version(
            runbook_id="rb-001",
            steps=["Check logs", "Restart service", "Verify health"],
            category=RunbookCategory.INCIDENT_RESPONSE,
            author="alice",
            change_type=ChangeType.STEP_ADDED,
            change_summary="Initial version",
        )
        assert v.runbook_id == "rb-001"
        assert v.version_number == 1
        assert v.status == VersionStatus.DRAFT
        assert v.author == "alice"
        assert len(v.steps) == 3
        assert v.content_hash != ""

    def test_auto_increment_version(self):
        eng = _engine()
        v1 = eng.create_version(runbook_id="rb-001", steps=["Step 1"])
        v2 = eng.create_version(runbook_id="rb-001", steps=["Step 1", "Step 2"])
        assert v1.version_number == 1
        assert v2.version_number == 2

    def test_eviction_at_max(self):
        eng = _engine(max_versions=3)
        for i in range(5):
            eng.create_version(runbook_id=f"rb-{i}", steps=[f"Step {i}"])
        assert len(eng._items) == 3


# ---------------------------------------------------------------------------
# get_version
# ---------------------------------------------------------------------------


class TestGetVersion:
    def test_found(self):
        eng = _engine()
        v = eng.create_version(runbook_id="rb-001", steps=["Step 1"])
        assert eng.get_version(v.id) is not None
        assert eng.get_version(v.id).runbook_id == "rb-001"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_version("nonexistent") is None


# ---------------------------------------------------------------------------
# list_versions
# ---------------------------------------------------------------------------


class TestListVersions:
    def test_list_all(self):
        eng = _engine()
        eng.create_version(runbook_id="rb-001")
        eng.create_version(runbook_id="rb-002")
        assert len(eng.list_versions()) == 2

    def test_filter_by_runbook_id(self):
        eng = _engine()
        eng.create_version(runbook_id="rb-001")
        eng.create_version(runbook_id="rb-002")
        results = eng.list_versions(runbook_id="rb-001")
        assert len(results) == 1
        assert results[0].runbook_id == "rb-001"

    def test_filter_by_status(self):
        eng = _engine()
        v1 = eng.create_version(runbook_id="rb-001")
        eng.create_version(runbook_id="rb-002")
        eng.approve_version(v1.id)
        results = eng.list_versions(status=VersionStatus.APPROVED)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# diff_versions
# ---------------------------------------------------------------------------


class TestDiffVersions:
    def test_basic_diff(self):
        eng = _engine()
        v1 = eng.create_version(
            runbook_id="rb-001",
            steps=["Check logs", "Restart service"],
        )
        v2 = eng.create_version(
            runbook_id="rb-001",
            steps=["Check logs", "Scale up", "Verify health"],
        )
        diff = eng.diff_versions(v1.id, v2.id)
        assert diff is not None
        assert diff.runbook_id == "rb-001"
        assert diff.from_version == 1
        assert diff.to_version == 2
        assert diff.additions >= 1
        assert diff.deletions >= 1

    def test_diff_same_steps(self):
        eng = _engine()
        v1 = eng.create_version(
            runbook_id="rb-001",
            steps=["Step A", "Step B"],
        )
        v2 = eng.create_version(
            runbook_id="rb-001",
            steps=["Step A", "Step B"],
        )
        diff = eng.diff_versions(v1.id, v2.id)
        assert diff is not None
        assert diff.additions == 0
        assert diff.deletions == 0

    def test_diff_nonexistent_version(self):
        eng = _engine()
        v1 = eng.create_version(runbook_id="rb-001")
        diff = eng.diff_versions(v1.id, "nonexistent")
        assert diff is None

    def test_diff_different_runbooks(self):
        eng = _engine()
        v1 = eng.create_version(runbook_id="rb-001")
        v2 = eng.create_version(runbook_id="rb-002")
        diff = eng.diff_versions(v1.id, v2.id)
        assert diff is None


# ---------------------------------------------------------------------------
# approve_version
# ---------------------------------------------------------------------------


class TestApproveVersion:
    def test_approve_existing(self):
        eng = _engine()
        v = eng.create_version(runbook_id="rb-001")
        assert v.status == VersionStatus.DRAFT
        result = eng.approve_version(v.id)
        assert result is not None
        assert result.status == VersionStatus.APPROVED

    def test_approve_nonexistent(self):
        eng = _engine()
        assert eng.approve_version("bogus") is None


# ---------------------------------------------------------------------------
# publish_version
# ---------------------------------------------------------------------------


class TestPublishVersion:
    def test_publish_existing(self):
        eng = _engine()
        v = eng.create_version(runbook_id="rb-001")
        result = eng.publish_version(v.id)
        assert result is not None
        assert result.status == VersionStatus.PUBLISHED

    def test_publish_deprecates_previous(self):
        eng = _engine()
        v1 = eng.create_version(runbook_id="rb-001")
        eng.publish_version(v1.id)
        v2 = eng.create_version(runbook_id="rb-001")
        eng.publish_version(v2.id)
        assert v1.status == VersionStatus.DEPRECATED
        assert v2.status == VersionStatus.PUBLISHED

    def test_publish_nonexistent(self):
        eng = _engine()
        assert eng.publish_version("bogus") is None


# ---------------------------------------------------------------------------
# rollback_to_version
# ---------------------------------------------------------------------------


class TestRollbackToVersion:
    def test_basic_rollback(self):
        eng = _engine()
        v1 = eng.create_version(
            runbook_id="rb-001",
            steps=["Original step"],
            category=RunbookCategory.DEPLOYMENT,
        )
        eng.publish_version(v1.id)
        v2 = eng.create_version(
            runbook_id="rb-001",
            steps=["Bad step"],
        )
        eng.publish_version(v2.id)
        rolled = eng.rollback_to_version("rb-001", v1.id)
        assert rolled is not None
        assert rolled.steps == ["Original step"]
        assert rolled.status == VersionStatus.PUBLISHED
        assert rolled.change_summary == "Rollback to v1"

    def test_rollback_nonexistent(self):
        eng = _engine()
        assert eng.rollback_to_version("rb-001", "bogus") is None

    def test_rollback_wrong_runbook(self):
        eng = _engine()
        v = eng.create_version(runbook_id="rb-001")
        result = eng.rollback_to_version("rb-002", v.id)
        assert result is None


# ---------------------------------------------------------------------------
# detect_stale_runbooks
# ---------------------------------------------------------------------------


class TestDetectStaleRunbooks:
    def test_stale_detected(self):
        eng = _engine()
        v = eng.create_version(runbook_id="rb-old", steps=["Old step"])
        # Simulate old creation time (100 days ago)
        import time

        v.created_at = time.time() - (100 * 86400)
        stale = eng.detect_stale_runbooks(max_age_days=90)
        assert len(stale) >= 1
        assert stale[0]["runbook_id"] == "rb-old"
        assert stale[0]["age_days"] >= 100

    def test_fresh_not_stale(self):
        eng = _engine()
        eng.create_version(runbook_id="rb-new", steps=["Fresh step"])
        stale = eng.detect_stale_runbooks(max_age_days=90)
        assert len(stale) == 0


# ---------------------------------------------------------------------------
# generate_version_report
# ---------------------------------------------------------------------------


class TestGenerateVersionReport:
    def test_basic_report(self):
        eng = _engine()
        eng.create_version(
            runbook_id="rb-001",
            category=RunbookCategory.DEPLOYMENT,
        )
        eng.create_version(
            runbook_id="rb-001",
            category=RunbookCategory.DEPLOYMENT,
        )
        eng.create_version(
            runbook_id="rb-002",
            category=RunbookCategory.SECURITY,
        )
        report = eng.generate_version_report()
        assert isinstance(report, VersionReport)
        assert report.total_runbooks == 2
        assert report.total_versions == 3
        assert report.avg_versions_per_runbook == 1.5
        assert report.by_status["draft"] == 3
        assert report.by_category["deployment"] == 2
        assert report.by_category["security"] == 1

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_version_report()
        assert report.total_versions == 0
        assert len(report.recommendations) >= 1


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        v1 = eng.create_version(runbook_id="rb-001", steps=["A"])
        v2 = eng.create_version(runbook_id="rb-001", steps=["B"])
        eng.diff_versions(v1.id, v2.id)
        eng.clear_data()
        assert len(eng._items) == 0
        assert len(eng._diffs) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_versions"] == 0
        assert stats["total_diffs"] == 0
        assert stats["unique_runbooks"] == 0
        assert stats["statuses"] == []
        assert stats["categories"] == []

    def test_populated(self):
        eng = _engine()
        eng.create_version(
            runbook_id="rb-001",
            category=RunbookCategory.DEPLOYMENT,
        )
        eng.create_version(
            runbook_id="rb-002",
            category=RunbookCategory.SECURITY,
        )
        stats = eng.get_stats()
        assert stats["total_versions"] == 2
        assert stats["unique_runbooks"] == 2
        assert "draft" in stats["statuses"]
        assert "deployment" in stats["categories"]
        assert "security" in stats["categories"]
