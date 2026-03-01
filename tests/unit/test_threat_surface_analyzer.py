"""Tests for shieldops.security.threat_surface_analyzer — ThreatSurfaceAnalyzer."""

from __future__ import annotations

from shieldops.security.threat_surface_analyzer import (
    MitigationStatus,
    SurfaceMetric,
    SurfaceRecord,
    SurfaceVector,
    ThreatLevel,
    ThreatSurfaceAnalyzer,
    ThreatSurfaceReport,
)


def _engine(**kw) -> ThreatSurfaceAnalyzer:
    return ThreatSurfaceAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_vector_network_exposure(self):
        assert SurfaceVector.NETWORK_EXPOSURE == "network_exposure"

    def test_vector_api_endpoint(self):
        assert SurfaceVector.API_ENDPOINT == "api_endpoint"

    def test_vector_data_store(self):
        assert SurfaceVector.DATA_STORE == "data_store"

    def test_vector_credential_store(self):
        assert SurfaceVector.CREDENTIAL_STORE == "credential_store"

    def test_vector_admin_panel(self):
        assert SurfaceVector.ADMIN_PANEL == "admin_panel"

    def test_level_critical(self):
        assert ThreatLevel.CRITICAL == "critical"

    def test_level_high(self):
        assert ThreatLevel.HIGH == "high"

    def test_level_moderate(self):
        assert ThreatLevel.MODERATE == "moderate"

    def test_level_low(self):
        assert ThreatLevel.LOW == "low"

    def test_level_acceptable(self):
        assert ThreatLevel.ACCEPTABLE == "acceptable"

    def test_status_mitigated(self):
        assert MitigationStatus.MITIGATED == "mitigated"

    def test_status_partially_mitigated(self):
        assert MitigationStatus.PARTIALLY_MITIGATED == "partially_mitigated"

    def test_status_unmitigated(self):
        assert MitigationStatus.UNMITIGATED == "unmitigated"

    def test_status_accepted(self):
        assert MitigationStatus.ACCEPTED == "accepted"

    def test_status_in_progress(self):
        assert MitigationStatus.IN_PROGRESS == "in_progress"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_surface_record_defaults(self):
        r = SurfaceRecord()
        assert r.id
        assert r.surface_id == ""
        assert r.surface_vector == SurfaceVector.NETWORK_EXPOSURE
        assert r.threat_level == ThreatLevel.MODERATE
        assert r.mitigation_status == MitigationStatus.UNMITIGATED
        assert r.exposure_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_surface_metric_defaults(self):
        m = SurfaceMetric()
        assert m.id
        assert m.surface_id == ""
        assert m.surface_vector == SurfaceVector.NETWORK_EXPOSURE
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_threat_surface_report_defaults(self):
        r = ThreatSurfaceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.unmitigated_count == 0
        assert r.avg_exposure_score == 0.0
        assert r.by_vector == {}
        assert r.by_level == {}
        assert r.by_status == {}
        assert r.top_exposed == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_surface
# ---------------------------------------------------------------------------


