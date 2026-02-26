"""Tests for shieldops.security.attack_surface — AttackSurfaceMonitor."""

from __future__ import annotations

from shieldops.security.attack_surface import (
    AttackSurfaceMonitor,
    AttackSurfaceReport,
    ExposureDetail,
    ExposureLevel,
    SurfaceRecord,
    SurfaceRisk,
    SurfaceType,
)


def _engine(**kw) -> AttackSurfaceMonitor:
    return AttackSurfaceMonitor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # SurfaceType (5)
    def test_type_public_api(self):
        assert SurfaceType.PUBLIC_API == "public_api"

    def test_type_exposed_port(self):
        assert SurfaceType.EXPOSED_PORT == "exposed_port"

    def test_type_cloud_storage(self):
        assert SurfaceType.CLOUD_STORAGE == "cloud_storage"

    def test_type_database_endpoint(self):
        assert SurfaceType.DATABASE_ENDPOINT == "database_endpoint"

    def test_type_admin_interface(self):
        assert SurfaceType.ADMIN_INTERFACE == "admin_interface"

    # ExposureLevel (5)
    def test_exposure_internet(self):
        assert ExposureLevel.INTERNET_FACING == "internet_facing"

    def test_exposure_vpn(self):
        assert ExposureLevel.VPN_ONLY == "vpn_only"

    def test_exposure_internal(self):
        assert ExposureLevel.INTERNAL == "internal"

    def test_exposure_restricted(self):
        assert ExposureLevel.RESTRICTED == "restricted"

    def test_exposure_air_gapped(self):
        assert ExposureLevel.AIR_GAPPED == "air_gapped"

    # SurfaceRisk (5)
    def test_risk_critical(self):
        assert SurfaceRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert SurfaceRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert SurfaceRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert SurfaceRisk.LOW == "low"

    def test_risk_acceptable(self):
        assert SurfaceRisk.ACCEPTABLE == "acceptable"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_surface_record_defaults(self):
        r = SurfaceRecord()
        assert r.id
        assert r.service_name == ""
        assert r.surface_type == SurfaceType.PUBLIC_API
        assert r.exposure == ExposureLevel.INTERNAL
        assert r.risk == SurfaceRisk.LOW
        assert r.risk_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_exposure_detail_defaults(self):
        e = ExposureDetail()
        assert e.id
        assert e.exposure_name == ""
        assert e.surface_type == SurfaceType.PUBLIC_API
        assert e.exposure == ExposureLevel.INTERNAL
        assert e.severity_score == 0.0
        assert e.description == ""
        assert e.created_at > 0

    def test_report_defaults(self):
        r = AttackSurfaceReport()
        assert r.total_surfaces == 0
        assert r.total_exposures == 0
        assert r.avg_risk_score == 0.0
        assert r.by_type == {}
        assert r.by_exposure == {}
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_surface
# -------------------------------------------------------------------


class TestRecordSurface:
    def test_basic(self):
        eng = _engine()
        r = eng.record_surface(
            "svc-a",
            surface_type=SurfaceType.EXPOSED_PORT,
            risk=SurfaceRisk.HIGH,
            risk_score=85.0,
        )
        assert r.service_name == "svc-a"
        assert r.surface_type == SurfaceType.EXPOSED_PORT
        assert r.risk_score == 85.0

    def test_with_exposure(self):
        eng = _engine()
        r = eng.record_surface("svc-b", exposure=ExposureLevel.INTERNET_FACING)
        assert r.exposure == ExposureLevel.INTERNET_FACING

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_surface(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_surface
# -------------------------------------------------------------------


class TestGetSurface:
    def test_found(self):
        eng = _engine()
        r = eng.record_surface("svc-a")
        assert eng.get_surface(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_surface("nonexistent") is None


# -------------------------------------------------------------------
# list_surfaces
# -------------------------------------------------------------------


class TestListSurfaces:
    def test_list_all(self):
        eng = _engine()
        eng.record_surface("svc-a")
        eng.record_surface("svc-b")
        assert len(eng.list_surfaces()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_surface("svc-a")
        eng.record_surface("svc-b")
        results = eng.list_surfaces(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_surface("svc-a", surface_type=SurfaceType.PUBLIC_API)
        eng.record_surface("svc-b", surface_type=SurfaceType.EXPOSED_PORT)
        results = eng.list_surfaces(surface_type=SurfaceType.PUBLIC_API)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_exposure
# -------------------------------------------------------------------


class TestAddExposure:
    def test_basic(self):
        eng = _engine()
        e = eng.add_exposure("open-s3-bucket", severity_score=90.0)
        assert e.exposure_name == "open-s3-bucket"
        assert e.severity_score == 90.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_exposure(f"exp-{i}")
        assert len(eng._exposures) == 2


# -------------------------------------------------------------------
# analyze_surface_risk
# -------------------------------------------------------------------


class TestAnalyzeSurfaceRisk:
    def test_with_data(self):
        eng = _engine(max_critical_exposures=5)
        eng.record_surface("svc-a", risk=SurfaceRisk.CRITICAL, risk_score=90.0)
        eng.record_surface("svc-a", risk=SurfaceRisk.LOW, risk_score=20.0)
        result = eng.analyze_surface_risk("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total"] == 2
        assert result["avg_risk"] == 55.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_surface_risk("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_critical_exposures
# -------------------------------------------------------------------


class TestIdentifyCriticalExposures:
    def test_with_critical(self):
        eng = _engine()
        eng.record_surface("svc-a", risk=SurfaceRisk.CRITICAL)
        eng.record_surface("svc-a", risk=SurfaceRisk.HIGH)
        eng.record_surface("svc-b", risk=SurfaceRisk.LOW)
        results = eng.identify_critical_exposures()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_exposures() == []


# -------------------------------------------------------------------
# rank_by_risk_score
# -------------------------------------------------------------------


class TestRankByRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_surface("svc-a", risk_score=10.0)
        eng.record_surface("svc-b", risk_score=90.0)
        results = eng.rank_by_risk_score()
        assert results[0]["avg_risk_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# -------------------------------------------------------------------
# detect_surface_expansion
# -------------------------------------------------------------------


class TestDetectSurfaceExpansion:
    def test_with_expansion(self):
        eng = _engine()
        for _ in range(4):
            eng.record_surface("svc-expanding")
        eng.record_surface("svc-stable")
        results = eng.detect_surface_expansion()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-expanding"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_surface_expansion() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_surface(
            "svc-a",
            risk=SurfaceRisk.CRITICAL,
            exposure=ExposureLevel.INTERNET_FACING,
            risk_score=95.0,
        )
        eng.record_surface("svc-b", risk=SurfaceRisk.LOW, risk_score=10.0)
        eng.add_exposure("exp-1")
        report = eng.generate_report()
        assert isinstance(report, AttackSurfaceReport)
        assert report.total_surfaces == 2
        assert report.total_exposures == 1
        assert report.critical_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "acceptable risk levels" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_surface("svc-a")
        eng.add_exposure("exp-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._exposures) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_surfaces"] == 0
        assert stats["total_exposures"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_surface("svc-a", surface_type=SurfaceType.PUBLIC_API)
        eng.record_surface("svc-b", surface_type=SurfaceType.EXPOSED_PORT)
        eng.add_exposure("exp-1")
        stats = eng.get_stats()
        assert stats["total_surfaces"] == 2
        assert stats["total_exposures"] == 1
        assert stats["unique_services"] == 2
