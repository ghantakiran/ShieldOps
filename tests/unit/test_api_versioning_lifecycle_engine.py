"""Tests for ApiVersioningLifecycleEngine."""

from __future__ import annotations

from shieldops.topology.api_versioning_lifecycle_engine import (
    AdoptionPhase,
    ApiVersioningLifecycleEngine,
    MigrationReadiness,
    VersionStatus,
)


def _engine(**kw) -> ApiVersioningLifecycleEngine:
    return ApiVersioningLifecycleEngine(**kw)


class TestEnums:
    def test_version_status_values(self):
        for v in VersionStatus:
            assert isinstance(v.value, str)

    def test_adoption_phase_values(self):
        for v in AdoptionPhase:
            assert isinstance(v.value, str)

    def test_migration_readiness_values(self):
        for v in MigrationReadiness:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(api_name="users-api")
        assert r.api_name == "users-api"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(api_name=f"api-{i}")
        assert len(eng._records) == 5

    def test_all_fields(self):
        eng = _engine()
        r = eng.record_item(
            api_name="users-api",
            version="v2",
            version_status=VersionStatus.DEPRECATED,
            consumer_count=10,
        )
        assert r.consumer_count == 10


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            api_name="users-api",
            version="v1",
            request_share_pct=80.0,
        )
        a = eng.process(r.id)
        assert a.adoption_pct == 80.0

    def test_stale(self):
        eng = _engine()
        r = eng.record_item(
            version_status=VersionStatus.DEPRECATED,
        )
        a = eng.process(r.id)
        assert a.is_stale is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(api_name="users-api")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_stale_versions(self):
        eng = _engine()
        eng.record_item(
            api_name="users-api",
            version="v1",
            version_status=VersionStatus.DEPRECATED,
        )
        rpt = eng.generate_report()
        assert len(rpt.stale_versions) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(api_name="users-api")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(api_name="users-api")
        eng.clear_data()
        assert len(eng._records) == 0


class TestTrackVersionAdoption:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            api_name="users-api",
            version="v2",
            request_share_pct=75.0,
        )
        result = eng.track_version_adoption()
        assert len(result) == 1
        assert result[0]["avg_share_pct"] == 75.0

    def test_empty(self):
        assert _engine().track_version_adoption() == []


class TestDetectStaleVersionUsage:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            api_name="users-api",
            version="v1",
            version_status=VersionStatus.DEPRECATED,
            consumer_count=5,
        )
        result = eng.detect_stale_version_usage()
        assert len(result) == 1

    def test_no_consumers(self):
        eng = _engine()
        eng.record_item(
            version_status=VersionStatus.DEPRECATED,
            consumer_count=0,
        )
        result = eng.detect_stale_version_usage()
        assert len(result) == 0

    def test_empty(self):
        assert _engine().detect_stale_version_usage() == []


class TestForecastDeprecationReadiness:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            api_name="users-api",
            version="v1",
            migration_readiness=(MigrationReadiness.READY),
        )
        result = eng.forecast_deprecation_readiness()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().forecast_deprecation_readiness() == []
