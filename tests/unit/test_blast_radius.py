"""Tests for shieldops.incidents.blast_radius — IncidentBlastRadiusAnalyzer."""

from __future__ import annotations

from shieldops.incidents.blast_radius import (
    BlastRadiusRecord,
    BlastRadiusReport,
    BlastRadiusScope,
    ContainmentStatus,
    ImpactVector,
    ImpactZone,
    IncidentBlastRadiusAnalyzer,
)


def _engine(**kw) -> IncidentBlastRadiusAnalyzer:
    return IncidentBlastRadiusAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_scope_single_service(self):
        assert BlastRadiusScope.SINGLE_SERVICE == "single_service"

    def test_scope_multi_service(self):
        assert BlastRadiusScope.MULTI_SERVICE == "multi_service"

    def test_scope_team_wide(self):
        assert BlastRadiusScope.TEAM_WIDE == "team_wide"

    def test_scope_region_wide(self):
        assert BlastRadiusScope.REGION_WIDE == "region_wide"

    def test_scope_platform_wide(self):
        assert BlastRadiusScope.PLATFORM_WIDE == "platform_wide"

    def test_vector_availability(self):
        assert ImpactVector.AVAILABILITY == "availability"

    def test_vector_latency(self):
        assert ImpactVector.LATENCY == "latency"

    def test_vector_data_integrity(self):
        assert ImpactVector.DATA_INTEGRITY == "data_integrity"

    def test_vector_security(self):
        assert ImpactVector.SECURITY == "security"

    def test_vector_customer_experience(self):
        assert ImpactVector.CUSTOMER_EXPERIENCE == "customer_experience"

    def test_containment_contained(self):
        assert ContainmentStatus.CONTAINED == "contained"

    def test_containment_spreading(self):
        assert ContainmentStatus.SPREADING == "spreading"

    def test_containment_mitigated(self):
        assert ContainmentStatus.MITIGATED == "mitigated"

    def test_containment_escalating(self):
        assert ContainmentStatus.ESCALATING == "escalating"

    def test_containment_resolved(self):
        assert ContainmentStatus.RESOLVED == "resolved"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_blast_radius_record_defaults(self):
        r = BlastRadiusRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.blast_radius_scope == BlastRadiusScope.SINGLE_SERVICE
        assert r.impact_vector == ImpactVector.AVAILABILITY
        assert r.containment_status == ContainmentStatus.CONTAINED
        assert r.blast_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_impact_zone_defaults(self):
        z = ImpactZone()
        assert z.id
        assert z.zone_name == ""
        assert z.blast_radius_scope == BlastRadiusScope.SINGLE_SERVICE
        assert z.impact_threshold == 0.0
        assert z.avg_blast_score == 0.0
        assert z.description == ""
        assert z.created_at > 0

    def test_blast_radius_report_defaults(self):
        r = BlastRadiusReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_zones == 0
        assert r.high_radius_incidents == 0
        assert r.avg_blast_score == 0.0
        assert r.by_scope == {}
        assert r.by_impact_vector == {}
        assert r.by_containment == {}
        assert r.top_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_blast_radius
# ---------------------------------------------------------------------------


