"""Tests for shieldops.analytics.api_deprecation_tracker — APIDeprecationTracker.

Covers APILifecycleStage, MigrationStatus, and DeprecationUrgency enums,
APIVersionRecord / ConsumerMigration / DeprecationReport models, and all
APIDeprecationTracker operations including version registration, consumer
migration tracking, overdue sunset detection, urgency assessment, and report
generation.
"""

from __future__ import annotations

import time

from shieldops.analytics.api_deprecation_tracker import (
    APIDeprecationTracker,
    APILifecycleStage,
    APIVersionRecord,
    ConsumerMigration,
    DeprecationReport,
    DeprecationUrgency,
    MigrationStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kw) -> APIDeprecationTracker:
    return APIDeprecationTracker(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of APILifecycleStage, MigrationStatus, and DeprecationUrgency."""

    # -- APILifecycleStage (5 members) ----------------------------------------

    def test_stage_active(self):
        assert APILifecycleStage.ACTIVE == "active"

    def test_stage_deprecated(self):
        assert APILifecycleStage.DEPRECATED == "deprecated"

    def test_stage_sunset_planned(self):
        assert APILifecycleStage.SUNSET_PLANNED == "sunset_planned"

    def test_stage_sunset_in_progress(self):
        assert APILifecycleStage.SUNSET_IN_PROGRESS == "sunset_in_progress"

    def test_stage_retired(self):
        assert APILifecycleStage.RETIRED == "retired"

    # -- MigrationStatus (5 members) ------------------------------------------

    def test_migration_not_started(self):
        assert MigrationStatus.NOT_STARTED == "not_started"

    def test_migration_in_progress(self):
        assert MigrationStatus.IN_PROGRESS == "in_progress"

    def test_migration_completed(self):
        assert MigrationStatus.COMPLETED == "completed"

    def test_migration_blocked(self):
        assert MigrationStatus.BLOCKED == "blocked"

    def test_migration_opted_out(self):
        assert MigrationStatus.OPTED_OUT == "opted_out"

    # -- DeprecationUrgency (5 members) ---------------------------------------

    def test_urgency_low(self):
        assert DeprecationUrgency.LOW == "low"

    def test_urgency_medium(self):
        assert DeprecationUrgency.MEDIUM == "medium"

    def test_urgency_high(self):
        assert DeprecationUrgency.HIGH == "high"

    def test_urgency_critical(self):
        assert DeprecationUrgency.CRITICAL == "critical"

    def test_urgency_overdue(self):
        assert DeprecationUrgency.OVERDUE == "overdue"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_api_version_record_defaults(self):
        v = APIVersionRecord()
        assert v.id
        assert v.api_name == ""
        assert v.version == ""
        assert v.stage == APILifecycleStage.ACTIVE
        assert v.deprecated_at == 0.0
        assert v.sunset_date == 0.0
        assert v.replacement_version == ""
        assert v.consumer_count == 0
        assert v.created_at > 0

    def test_consumer_migration_defaults(self):
        m = ConsumerMigration()
        assert m.id
        assert m.api_version_id == ""
        assert m.consumer_name == ""
        assert m.status == MigrationStatus.NOT_STARTED
        assert m.started_at == 0.0
        assert m.completed_at == 0.0
        assert m.notes == ""
        assert m.created_at > 0

    def test_deprecation_report_defaults(self):
        r = DeprecationReport()
        assert r.total_apis == 0
        assert r.deprecated_count == 0
        assert r.sunset_count == 0
        assert r.retired_count == 0
        assert r.overdue_count == 0
        assert r.avg_migration_progress == 0.0
        assert r.stage_distribution == {}
        assert r.urgency_distribution == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# ===========================================================================
# RegisterAPIVersion
# ===========================================================================


class TestRegisterAPIVersion:
    """Test APIDeprecationTracker.register_api_version."""

    def test_basic_registration(self):
        eng = _engine()
        v = eng.register_api_version(
            api_name="user-api",
            version="v1",
            stage=APILifecycleStage.ACTIVE,
            consumer_count=5,
        )
        assert v.id
        assert v.api_name == "user-api"
        assert v.version == "v1"
        assert v.stage == APILifecycleStage.ACTIVE
        assert v.consumer_count == 5

    def test_eviction_on_overflow(self):
        eng = _engine(max_records=2)
        eng.register_api_version(api_name="api-a", version="v1")
        eng.register_api_version(api_name="api-b", version="v1")
        v3 = eng.register_api_version(api_name="api-c", version="v1")
        versions = eng.list_api_versions(limit=10)
        assert len(versions) == 2
        assert versions[-1].id == v3.id


# ===========================================================================
# GetAPIVersion
# ===========================================================================


class TestGetAPIVersion:
    """Test APIDeprecationTracker.get_api_version."""

    def test_found(self):
        eng = _engine()
        v = eng.register_api_version(api_name="payments", version="v2")
        assert eng.get_api_version(v.id) is v

    def test_not_found(self):
        eng = _engine()
        assert eng.get_api_version("nonexistent-id") is None


# ===========================================================================
# ListAPIVersions
# ===========================================================================


class TestListAPIVersions:
    """Test APIDeprecationTracker.list_api_versions with various filters."""

    def test_all_versions(self):
        eng = _engine()
        eng.register_api_version(api_name="api-a", version="v1")
        eng.register_api_version(api_name="api-b", version="v1")
        assert len(eng.list_api_versions()) == 2

    def test_filter_by_stage(self):
        eng = _engine()
        eng.register_api_version(
            api_name="api-a",
            version="v1",
            stage=APILifecycleStage.ACTIVE,
        )
        eng.register_api_version(
            api_name="api-b",
            version="v1",
            stage=APILifecycleStage.DEPRECATED,
        )
        results = eng.list_api_versions(stage=APILifecycleStage.DEPRECATED)
        assert len(results) == 1
        assert results[0].stage == APILifecycleStage.DEPRECATED

    def test_filter_by_api_name(self):
        eng = _engine()
        eng.register_api_version(api_name="user-api", version="v1")
        eng.register_api_version(api_name="user-api", version="v2")
        eng.register_api_version(api_name="billing-api", version="v1")
        results = eng.list_api_versions(api_name="user-api")
        assert len(results) == 2
        assert all(v.api_name == "user-api" for v in results)


# ===========================================================================
# RegisterConsumerMigration
# ===========================================================================


class TestRegisterConsumerMigration:
    """Test APIDeprecationTracker.register_consumer_migration."""

    def test_basic_migration(self):
        eng = _engine()
        v = eng.register_api_version(
            api_name="orders",
            version="v1",
            stage=APILifecycleStage.DEPRECATED,
        )
        m = eng.register_consumer_migration(
            api_version_id=v.id,
            consumer_name="checkout-svc",
        )
        assert m.id
        assert m.api_version_id == v.id
        assert m.consumer_name == "checkout-svc"
        assert m.status == MigrationStatus.NOT_STARTED


# ===========================================================================
# UpdateMigrationStatus
# ===========================================================================


class TestUpdateMigrationStatus:
    """Test APIDeprecationTracker.update_migration_status."""

    def test_update_success(self):
        eng = _engine()
        v = eng.register_api_version(api_name="orders", version="v1")
        m = eng.register_consumer_migration(
            api_version_id=v.id,
            consumer_name="checkout-svc",
        )
        result = eng.update_migration_status(
            migration_id=m.id,
            status=MigrationStatus.IN_PROGRESS,
            notes="Started migration sprint",
        )
        assert result is True
        assert m.status == MigrationStatus.IN_PROGRESS
        assert m.started_at > 0
        assert m.notes == "Started migration sprint"

    def test_update_not_found(self):
        eng = _engine()
        result = eng.update_migration_status(
            migration_id="no-such-id",
            status=MigrationStatus.COMPLETED,
        )
        assert result is False


# ===========================================================================
# DetectOverdueSunsets
# ===========================================================================


class TestDetectOverdueSunsets:
    """Test APIDeprecationTracker.detect_overdue_sunsets."""

    def test_with_overdue_apis(self):
        eng = _engine()
        past_date = time.time() - 86400 * 30  # 30 days ago
        eng.register_api_version(
            api_name="legacy-api",
            version="v1",
            stage=APILifecycleStage.SUNSET_IN_PROGRESS,
            sunset_date=past_date,
        )
        eng.register_api_version(
            api_name="current-api",
            version="v2",
            stage=APILifecycleStage.ACTIVE,
            sunset_date=0.0,
        )
        # Retired API with past sunset should NOT be overdue
        eng.register_api_version(
            api_name="old-api",
            version="v0",
            stage=APILifecycleStage.RETIRED,
            sunset_date=past_date,
        )
        overdue = eng.detect_overdue_sunsets()
        assert len(overdue) == 1
        assert overdue[0].api_name == "legacy-api"


# ===========================================================================
# CalculateMigrationProgress
# ===========================================================================


class TestCalculateMigrationProgress:
    """Test APIDeprecationTracker.calculate_migration_progress."""

    def test_mixed_migration_statuses(self):
        eng = _engine()
        v = eng.register_api_version(
            api_name="orders",
            version="v1",
            stage=APILifecycleStage.DEPRECATED,
        )
        m1 = eng.register_consumer_migration(api_version_id=v.id, consumer_name="svc-a")
        m2 = eng.register_consumer_migration(api_version_id=v.id, consumer_name="svc-b")
        eng.register_consumer_migration(api_version_id=v.id, consumer_name="svc-c")

        eng.update_migration_status(m1.id, MigrationStatus.COMPLETED)
        eng.update_migration_status(m2.id, MigrationStatus.IN_PROGRESS)
        # m3 stays NOT_STARTED

        progress = eng.calculate_migration_progress(v.id)
        assert progress["api_version_id"] == v.id
        assert progress["total_consumers"] == 3
        assert progress["completion_pct"] == round(1 / 3 * 100, 2)
        assert progress["status_breakdown"]["completed"] == 1
        assert progress["status_breakdown"]["in_progress"] == 1
        assert progress["status_breakdown"]["not_started"] == 1


# ===========================================================================
# AssessDeprecationUrgency
# ===========================================================================


class TestAssessDeprecationUrgency:
    """Test APIDeprecationTracker.assess_deprecation_urgency."""

    def test_overdue_urgency(self):
        eng = _engine()
        past_date = time.time() - 86400 * 10  # 10 days ago
        v = eng.register_api_version(
            api_name="old-api",
            version="v1",
            stage=APILifecycleStage.SUNSET_IN_PROGRESS,
            sunset_date=past_date,
        )
        assessment = eng.assess_deprecation_urgency(v.id)
        assert assessment["urgency"] == "overdue"
        assert assessment["days_until_sunset"] < 0

    def test_critical_urgency(self):
        eng = _engine()
        # Sunset in 3 days -> CRITICAL
        near_date = time.time() + 86400 * 3
        v = eng.register_api_version(
            api_name="urgent-api",
            version="v2",
            stage=APILifecycleStage.SUNSET_PLANNED,
            sunset_date=near_date,
        )
        assessment = eng.assess_deprecation_urgency(v.id)
        assert assessment["urgency"] == "critical"
        assert 0 < assessment["days_until_sunset"] < 7

    def test_low_urgency(self):
        eng = _engine()
        # Sunset in 120 days -> LOW
        future_date = time.time() + 86400 * 120
        v = eng.register_api_version(
            api_name="future-api",
            version="v3",
            stage=APILifecycleStage.DEPRECATED,
            sunset_date=future_date,
        )
        assessment = eng.assess_deprecation_urgency(v.id)
        assert assessment["urgency"] == "low"
        assert assessment["days_until_sunset"] > 90


# ===========================================================================
# GenerateDeprecationReport
# ===========================================================================


class TestGenerateDeprecationReport:
    """Test APIDeprecationTracker.generate_deprecation_report."""

    def test_basic_report(self):
        eng = _engine()
        eng.register_api_version(
            api_name="user-api",
            version="v1",
            stage=APILifecycleStage.ACTIVE,
        )
        past_sunset = time.time() - 86400 * 5
        v_dep = eng.register_api_version(
            api_name="user-api",
            version="v0",
            stage=APILifecycleStage.DEPRECATED,
            sunset_date=past_sunset,
        )
        eng.register_api_version(
            api_name="billing-api",
            version="v1",
            stage=APILifecycleStage.RETIRED,
        )
        # Add a consumer migration for the deprecated version
        m = eng.register_consumer_migration(
            api_version_id=v_dep.id,
            consumer_name="frontend",
        )
        eng.update_migration_status(m.id, MigrationStatus.BLOCKED, notes="Needs v2 SDK")

        report = eng.generate_deprecation_report()
        assert isinstance(report, DeprecationReport)
        assert report.total_apis == 3
        assert report.deprecated_count == 1
        assert report.retired_count == 1
        assert report.generated_at > 0
        assert len(report.stage_distribution) >= 1
        # Recommendations should mention overdue and/or blocked migrations
        assert len(report.recommendations) >= 1


# ===========================================================================
# ClearData
# ===========================================================================


class TestClearData:
    """Test APIDeprecationTracker.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        v = eng.register_api_version(api_name="api-x", version="v1")
        eng.register_consumer_migration(api_version_id=v.id, consumer_name="svc-y")
        eng.clear_data()
        assert len(eng.list_api_versions()) == 0
        stats = eng.get_stats()
        assert stats["total_api_versions"] == 0
        assert stats["total_migrations"] == 0


# ===========================================================================
# GetStats
# ===========================================================================


class TestGetStats:
    """Test APIDeprecationTracker.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_api_versions"] == 0
        assert stats["total_migrations"] == 0
        assert stats["unique_api_names"] == 0
        assert stats["stage_distribution"] == {}
        assert stats["migration_status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        v1 = eng.register_api_version(
            api_name="user-api",
            version="v1",
            stage=APILifecycleStage.ACTIVE,
        )
        eng.register_api_version(
            api_name="user-api",
            version="v2",
            stage=APILifecycleStage.DEPRECATED,
        )
        eng.register_consumer_migration(api_version_id=v1.id, consumer_name="svc-a")
        eng.register_consumer_migration(api_version_id=v1.id, consumer_name="svc-b")

        stats = eng.get_stats()
        assert stats["total_api_versions"] == 2
        assert stats["total_migrations"] == 2
        assert stats["unique_api_names"] == 1
        assert stats["stage_distribution"]["active"] == 1
        assert stats["stage_distribution"]["deprecated"] == 1
        assert stats["migration_status_distribution"]["not_started"] == 2
