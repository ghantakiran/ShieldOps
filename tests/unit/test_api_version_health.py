"""Tests for shieldops.topology.api_version_health — APIVersionHealthMonitor."""

from __future__ import annotations

from shieldops.topology.api_version_health import (
    APIVersionHealthMonitor,
    APIVersionHealthReport,
    APIVersionRecord,
    MigrationProgress,
    SunsetRisk,
    VersionMigration,
    VersionStatus,
)


def _engine(**kw) -> APIVersionHealthMonitor:
    return APIVersionHealthMonitor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # VersionStatus (5)
    def test_status_current(self):
        assert VersionStatus.CURRENT == "current"

    def test_status_supported(self):
        assert VersionStatus.SUPPORTED == "supported"

    def test_status_deprecated(self):
        assert VersionStatus.DEPRECATED == "deprecated"

    def test_status_sunset(self):
        assert VersionStatus.SUNSET == "sunset"

    def test_status_retired(self):
        assert VersionStatus.RETIRED == "retired"

    # MigrationProgress (5)
    def test_progress_not_started(self):
        assert MigrationProgress.NOT_STARTED == "not_started"

    def test_progress_in_progress(self):
        assert MigrationProgress.IN_PROGRESS == "in_progress"

    def test_progress_mostly_complete(self):
        assert MigrationProgress.MOSTLY_COMPLETE == "mostly_complete"

    def test_progress_complete(self):
        assert MigrationProgress.COMPLETE == "complete"

    def test_progress_blocked(self):
        assert MigrationProgress.BLOCKED == "blocked"

    # SunsetRisk (5)
    def test_sunset_risk_on_track(self):
        assert SunsetRisk.ON_TRACK == "on_track"

    def test_sunset_risk_at_risk(self):
        assert SunsetRisk.AT_RISK == "at_risk"

    def test_sunset_risk_overdue(self):
        assert SunsetRisk.OVERDUE == "overdue"

    def test_sunset_risk_critical(self):
        assert SunsetRisk.CRITICAL == "critical"

    def test_sunset_risk_no_deadline(self):
        assert SunsetRisk.NO_DEADLINE == "no_deadline"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_api_version_record_defaults(self):
        r = APIVersionRecord()
        assert r.id
        assert r.api_name == ""
        assert r.version == ""
        assert r.status == VersionStatus.CURRENT
        assert r.consumer_count == 0
        assert r.sunset_days_remaining == -1
        assert r.traffic_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_version_migration_defaults(self):
        r = VersionMigration()
        assert r.id
        assert r.api_name == ""
        assert r.from_version == ""
        assert r.to_version == ""
        assert r.progress == MigrationProgress.NOT_STARTED
        assert r.consumer_migrated_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_api_version_health_report_defaults(self):
        r = APIVersionHealthReport()
        assert r.total_versions == 0
        assert r.total_migrations == 0
        assert r.by_status == {}
        assert r.deprecated_count == 0
        assert r.sunset_risk_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_version
# -------------------------------------------------------------------


