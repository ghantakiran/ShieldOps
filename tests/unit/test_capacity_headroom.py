"""Tests for shieldops.analytics.capacity_headroom — CapacityHeadroomAnalyzer."""

from __future__ import annotations

from shieldops.analytics.capacity_headroom import (
    CapacityHeadroomAnalyzer,
    CapacityHeadroomReport,
    GrowthRate,
    HeadroomLevel,
    HeadroomProjection,
    HeadroomRecord,
    ResourceType,
)


def _engine(**kw) -> CapacityHeadroomAnalyzer:
    return CapacityHeadroomAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_resource_type_cpu(self):
        assert ResourceType.CPU == "cpu"

    def test_resource_type_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_resource_type_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_resource_type_network(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_type_connections(self):
        assert ResourceType.CONNECTIONS == "connections"

    def test_headroom_ample(self):
        assert HeadroomLevel.AMPLE == "ample"

    def test_headroom_adequate(self):
        assert HeadroomLevel.ADEQUATE == "adequate"

    def test_headroom_tight(self):
        assert HeadroomLevel.TIGHT == "tight"

    def test_headroom_critical(self):
        assert HeadroomLevel.CRITICAL == "critical"

    def test_headroom_exhausted(self):
        assert HeadroomLevel.EXHAUSTED == "exhausted"

    def test_growth_rapid(self):
        assert GrowthRate.RAPID == "rapid"

    def test_growth_moderate(self):
        assert GrowthRate.MODERATE == "moderate"

    def test_growth_slow(self):
        assert GrowthRate.SLOW == "slow"

    def test_growth_stable(self):
        assert GrowthRate.STABLE == "stable"

    def test_growth_declining(self):
        assert GrowthRate.DECLINING == "declining"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_headroom_record_defaults(self):
        r = HeadroomRecord()
        assert r.id
        assert r.resource_id == ""
        assert r.resource_type == ResourceType.CPU
        assert r.headroom_level == HeadroomLevel.AMPLE
        assert r.growth_rate == GrowthRate.STABLE
        assert r.headroom_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_headroom_projection_defaults(self):
        p = HeadroomProjection()
        assert p.id
        assert p.resource_id == ""
        assert p.resource_type == ResourceType.CPU
        assert p.projected_days == 0.0
        assert p.threshold == 0.0
        assert p.breached is False
        assert p.description == ""
        assert p.created_at > 0

    def test_capacity_headroom_report_defaults(self):
        r = CapacityHeadroomReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_projections == 0
        assert r.critical_resources == 0
        assert r.avg_headroom_pct == 0.0
        assert r.by_resource_type == {}
        assert r.by_headroom == {}
        assert r.by_growth == {}
        assert r.top_at_risk == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_headroom
# ---------------------------------------------------------------------------


class TestRecordHeadroom:
    def test_basic(self):
        eng = _engine()
        r = eng.record_headroom(
            resource_id="RES-001",
            resource_type=ResourceType.CPU,
            headroom_level=HeadroomLevel.ADEQUATE,
            growth_rate=GrowthRate.MODERATE,
            headroom_pct=45.0,
            service="api-gateway",
            team="sre",
        )
        assert r.resource_id == "RES-001"
        assert r.resource_type == ResourceType.CPU
        assert r.headroom_level == HeadroomLevel.ADEQUATE
        assert r.growth_rate == GrowthRate.MODERATE
        assert r.headroom_pct == 45.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_headroom(resource_id=f"RES-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_headroom
# ---------------------------------------------------------------------------


class TestGetHeadroom:
    def test_found(self):
        eng = _engine()
        r = eng.record_headroom(
            resource_id="RES-001",
            resource_type=ResourceType.MEMORY,
        )
        result = eng.get_headroom(r.id)
        assert result is not None
        assert result.resource_type == ResourceType.MEMORY

    def test_not_found(self):
        eng = _engine()
        assert eng.get_headroom("nonexistent") is None


# ---------------------------------------------------------------------------
# list_headroom
# ---------------------------------------------------------------------------


class TestListHeadroom:
    def test_list_all(self):
        eng = _engine()
        eng.record_headroom(resource_id="RES-001")
        eng.record_headroom(resource_id="RES-002")
        assert len(eng.list_headroom()) == 2

    def test_filter_by_resource_type(self):
        eng = _engine()
        eng.record_headroom(
            resource_id="RES-001",
            resource_type=ResourceType.CPU,
        )
        eng.record_headroom(
            resource_id="RES-002",
            resource_type=ResourceType.MEMORY,
        )
        results = eng.list_headroom(resource_type=ResourceType.CPU)
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_headroom(
            resource_id="RES-001",
            headroom_level=HeadroomLevel.AMPLE,
        )
        eng.record_headroom(
            resource_id="RES-002",
            headroom_level=HeadroomLevel.CRITICAL,
        )
        results = eng.list_headroom(level=HeadroomLevel.AMPLE)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_headroom(resource_id="RES-001", service="api-gateway")
        eng.record_headroom(resource_id="RES-002", service="auth-svc")
        results = eng.list_headroom(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_headroom(resource_id="RES-001", team="sre")
        eng.record_headroom(resource_id="RES-002", team="platform")
        results = eng.list_headroom(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_headroom(resource_id=f"RES-{i}")
        assert len(eng.list_headroom(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_projection
# ---------------------------------------------------------------------------


class TestAddProjection:
    def test_basic(self):
        eng = _engine()
        p = eng.add_projection(
            resource_id="RES-001",
            resource_type=ResourceType.STORAGE,
            projected_days=30.0,
            threshold=7.0,
            breached=True,
            description="Storage filling fast",
        )
        assert p.resource_id == "RES-001"
        assert p.resource_type == ResourceType.STORAGE
        assert p.projected_days == 30.0
        assert p.threshold == 7.0
        assert p.breached is True
        assert p.description == "Storage filling fast"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_projection(resource_id=f"RES-{i}")
        assert len(eng._projections) == 2


# ---------------------------------------------------------------------------
# analyze_headroom_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeHeadroomDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_headroom(
            resource_id="RES-001",
            resource_type=ResourceType.CPU,
            headroom_pct=40.0,
        )
        eng.record_headroom(
            resource_id="RES-002",
            resource_type=ResourceType.CPU,
            headroom_pct=60.0,
        )
        result = eng.analyze_headroom_distribution()
        assert "cpu" in result
        assert result["cpu"]["count"] == 2
        assert result["cpu"]["avg_headroom_pct"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_headroom_distribution() == {}


# ---------------------------------------------------------------------------
# identify_critical_resources
# ---------------------------------------------------------------------------


class TestIdentifyCriticalResources:
    def test_detects(self):
        eng = _engine()
        eng.record_headroom(
            resource_id="RES-001",
            headroom_level=HeadroomLevel.CRITICAL,
        )
        eng.record_headroom(
            resource_id="RES-002",
            headroom_level=HeadroomLevel.AMPLE,
        )
        results = eng.identify_critical_resources()
        assert len(results) == 1
        assert results[0]["resource_id"] == "RES-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_resources() == []


# ---------------------------------------------------------------------------
# rank_by_headroom
# ---------------------------------------------------------------------------


class TestRankByHeadroom:
    def test_ranked(self):
        eng = _engine()
        eng.record_headroom(
            resource_id="RES-001",
            service="api-gateway",
            headroom_pct=80.0,
        )
        eng.record_headroom(
            resource_id="RES-002",
            service="auth-svc",
            headroom_pct=20.0,
        )
        eng.record_headroom(
            resource_id="RES-001",
            service="api-gateway",
            headroom_pct=60.0,
        )
        results = eng.rank_by_headroom()
        assert len(results) == 2
        # ascending: RES-002 (20.0) first, RES-001 (70.0) second
        assert results[0]["resource_id"] == "RES-002"
        assert results[0]["avg_headroom_pct"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_headroom() == []


# ---------------------------------------------------------------------------
# detect_headroom_trends
# ---------------------------------------------------------------------------


class TestDetectHeadroomTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_projection(resource_id="RES-1", projected_days=val)
        result = eng.detect_headroom_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_projection(resource_id="RES-1", projected_days=val)
        result = eng.detect_headroom_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_degrading(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_projection(resource_id="RES-1", projected_days=val)
        result = eng.detect_headroom_trends()
        assert result["trend"] == "degrading"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_headroom_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_headroom(
            resource_id="RES-001",
            resource_type=ResourceType.CPU,
            headroom_level=HeadroomLevel.CRITICAL,
            growth_rate=GrowthRate.RAPID,
            headroom_pct=5.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, CapacityHeadroomReport)
        assert report.total_records == 1
        assert report.critical_resources == 1
        assert len(report.top_at_risk) >= 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_headroom(resource_id="RES-001")
        eng.add_projection(resource_id="RES-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._projections) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_projections"] == 0
        assert stats["resource_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_headroom(
            resource_id="RES-001",
            resource_type=ResourceType.CPU,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "cpu" in stats["resource_type_distribution"]
