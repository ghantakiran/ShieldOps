"""Tests for shieldops.incidents.incident_cluster — IncidentClusterEngine."""

from __future__ import annotations

from shieldops.incidents.incident_cluster import (
    ClusterMember,
    ClusterMethod,
    ClusterRecord,
    ClusterSize,
    ClusterStatus,
    IncidentClusterEngine,
    IncidentClusterReport,
)


def _engine(**kw) -> IncidentClusterEngine:
    return IncidentClusterEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_method_symptom(self):
        assert ClusterMethod.SYMPTOM == "symptom"

    def test_method_root_cause(self):
        assert ClusterMethod.ROOT_CAUSE == "root_cause"

    def test_method_service_affinity(self):
        assert ClusterMethod.SERVICE_AFFINITY == "service_affinity"

    def test_method_timeline_proximity(self):
        assert ClusterMethod.TIMELINE_PROXIMITY == "timeline_proximity"

    def test_method_impact_pattern(self):
        assert ClusterMethod.IMPACT_PATTERN == "impact_pattern"

    def test_size_single(self):
        assert ClusterSize.SINGLE == "single"

    def test_size_small(self):
        assert ClusterSize.SMALL == "small"

    def test_size_medium(self):
        assert ClusterSize.MEDIUM == "medium"

    def test_size_large(self):
        assert ClusterSize.LARGE == "large"

    def test_size_storm(self):
        assert ClusterSize.STORM == "storm"

    def test_status_forming(self):
        assert ClusterStatus.FORMING == "forming"

    def test_status_active(self):
        assert ClusterStatus.ACTIVE == "active"

    def test_status_resolved(self):
        assert ClusterStatus.RESOLVED == "resolved"

    def test_status_merged(self):
        assert ClusterStatus.MERGED == "merged"

    def test_status_split(self):
        assert ClusterStatus.SPLIT == "split"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cluster_record_defaults(self):
        r = ClusterRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.cluster_method == ClusterMethod.SYMPTOM
        assert r.cluster_size == ClusterSize.SINGLE
        assert r.cluster_status == ClusterStatus.FORMING
        assert r.confidence_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_cluster_member_defaults(self):
        m = ClusterMember()
        assert m.id
        assert m.cluster_id == ""
        assert m.incident_id == ""
        assert m.similarity_score == 0.0
        assert m.joined_at > 0
        assert m.created_at > 0

    def test_cluster_report_defaults(self):
        r = IncidentClusterReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_members == 0
        assert r.active_clusters == 0
        assert r.avg_confidence_score == 0.0
        assert r.by_method == {}
        assert r.by_size == {}
        assert r.by_status == {}
        assert r.storm_alerts == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_cluster
# ---------------------------------------------------------------------------


