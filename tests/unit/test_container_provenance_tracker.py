"""Tests for shieldops.security.container_provenance_tracker."""

from __future__ import annotations

from shieldops.security.container_provenance_tracker import (
    BuildSystem,
    ContainerProvenanceReport,
    ContainerProvenanceTracker,
    ProvenanceAnalysis,
    ProvenanceLevel,
    ProvenanceRecord,
    RegistryType,
)


def _engine(**kw) -> ContainerProvenanceTracker:
    return ContainerProvenanceTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_provenance_full(self):
        assert ProvenanceLevel.FULL == "full"

    def test_provenance_partial(self):
        assert ProvenanceLevel.PARTIAL == "partial"

    def test_provenance_minimal(self):
        assert ProvenanceLevel.MINIMAL == "minimal"

    def test_provenance_none(self):
        assert ProvenanceLevel.NONE == "none"

    def test_provenance_unknown(self):
        assert ProvenanceLevel.UNKNOWN == "unknown"

    def test_registry_public(self):
        assert RegistryType.PUBLIC == "public"

    def test_registry_private(self):
        assert RegistryType.PRIVATE == "private"

    def test_registry_mirror(self):
        assert RegistryType.MIRROR == "mirror"

    def test_registry_cache(self):
        assert RegistryType.CACHE == "cache"

    def test_registry_internal(self):
        assert RegistryType.INTERNAL == "internal"

    def test_build_docker(self):
        assert BuildSystem.DOCKER == "docker"

    def test_build_buildpack(self):
        assert BuildSystem.BUILDPACK == "buildpack"

    def test_build_kaniko(self):
        assert BuildSystem.KANIKO == "kaniko"

    def test_build_buildah(self):
        assert BuildSystem.BUILDAH == "buildah"

    def test_build_custom(self):
        assert BuildSystem.CUSTOM == "custom"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_provenance_record_defaults(self):
        r = ProvenanceRecord()
        assert r.id
        assert r.image_name == ""
        assert r.provenance_level == ProvenanceLevel.FULL
        assert r.registry_type == RegistryType.PRIVATE
        assert r.build_system == BuildSystem.DOCKER
        assert r.provenance_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_provenance_analysis_defaults(self):
        c = ProvenanceAnalysis()
        assert c.id
        assert c.image_name == ""
        assert c.provenance_level == ProvenanceLevel.FULL
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_container_provenance_report_defaults(self):
        r = ContainerProvenanceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_provenance_score == 0.0
        assert r.by_provenance == {}
        assert r.by_registry == {}
        assert r.by_build_system == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_provenance / get / list
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_provenance(
            image_name="my-svc:v1.0",
            provenance_level=ProvenanceLevel.PARTIAL,
            registry_type=RegistryType.PRIVATE,
            build_system=BuildSystem.KANIKO,
            provenance_score=75.0,
            service="build-svc",
            team="platform",
        )
        assert r.image_name == "my-svc:v1.0"
        assert r.provenance_level == ProvenanceLevel.PARTIAL
        assert r.registry_type == RegistryType.PRIVATE
        assert r.build_system == BuildSystem.KANIKO
        assert r.provenance_score == 75.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_provenance(image_name="api:v2", provenance_score=95.0)
        result = eng.get_provenance(r.id)
        assert result is not None
        assert result.provenance_score == 95.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_provenance("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_provenance(image_name=f"img-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_provenance_records
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_provenance(image_name="a")
        eng.record_provenance(image_name="b")
        assert len(eng.list_provenance_records()) == 2

    def test_filter_by_provenance_level(self):
        eng = _engine()
        eng.record_provenance(image_name="a", provenance_level=ProvenanceLevel.FULL)
        eng.record_provenance(image_name="b", provenance_level=ProvenanceLevel.MINIMAL)
        results = eng.list_provenance_records(provenance_level=ProvenanceLevel.FULL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_provenance(image_name="a", team="platform")
        eng.record_provenance(image_name="b", team="security")
        results = eng.list_provenance_records(team="platform")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_provenance(image_name=f"img-{i}")
        assert len(eng.list_provenance_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            image_name="svc:v1",
            provenance_level=ProvenanceLevel.MINIMAL,
            analysis_score=35.0,
            threshold=60.0,
            breached=True,
            description="missing provenance metadata",
        )
        assert a.image_name == "svc:v1"
        assert a.provenance_level == ProvenanceLevel.MINIMAL
        assert a.analysis_score == 35.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(image_name=f"img-{i}")
        assert len(eng._analyses) == 2

    def test_filter_by_registry_type(self):
        eng = _engine()
        eng.record_provenance(image_name="a", registry_type=RegistryType.PRIVATE)
        eng.record_provenance(image_name="b", registry_type=RegistryType.PUBLIC)
        results = eng.list_provenance_records(registry_type=RegistryType.PRIVATE)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# analyze_provenance_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_provenance(
            image_name="a", provenance_level=ProvenanceLevel.FULL, provenance_score=90.0
        )
        eng.record_provenance(
            image_name="b", provenance_level=ProvenanceLevel.FULL, provenance_score=70.0
        )
        result = eng.analyze_provenance_distribution()
        assert "full" in result
        assert result["full"]["count"] == 2
        assert result["full"]["avg_provenance_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_provenance_distribution() == {}


# ---------------------------------------------------------------------------
# identify_provenance_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(provenance_gap_threshold=70.0)
        eng.record_provenance(image_name="a", provenance_score=50.0)
        eng.record_provenance(image_name="b", provenance_score=80.0)
        results = eng.identify_provenance_gaps()
        assert len(results) == 1
        assert results[0]["image_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(provenance_gap_threshold=80.0)
        eng.record_provenance(image_name="a", provenance_score=50.0)
        eng.record_provenance(image_name="b", provenance_score=20.0)
        results = eng.identify_provenance_gaps()
        assert len(results) == 2
        assert results[0]["provenance_score"] == 20.0


# ---------------------------------------------------------------------------
# rank_by_provenance
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_provenance(image_name="a", service="build-svc", provenance_score=90.0)
        eng.record_provenance(image_name="b", service="deploy-svc", provenance_score=40.0)
        results = eng.rank_by_provenance()
        assert len(results) == 2
        assert results[0]["service"] == "deploy-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_provenance() == []


# ---------------------------------------------------------------------------
# detect_provenance_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(image_name="img", analysis_score=50.0)
        result = eng.detect_provenance_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(image_name="img", analysis_score=20.0)
        eng.add_analysis(image_name="img", analysis_score=20.0)
        eng.add_analysis(image_name="img", analysis_score=80.0)
        eng.add_analysis(image_name="img", analysis_score=80.0)
        result = eng.detect_provenance_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_provenance_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(provenance_gap_threshold=60.0)
        eng.record_provenance(
            image_name="svc:v1",
            provenance_level=ProvenanceLevel.MINIMAL,
            registry_type=RegistryType.PUBLIC,
            provenance_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ContainerProvenanceReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_provenance(image_name="img")
        eng.add_analysis(image_name="img")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats(self):
        eng = _engine()
        eng.record_provenance(
            image_name="svc:v1",
            provenance_level=ProvenanceLevel.FULL,
            service="build-svc",
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "full" in stats["provenance_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.record_provenance(image_name=f"img-{i}")
        assert len(eng._records) == 2
        assert eng._records[-1].image_name == "img-4"