class TestRecordSurface:
    def test_basic(self):
        eng = _engine()
        r = eng.record_surface(
            surface_id="SRF-001",
            surface_vector=SurfaceVector.API_ENDPOINT,
            threat_level=ThreatLevel.HIGH,
            mitigation_status=MitigationStatus.UNMITIGATED,
            exposure_score=75.0,
            service="api-gateway",
            team="sre",
        )
        assert r.surface_id == "SRF-001"
        assert r.surface_vector == SurfaceVector.API_ENDPOINT
        assert r.threat_level == ThreatLevel.HIGH
        assert r.mitigation_status == MitigationStatus.UNMITIGATED
        assert r.exposure_score == 75.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_surface(surface_id=f"SRF-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_surface
# ---------------------------------------------------------------------------


class TestGetSurface:
    def test_found(self):
        eng = _engine()
        r = eng.record_surface(
            surface_id="SRF-001",
            threat_level=ThreatLevel.CRITICAL,
        )
        result = eng.get_surface(r.id)
        assert result is not None
        assert result.threat_level == ThreatLevel.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_surface("nonexistent") is None


# ---------------------------------------------------------------------------
# list_surfaces
# ---------------------------------------------------------------------------


class TestListSurfaces:
    def test_list_all(self):
        eng = _engine()
        eng.record_surface(surface_id="SRF-001")
        eng.record_surface(surface_id="SRF-002")
        assert len(eng.list_surfaces()) == 2

    def test_filter_by_vector(self):
        eng = _engine()
        eng.record_surface(
            surface_id="SRF-001",
            surface_vector=SurfaceVector.API_ENDPOINT,
        )
        eng.record_surface(
            surface_id="SRF-002",
            surface_vector=SurfaceVector.DATA_STORE,
        )
        results = eng.list_surfaces(
            surface_vector=SurfaceVector.API_ENDPOINT,
        )
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_surface(
            surface_id="SRF-001",
            threat_level=ThreatLevel.CRITICAL,
        )
        eng.record_surface(
            surface_id="SRF-002",
            threat_level=ThreatLevel.LOW,
        )
        results = eng.list_surfaces(
            threat_level=ThreatLevel.CRITICAL,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_surface(surface_id="SRF-001", team="sre")
        eng.record_surface(surface_id="SRF-002", team="platform")
        results = eng.list_surfaces(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_surface(surface_id=f"SRF-{i}")
        assert len(eng.list_surfaces(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            surface_id="SRF-001",
            surface_vector=SurfaceVector.API_ENDPOINT,
            metric_score=85.0,
            threshold=70.0,
            breached=True,
            description="endpoint exposure check",
        )
        assert m.surface_id == "SRF-001"
        assert m.surface_vector == SurfaceVector.API_ENDPOINT
        assert m.metric_score == 85.0
        assert m.threshold == 70.0
        assert m.breached is True
        assert m.description == "endpoint exposure check"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(surface_id=f"SRF-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_surface_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeSurfaceDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_surface(
            surface_id="SRF-001",
            surface_vector=SurfaceVector.API_ENDPOINT,
            exposure_score=60.0,
        )
        eng.record_surface(
            surface_id="SRF-002",
            surface_vector=SurfaceVector.API_ENDPOINT,
            exposure_score=40.0,
        )
        result = eng.analyze_surface_distribution()
        assert "api_endpoint" in result
        assert result["api_endpoint"]["count"] == 2
        assert result["api_endpoint"]["avg_exposure_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_surface_distribution() == {}


# ---------------------------------------------------------------------------
# identify_exposed_surfaces
# ---------------------------------------------------------------------------


class TestIdentifyExposedSurfaces:
    def test_detects_exposed(self):
        eng = _engine(max_exposure_score=30.0)
        eng.record_surface(
            surface_id="SRF-001",
            exposure_score=50.0,
        )
        eng.record_surface(
            surface_id="SRF-002",
            exposure_score=20.0,
        )
        results = eng.identify_exposed_surfaces()
        assert len(results) == 1
        assert results[0]["surface_id"] == "SRF-001"

    def test_sorted_desc(self):
        eng = _engine(max_exposure_score=30.0)
        eng.record_surface(surface_id="SRF-001", exposure_score=50.0)
        eng.record_surface(surface_id="SRF-002", exposure_score=80.0)
        results = eng.identify_exposed_surfaces()
        assert len(results) == 2
        assert results[0]["exposure_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_exposed_surfaces() == []


# ---------------------------------------------------------------------------
# rank_by_exposure
# ---------------------------------------------------------------------------


class TestRankByExposure:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_surface(surface_id="SRF-001", service="api", exposure_score=20.0)
        eng.record_surface(surface_id="SRF-002", service="web", exposure_score=80.0)
        results = eng.rank_by_exposure()
        assert len(results) == 2
        assert results[0]["service"] == "web"
        assert results[0]["avg_exposure_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_exposure() == []


# ---------------------------------------------------------------------------
# detect_surface_trends
# ---------------------------------------------------------------------------


class TestDetectSurfaceTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(surface_id="SRF-001", metric_score=50.0)
        result = eng.detect_surface_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_metric(surface_id="SRF-001", metric_score=20.0)
        eng.add_metric(surface_id="SRF-002", metric_score=20.0)
        eng.add_metric(surface_id="SRF-003", metric_score=80.0)
        eng.add_metric(surface_id="SRF-004", metric_score=80.0)
        result = eng.detect_surface_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_surface_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_exposure_score=30.0)
        eng.record_surface(
            surface_id="SRF-001",
            surface_vector=SurfaceVector.API_ENDPOINT,
            threat_level=ThreatLevel.CRITICAL,
            mitigation_status=MitigationStatus.UNMITIGATED,
            exposure_score=75.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ThreatSurfaceReport)
        assert report.total_records == 1
        assert report.unmitigated_count == 1
        assert len(report.top_exposed) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_surface(surface_id="SRF-001")
        eng.add_metric(surface_id="SRF-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["vector_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_surface(
            surface_id="SRF-001",
            surface_vector=SurfaceVector.API_ENDPOINT,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_surfaces"] == 1
        assert "api_endpoint" in stats["vector_distribution"]