class TestRecordCluster:
    def test_basic(self):
        eng = _engine()
        r = eng.record_cluster(
            incident_id="INC-001",
            cluster_method=ClusterMethod.ROOT_CAUSE,
            cluster_size=ClusterSize.SMALL,
            confidence_score=85.0,
            team="sre",
        )
        assert r.incident_id == "INC-001"
        assert r.cluster_method == ClusterMethod.ROOT_CAUSE
        assert r.cluster_size == ClusterSize.SMALL
        assert r.confidence_score == 85.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_cluster(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_cluster
# ---------------------------------------------------------------------------


class TestGetCluster:
    def test_found(self):
        eng = _engine()
        r = eng.record_cluster(incident_id="INC-001", confidence_score=90.0)
        result = eng.get_cluster(r.id)
        assert result is not None
        assert result.confidence_score == 90.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_cluster("nonexistent") is None


# ---------------------------------------------------------------------------
# list_clusters
# ---------------------------------------------------------------------------


class TestListClusters:
    def test_list_all(self):
        eng = _engine()
        eng.record_cluster(incident_id="INC-001")
        eng.record_cluster(incident_id="INC-002")
        assert len(eng.list_clusters()) == 2

    def test_filter_by_method(self):
        eng = _engine()
        eng.record_cluster(incident_id="INC-001", cluster_method=ClusterMethod.SYMPTOM)
        eng.record_cluster(incident_id="INC-002", cluster_method=ClusterMethod.ROOT_CAUSE)
        results = eng.list_clusters(method=ClusterMethod.SYMPTOM)
        assert len(results) == 1

    def test_filter_by_size(self):
        eng = _engine()
        eng.record_cluster(incident_id="INC-001", cluster_size=ClusterSize.STORM)
        eng.record_cluster(incident_id="INC-002", cluster_size=ClusterSize.SMALL)
        results = eng.list_clusters(size=ClusterSize.STORM)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_cluster(incident_id="INC-001", team="sre")
        eng.record_cluster(incident_id="INC-002", team="platform")
        results = eng.list_clusters(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_cluster(incident_id=f"INC-{i}")
        assert len(eng.list_clusters(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_member
# ---------------------------------------------------------------------------


class TestAddMember:
    def test_basic(self):
        eng = _engine()
        m = eng.add_member(cluster_id="CLU-001", incident_id="INC-001", similarity_score=0.95)
        assert m.cluster_id == "CLU-001"
        assert m.incident_id == "INC-001"
        assert m.similarity_score == 0.95

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_member(cluster_id="CLU-001", incident_id=f"INC-{i}")
        assert len(eng._members) == 2


# ---------------------------------------------------------------------------
# analyze_cluster_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeClusterPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_cluster(
            incident_id="INC-001",
            cluster_method=ClusterMethod.SYMPTOM,
            confidence_score=80.0,
        )
        eng.record_cluster(
            incident_id="INC-002",
            cluster_method=ClusterMethod.SYMPTOM,
            confidence_score=60.0,
        )
        result = eng.analyze_cluster_patterns()
        assert "symptom" in result
        assert result["symptom"]["count"] == 2
        assert result["symptom"]["avg_confidence"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_cluster_patterns() == {}


# ---------------------------------------------------------------------------
# identify_incident_storms
# ---------------------------------------------------------------------------


class TestIdentifyIncidentStorms:
    def test_detects_large(self):
        eng = _engine()
        eng.record_cluster(incident_id="INC-001", cluster_size=ClusterSize.LARGE)
        eng.record_cluster(incident_id="INC-002", cluster_size=ClusterSize.SMALL)
        results = eng.identify_incident_storms()
        assert len(results) == 1
        assert results[0]["cluster_size"] == "large"

    def test_detects_storm(self):
        eng = _engine()
        eng.record_cluster(incident_id="INC-001", cluster_size=ClusterSize.STORM)
        results = eng.identify_incident_storms()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_incident_storms() == []


# ---------------------------------------------------------------------------
# rank_by_confidence
# ---------------------------------------------------------------------------


class TestRankByConfidence:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_cluster(incident_id="INC-001", team="sre", confidence_score=90.0)
        eng.record_cluster(incident_id="INC-002", team="platform", confidence_score=60.0)
        results = eng.rank_by_confidence()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_confidence"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# ---------------------------------------------------------------------------
# detect_cluster_trends
# ---------------------------------------------------------------------------


class TestDetectClusterTrends:
    def test_stable(self):
        eng = _engine()
        for score in [80.0, 80.0, 80.0, 80.0]:
            eng.record_cluster(incident_id="INC-001", confidence_score=score)
        result = eng.detect_cluster_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for score in [50.0, 50.0, 90.0, 90.0]:
            eng.record_cluster(incident_id="INC-001", confidence_score=score)
        result = eng.detect_cluster_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_cluster_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_cluster(
            incident_id="INC-001",
            cluster_size=ClusterSize.STORM,
            cluster_status=ClusterStatus.ACTIVE,
            confidence_score=95.0,
        )
        report = eng.generate_report()
        assert isinstance(report, IncidentClusterReport)
        assert report.total_records == 1
        assert report.active_clusters == 1
        assert len(report.storm_alerts) == 1
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
        eng.record_cluster(incident_id="INC-001")
        eng.add_member(cluster_id="CLU-001", incident_id="INC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._members) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_members"] == 0
        assert stats["method_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_cluster(
            incident_id="INC-001",
            cluster_method=ClusterMethod.SYMPTOM,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_incidents"] == 1
        assert "symptom" in stats["method_distribution"]
