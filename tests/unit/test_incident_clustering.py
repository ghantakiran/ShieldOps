"""Tests for shieldops.analytics.incident_clustering — IncidentClusteringEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.incident_clustering import (
    ClusterStatus,
    IncidentCluster,
    IncidentClusteringEngine,
    IncidentRecord,
    SimilarityMetric,
)


def _engine(**kw) -> IncidentClusteringEngine:
    return IncidentClusteringEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ClusterStatus (3 values)

    def test_status_active(self):
        assert ClusterStatus.ACTIVE == "active"

    def test_status_resolved(self):
        assert ClusterStatus.RESOLVED == "resolved"

    def test_status_archived(self):
        assert ClusterStatus.ARCHIVED == "archived"

    # SimilarityMetric (4 values)

    def test_metric_symptom(self):
        assert SimilarityMetric.SYMPTOM == "symptom"

    def test_metric_service(self):
        assert SimilarityMetric.SERVICE == "service"

    def test_metric_time_window(self):
        assert SimilarityMetric.TIME_WINDOW == "time_window"

    def test_metric_error_pattern(self):
        assert SimilarityMetric.ERROR_PATTERN == "error_pattern"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_incident_record_defaults(self):
        rec = IncidentRecord(title="alert")
        assert rec.id
        assert rec.title == "alert"
        assert rec.service == ""
        assert rec.symptoms == []
        assert rec.error_pattern == ""
        assert rec.severity == "medium"
        assert rec.occurred_at > 0

    def test_incident_cluster_defaults(self):
        cl = IncidentCluster(name="grp")
        assert cl.id
        assert cl.name == "grp"
        assert cl.incident_ids == []
        assert cl.root_cause == ""
        assert cl.status == ClusterStatus.ACTIVE
        assert cl.similarity_scores == {}
        assert cl.created_at > 0
        assert cl.updated_at is None


# ---------------------------------------------------------------------------
# add_incident
# ---------------------------------------------------------------------------


class TestAddIncident:
    def test_basic_add(self):
        e = _engine()
        inc = e.add_incident("CPU spike", service="web")
        assert inc.title == "CPU spike"
        assert inc.service == "web"
        assert inc.id in e._incidents

    def test_add_with_symptoms(self):
        e = _engine()
        inc = e.add_incident("OOM", symptoms=["memory_high", "gc_pause"])
        assert inc.symptoms == ["memory_high", "gc_pause"]

    def test_evicts_at_max_incidents(self):
        e = _engine(max_incidents=2)
        i1 = e.add_incident("First")
        e.add_incident("Second")
        e.add_incident("Third")
        assert len(e._incidents) == 2
        assert i1.id not in e._incidents


# ---------------------------------------------------------------------------
# _jaccard similarity
# ---------------------------------------------------------------------------


class TestSimilarity:
    def test_jaccard_overlapping_sets(self):
        result = IncidentClusteringEngine._jaccard({"a", "b", "c"}, {"b", "c", "d"})
        # intersection=2, union=4 => 0.5
        assert result == pytest.approx(0.5, abs=0.01)

    def test_jaccard_identical_sets(self):
        result = IncidentClusteringEngine._jaccard({"a", "b"}, {"a", "b"})
        assert result == pytest.approx(1.0, abs=0.01)

    def test_jaccard_disjoint_sets(self):
        result = IncidentClusteringEngine._jaccard({"a"}, {"b"})
        assert result == pytest.approx(0.0, abs=0.01)

    def test_jaccard_both_empty(self):
        result = IncidentClusteringEngine._jaccard(set(), set())
        assert result == 0.0

    def test_jaccard_one_empty(self):
        result = IncidentClusteringEngine._jaccard({"a"}, set())
        assert result == pytest.approx(0.0, abs=0.01)

    def test_compute_similarity_same_service_symptoms(self):
        e = _engine()
        a = IncidentRecord(
            title="A",
            service="web",
            symptoms=["cpu", "latency"],
            error_pattern="timeout",
        )
        b = IncidentRecord(
            title="B",
            service="web",
            symptoms=["cpu", "latency"],
            error_pattern="timeout",
        )
        sim = e._compute_similarity(a, b)
        assert sim == pytest.approx(1.0, abs=0.01)

    def test_compute_similarity_different_everything(self):
        e = _engine()
        a = IncidentRecord(
            title="A",
            service="web",
            symptoms=["cpu"],
            error_pattern="timeout",
        )
        b = IncidentRecord(
            title="B",
            service="db",
            symptoms=["disk"],
            error_pattern="connection_refused",
        )
        sim = e._compute_similarity(a, b)
        assert sim < 0.1

    def test_compute_similarity_partial_error_match(self):
        e = _engine()
        a = IncidentRecord(
            title="A",
            error_pattern="timeout",
        )
        b = IncidentRecord(
            title="B",
            error_pattern="timeout_error",
        )
        sim = e._compute_similarity(a, b)
        # Partial match contributes 0.15
        assert sim > 0.0


# ---------------------------------------------------------------------------
# find_similar
# ---------------------------------------------------------------------------


class TestFindSimilar:
    def test_finds_similar_incidents(self):
        e = _engine()
        i1 = e.add_incident("A", service="web", symptoms=["cpu"])
        e.add_incident("B", service="web", symptoms=["cpu"])
        e.add_incident("C", service="db", symptoms=["disk"])
        similar = e.find_similar(i1.id)
        assert len(similar) >= 1
        ids = [s[0] for s in similar]
        # B should be in similar results
        assert any(e._incidents[sid].title == "B" for sid in ids)

    def test_find_similar_not_found(self):
        e = _engine()
        result = e.find_similar("nonexistent")
        assert result == []

    def test_find_similar_respects_limit(self):
        e = _engine()
        base = e.add_incident("Base", service="web", symptoms=["cpu"])
        for i in range(5):
            e.add_incident(
                f"Similar-{i}",
                service="web",
                symptoms=["cpu"],
            )
        result = e.find_similar(base.id, limit=2)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# create_cluster
# ---------------------------------------------------------------------------


class TestCreateCluster:
    def test_manual_cluster(self):
        e = _engine()
        i1 = e.add_incident("A")
        i2 = e.add_incident("B")
        cluster = e.create_cluster("grp-1", [i1.id, i2.id])
        assert cluster.name == "grp-1"
        assert len(cluster.incident_ids) == 2

    def test_filters_invalid_ids(self):
        e = _engine()
        i1 = e.add_incident("A")
        cluster = e.create_cluster("grp-1", [i1.id, "nonexistent"])
        assert len(cluster.incident_ids) == 1
        assert cluster.incident_ids[0] == i1.id

    def test_empty_ids_all_invalid(self):
        e = _engine()
        cluster = e.create_cluster("grp-1", ["fake-1", "fake-2"])
        assert cluster.incident_ids == []


# ---------------------------------------------------------------------------
# auto_cluster
# ---------------------------------------------------------------------------


class TestAutoCluster:
    def test_groups_similar_incidents(self):
        e = _engine(similarity_threshold=0.5)
        e.add_incident("A", service="web", symptoms=["cpu", "mem"])
        e.add_incident("B", service="web", symptoms=["cpu", "mem"])
        clusters = e.auto_cluster(time_window_seconds=3600)
        assert len(clusters) >= 1
        assert len(clusters[0].incident_ids) >= 2

    def test_respects_similarity_threshold(self):
        e = _engine(similarity_threshold=0.99)
        e.add_incident("A", service="web", symptoms=["cpu"])
        e.add_incident("B", service="db", symptoms=["disk"])
        clusters = e.auto_cluster(time_window_seconds=3600)
        assert len(clusters) == 0

    def test_no_incidents_returns_empty(self):
        e = _engine()
        clusters = e.auto_cluster()
        assert clusters == []


# ---------------------------------------------------------------------------
# cluster operations
# ---------------------------------------------------------------------------


class TestClusterOps:
    def test_add_to_cluster(self):
        e = _engine()
        i1 = e.add_incident("A")
        i2 = e.add_incident("B")
        cluster = e.create_cluster("grp", [i1.id])
        result = e.add_to_cluster(cluster.id, i2.id)
        assert result is not None
        assert i2.id in result.incident_ids
        assert result.updated_at is not None

    def test_add_to_cluster_no_duplicate(self):
        e = _engine()
        i1 = e.add_incident("A")
        cluster = e.create_cluster("grp", [i1.id])
        e.add_to_cluster(cluster.id, i1.id)
        assert cluster.incident_ids.count(i1.id) == 1

    def test_add_to_cluster_not_found(self):
        e = _engine()
        result = e.add_to_cluster("fake", "inc-1")
        assert result is None

    def test_set_root_cause(self):
        e = _engine()
        i1 = e.add_incident("A")
        cluster = e.create_cluster("grp", [i1.id])
        result = e.set_root_cause(cluster.id, "Memory leak in service X")
        assert result is not None
        assert result.root_cause == "Memory leak in service X"
        assert result.updated_at is not None

    def test_set_root_cause_not_found(self):
        e = _engine()
        result = e.set_root_cause("fake", "cause")
        assert result is None

    def test_resolve_cluster(self):
        e = _engine()
        i1 = e.add_incident("A")
        cluster = e.create_cluster("grp", [i1.id])
        result = e.resolve_cluster(cluster.id)
        assert result is not None
        assert result.status == ClusterStatus.RESOLVED
        assert result.updated_at is not None

    def test_resolve_cluster_not_found(self):
        e = _engine()
        result = e.resolve_cluster("fake")
        assert result is None


# ---------------------------------------------------------------------------
# list_clusters
# ---------------------------------------------------------------------------


class TestListClusters:
    def test_list_all(self):
        e = _engine()
        i1 = e.add_incident("A")
        i2 = e.add_incident("B")
        e.create_cluster("grp-1", [i1.id])
        e.create_cluster("grp-2", [i2.id])
        assert len(e.list_clusters()) == 2

    def test_filter_by_status(self):
        e = _engine()
        i1 = e.add_incident("A")
        i2 = e.add_incident("B")
        c1 = e.create_cluster("grp-1", [i1.id])
        e.create_cluster("grp-2", [i2.id])
        e.resolve_cluster(c1.id)
        active = e.list_clusters(status=ClusterStatus.ACTIVE)
        resolved = e.list_clusters(status=ClusterStatus.RESOLVED)
        assert len(active) == 1
        assert len(resolved) == 1

    def test_list_empty(self):
        e = _engine()
        assert e.list_clusters() == []


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_incidents"] == 0
        assert stats["total_clusters"] == 0
        assert stats["avg_cluster_size"] == 0.0

    def test_populated_stats(self):
        e = _engine()
        i1 = e.add_incident("A")
        i2 = e.add_incident("B")
        i3 = e.add_incident("C")
        e.create_cluster("grp-1", [i1.id, i2.id])
        e.create_cluster("grp-2", [i3.id])
        stats = e.get_stats()
        assert stats["total_incidents"] == 3
        assert stats["total_clusters"] == 2
        # (2+1)/2 = 1.5
        assert stats["avg_cluster_size"] == pytest.approx(1.5, abs=0.01)
        by_status = stats["clusters_by_status"]
        assert by_status["active"] == 2
        assert by_status["resolved"] == 0