class TestRecordBlastRadius:
    def test_basic(self):
        eng = _engine()
        r = eng.record_blast_radius(
            incident_id="INC-001",
            blast_radius_scope=BlastRadiusScope.MULTI_SERVICE,
            impact_vector=ImpactVector.LATENCY,
            containment_status=ContainmentStatus.CONTAINED,
            blast_score=65.0,
            team="sre",
        )
        assert r.incident_id == "INC-001"
        assert r.blast_radius_scope == BlastRadiusScope.MULTI_SERVICE
        assert r.impact_vector == ImpactVector.LATENCY
        assert r.containment_status == ContainmentStatus.CONTAINED
        assert r.blast_score == 65.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_blast_radius(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_blast_radius
# ---------------------------------------------------------------------------


class TestGetBlastRadius:
    def test_found(self):
        eng = _engine()
        r = eng.record_blast_radius(
            incident_id="INC-001",
            blast_radius_scope=BlastRadiusScope.REGION_WIDE,
        )
        result = eng.get_blast_radius(r.id)
        assert result is not None
        assert result.blast_radius_scope == BlastRadiusScope.REGION_WIDE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_blast_radius("nonexistent") is None


# ---------------------------------------------------------------------------
# list_blast_radii
# ---------------------------------------------------------------------------


class TestListBlastRadii:
    def test_list_all(self):
        eng = _engine()
        eng.record_blast_radius(incident_id="INC-001")
        eng.record_blast_radius(incident_id="INC-002")
        assert len(eng.list_blast_radii()) == 2

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_blast_radius(
            incident_id="INC-001",
            blast_radius_scope=BlastRadiusScope.SINGLE_SERVICE,
        )
        eng.record_blast_radius(
            incident_id="INC-002",
            blast_radius_scope=BlastRadiusScope.PLATFORM_WIDE,
        )
        results = eng.list_blast_radii(scope=BlastRadiusScope.SINGLE_SERVICE)
        assert len(results) == 1

    def test_filter_by_vector(self):
        eng = _engine()
        eng.record_blast_radius(
            incident_id="INC-001",
            impact_vector=ImpactVector.AVAILABILITY,
        )
        eng.record_blast_radius(
            incident_id="INC-002",
            impact_vector=ImpactVector.SECURITY,
        )
        results = eng.list_blast_radii(vector=ImpactVector.AVAILABILITY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_blast_radius(incident_id="INC-001", team="sre")
        eng.record_blast_radius(incident_id="INC-002", team="platform")
        results = eng.list_blast_radii(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_blast_radius(incident_id=f"INC-{i}")
        assert len(eng.list_blast_radii(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_impact_zone
# ---------------------------------------------------------------------------


class TestAddImpactZone:
    def test_basic(self):
        eng = _engine()
        z = eng.add_impact_zone(
            zone_name="us-east-1",
            blast_radius_scope=BlastRadiusScope.REGION_WIDE,
            impact_threshold=0.8,
            avg_blast_score=70.0,
            description="US East region zone",
        )
        assert z.zone_name == "us-east-1"
        assert z.blast_radius_scope == BlastRadiusScope.REGION_WIDE
        assert z.impact_threshold == 0.8
        assert z.avg_blast_score == 70.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_impact_zone(zone_name=f"zone-{i}")
        assert len(eng._zones) == 2


# ---------------------------------------------------------------------------
# analyze_blast_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeBlastPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_blast_radius(
            incident_id="INC-001",
            blast_radius_scope=BlastRadiusScope.MULTI_SERVICE,
            blast_score=90.0,
        )
        eng.record_blast_radius(
            incident_id="INC-002",
            blast_radius_scope=BlastRadiusScope.MULTI_SERVICE,
            blast_score=80.0,
        )
        result = eng.analyze_blast_patterns()
        assert "multi_service" in result
        assert result["multi_service"]["count"] == 2
        assert result["multi_service"]["avg_blast_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_blast_patterns() == {}


# ---------------------------------------------------------------------------
# identify_high_radius_incidents
# ---------------------------------------------------------------------------


class TestIdentifyHighRadiusIncidents:
    def test_detects_region_wide(self):
        eng = _engine()
        eng.record_blast_radius(
            incident_id="INC-001",
            blast_radius_scope=BlastRadiusScope.REGION_WIDE,
            blast_score=80.0,
        )
        eng.record_blast_radius(
            incident_id="INC-002",
            blast_radius_scope=BlastRadiusScope.SINGLE_SERVICE,
        )
        results = eng.identify_high_radius_incidents()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_detects_platform_wide(self):
        eng = _engine()
        eng.record_blast_radius(
            incident_id="INC-001",
            blast_radius_scope=BlastRadiusScope.PLATFORM_WIDE,
        )
        results = eng.identify_high_radius_incidents()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_radius_incidents() == []


# ---------------------------------------------------------------------------
# rank_by_blast_score
# ---------------------------------------------------------------------------


class TestRankByBlastScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_blast_radius(incident_id="INC-001", team="sre", blast_score=90.0)
        eng.record_blast_radius(incident_id="INC-002", team="sre", blast_score=80.0)
        eng.record_blast_radius(incident_id="INC-003", team="platform", blast_score=70.0)
        results = eng.rank_by_blast_score()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_blast_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_blast_score() == []


# ---------------------------------------------------------------------------
# detect_containment_failures
# ---------------------------------------------------------------------------


class TestDetectContainmentFailures:
    def test_stable(self):
        eng = _engine()
        for s in [80.0, 80.0, 80.0, 80.0]:
            eng.add_impact_zone(zone_name="z", avg_blast_score=s)
        result = eng.detect_containment_failures()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [50.0, 50.0, 90.0, 90.0]:
            eng.add_impact_zone(zone_name="z", avg_blast_score=s)
        result = eng.detect_containment_failures()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_containment_failures()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_blast_radius(
            incident_id="INC-001",
            blast_radius_scope=BlastRadiusScope.PLATFORM_WIDE,
            impact_vector=ImpactVector.AVAILABILITY,
            blast_score=85.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, BlastRadiusReport)
        assert report.total_records == 1
        assert report.high_radius_incidents == 1
        assert report.avg_blast_score == 85.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable limits" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_blast_radius(incident_id="INC-001")
        eng.add_impact_zone(zone_name="z1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._zones) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_zones"] == 0
        assert stats["scope_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_blast_radius(
            incident_id="INC-001",
            blast_radius_scope=BlastRadiusScope.MULTI_SERVICE,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_incidents"] == 1
        assert "multi_service" in stats["scope_distribution"]