class TestRecordVersion:
    def test_basic(self):
        eng = _engine()
        r = eng.record_version("payments-api", "v2", consumer_count=15)
        assert r.api_name == "payments-api"
        assert r.version == "v2"
        assert r.consumer_count == 15
        assert r.status == VersionStatus.CURRENT

    def test_with_sunset(self):
        eng = _engine()
        r = eng.record_version(
            "users-api",
            "v1",
            status=VersionStatus.DEPRECATED,
            sunset_days_remaining=20,
        )
        assert r.status == VersionStatus.DEPRECATED
        assert r.sunset_days_remaining == 20

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_version(f"api-{i}", f"v{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_version
# -------------------------------------------------------------------


class TestGetVersion:
    def test_found(self):
        eng = _engine()
        r = eng.record_version("api", "v1")
        assert eng.get_version(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_version("nonexistent") is None


# -------------------------------------------------------------------
# list_versions
# -------------------------------------------------------------------


class TestListVersions:
    def test_list_all(self):
        eng = _engine()
        eng.record_version("api-a", "v1")
        eng.record_version("api-b", "v2")
        assert len(eng.list_versions()) == 2

    def test_filter_by_api_name(self):
        eng = _engine()
        eng.record_version("api-a", "v1")
        eng.record_version("api-b", "v2")
        results = eng.list_versions(api_name="api-a")
        assert len(results) == 1
        assert results[0].api_name == "api-a"

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_version("api-a", "v1", status=VersionStatus.CURRENT)
        eng.record_version("api-b", "v2", status=VersionStatus.DEPRECATED)
        results = eng.list_versions(status=VersionStatus.DEPRECATED)
        assert len(results) == 1
        assert results[0].api_name == "api-b"


# -------------------------------------------------------------------
# record_migration
# -------------------------------------------------------------------


class TestRecordMigration:
    def test_basic(self):
        eng = _engine()
        m = eng.record_migration("payments-api", "v1", "v2", consumer_migrated_pct=45.0)
        assert m.api_name == "payments-api"
        assert m.from_version == "v1"
        assert m.to_version == "v2"
        assert m.consumer_migrated_pct == 45.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_migration(f"api-{i}", "v1", "v2")
        assert len(eng._migrations) == 2


# -------------------------------------------------------------------
# identify_sunset_risks
# -------------------------------------------------------------------


class TestIdentifySunsetRisks:
    def test_with_risks(self):
        eng = _engine(sunset_warning_days=30)
        eng.record_version("api-a", "v1", status=VersionStatus.DEPRECATED, sunset_days_remaining=10)
        eng.record_version("api-b", "v2", status=VersionStatus.DEPRECATED, sunset_days_remaining=0)
        eng.record_version("api-c", "v3", status=VersionStatus.DEPRECATED, sunset_days_remaining=-1)
        eng.record_version("api-d", "v1", status=VersionStatus.CURRENT, sunset_days_remaining=5)
        results = eng.identify_sunset_risks()
        # api-c has NO_DEADLINE (sunset_days=-1), api-b OVERDUE (0), api-a AT_RISK (10<30)
        # api-d is CURRENT so not included
        assert len(results) == 3
        # Sorted by sunset_days asc: -1, 0, 10
        assert results[0]["risk"] == "no_deadline"
        assert results[1]["risk"] == "overdue"
        assert results[2]["risk"] == "at_risk"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_sunset_risks() == []

    def test_on_track_excluded(self):
        eng = _engine(sunset_warning_days=30)
        eng.record_version("api-a", "v1", status=VersionStatus.DEPRECATED, sunset_days_remaining=60)
        results = eng.identify_sunset_risks()
        assert len(results) == 0


# -------------------------------------------------------------------
# track_migration_progress
# -------------------------------------------------------------------


class TestTrackMigrationProgress:
    def test_with_migrations(self):
        eng = _engine()
        eng.record_migration("api-a", "v1", "v2", consumer_migrated_pct=80.0)
        eng.record_migration("api-b", "v2", "v3", consumer_migrated_pct=20.0)
        results = eng.track_migration_progress()
        assert len(results) == 2
        # Sorted by consumer_migrated_pct asc
        assert results[0]["api_name"] == "api-b"

    def test_empty(self):
        eng = _engine()
        assert eng.track_migration_progress() == []


# -------------------------------------------------------------------
# identify_zombie_versions
# -------------------------------------------------------------------


class TestIdentifyZombieVersions:
    def test_zombie_with_traffic(self):
        eng = _engine()
        eng.record_version("api-a", "v1", status=VersionStatus.RETIRED, traffic_pct=5.0)
        eng.record_version("api-b", "v2", status=VersionStatus.SUNSET, consumer_count=3)
        eng.record_version("api-c", "v3", status=VersionStatus.CURRENT, traffic_pct=90.0)
        results = eng.identify_zombie_versions()
        assert len(results) == 2
        # Sorted by traffic_pct desc
        assert results[0]["api_name"] == "api-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_zombie_versions() == []


# -------------------------------------------------------------------
# rank_apis_by_version_health
# -------------------------------------------------------------------


class TestRankApisByVersionHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_version("api-a", "v1", status=VersionStatus.CURRENT)
        eng.record_version("api-a", "v2", status=VersionStatus.DEPRECATED)
        eng.record_version("api-b", "v1", status=VersionStatus.CURRENT)
        results = eng.rank_apis_by_version_health()
        assert len(results) == 2
        # api-b: 100% health, api-a: 50% health
        assert results[0]["api_name"] == "api-b"
        assert results[0]["health_score"] == 100.0
        assert results[1]["health_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_apis_by_version_health() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(sunset_warning_days=30)
        eng.record_version("api-a", "v1", status=VersionStatus.DEPRECATED, sunset_days_remaining=10)
        eng.record_version("api-b", "v2", status=VersionStatus.CURRENT)
        eng.record_migration("api-a", "v1", "v2")
        report = eng.generate_report()
        assert report.total_versions == 2
        assert report.total_migrations == 1
        assert report.deprecated_count == 1
        assert report.by_status != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_versions == 0
        assert "good" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_version("api", "v1")
        eng.record_migration("api", "v1", "v2")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._migrations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_versions"] == 0
        assert stats["total_migrations"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_version("api-a", "v1")
        eng.record_version("api-b", "v2")
        eng.record_migration("api-a", "v1", "v2")
        stats = eng.get_stats()
        assert stats["total_versions"] == 2
        assert stats["total_migrations"] == 1
        assert stats["unique_apis"] == 2
        assert stats["sunset_warning_days"] == 30
