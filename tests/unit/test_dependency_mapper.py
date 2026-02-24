"""Tests for shieldops.topology.dependency_mapper — ServiceDependencyMapper."""

from __future__ import annotations

from shieldops.topology.dependency_mapper import (
    DependencyCriticality,
    DependencyEdge,
    DependencyGraph,
    DependencyMapReport,
    DependencyType,
    GraphHealth,
    ServiceDependencyMapper,
)


def _engine(**kw) -> ServiceDependencyMapper:
    return ServiceDependencyMapper(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DependencyType (5)
    def test_type_sync_http(self):
        assert DependencyType.SYNC_HTTP == "sync_http"

    def test_type_async_message(self):
        assert DependencyType.ASYNC_MESSAGE == "async_message"

    def test_type_database(self):
        assert DependencyType.DATABASE == "database"

    def test_type_cache(self):
        assert DependencyType.CACHE == "cache"

    def test_type_shared_storage(self):
        assert DependencyType.SHARED_STORAGE == "shared_storage"

    # DependencyCriticality (5)
    def test_crit_critical(self):
        assert DependencyCriticality.CRITICAL == "critical"

    def test_crit_high(self):
        assert DependencyCriticality.HIGH == "high"

    def test_crit_medium(self):
        assert DependencyCriticality.MEDIUM == "medium"

    def test_crit_low(self):
        assert DependencyCriticality.LOW == "low"

    def test_crit_optional(self):
        assert DependencyCriticality.OPTIONAL == "optional"

    # GraphHealth (5)
    def test_health_healthy(self):
        assert GraphHealth.HEALTHY == "healthy"

    def test_health_has_cycles(self):
        assert GraphHealth.HAS_CYCLES == "has_cycles"

    def test_health_single_points(self):
        assert GraphHealth.SINGLE_POINTS == "single_points"

    def test_health_deep_chains(self):
        assert GraphHealth.DEEP_CHAINS == "deep_chains"

    def test_health_fragile(self):
        assert GraphHealth.FRAGILE == "fragile"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_edge_defaults(self):
        e = DependencyEdge()
        assert e.id
        assert e.source_service == ""
        assert e.target_service == ""
        assert e.dependency_type == (DependencyType.SYNC_HTTP)
        assert e.criticality == (DependencyCriticality.MEDIUM)
        assert e.latency_ms == 0.0
        assert e.failure_rate_pct == 0.0
        assert e.created_at > 0

    def test_graph_defaults(self):
        g = DependencyGraph()
        assert g.total_services == 0
        assert g.total_edges == 0
        assert g.depth == 0
        assert g.cycles == []
        assert g.single_points == []
        assert g.critical_paths == []
        assert g.health == GraphHealth.HEALTHY

    def test_report_defaults(self):
        r = DependencyMapReport()
        assert r.total_services == 0
        assert r.total_edges == 0
        assert r.graph_health == GraphHealth.HEALTHY
        assert r.avg_depth == 0.0
        assert r.by_type == {}
        assert r.by_criticality == {}
        assert r.issues == []
        assert r.recommendations == []


# -------------------------------------------------------------------
# register_dependency
# -------------------------------------------------------------------


class TestRegisterDependency:
    def test_basic_register(self):
        eng = _engine()
        e = eng.register_dependency("web", "api")
        assert e.source_service == "web"
        assert e.target_service == "api"

    def test_with_type_and_crit(self):
        eng = _engine()
        e = eng.register_dependency(
            "api",
            "db",
            dependency_type=DependencyType.DATABASE,
            criticality=DependencyCriticality.CRITICAL,
        )
        assert e.dependency_type == DependencyType.DATABASE
        assert e.criticality == (DependencyCriticality.CRITICAL)

    def test_unique_ids(self):
        eng = _engine()
        e1 = eng.register_dependency("a", "b")
        e2 = eng.register_dependency("c", "d")
        assert e1.id != e2.id

    def test_eviction_at_max(self):
        eng = _engine(max_edges=3)
        for i in range(5):
            eng.register_dependency(f"src{i}", "tgt")
        assert len(eng._edges) == 3


# -------------------------------------------------------------------
# get_dependency
# -------------------------------------------------------------------


class TestGetDependency:
    def test_found(self):
        eng = _engine()
        e = eng.register_dependency("web", "api")
        assert eng.get_dependency(e.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_dependency("nonexistent") is None


# -------------------------------------------------------------------
# list_dependencies
# -------------------------------------------------------------------


class TestListDependencies:
    def test_list_all(self):
        eng = _engine()
        eng.register_dependency("web", "api")
        eng.register_dependency("api", "db")
        assert len(eng.list_dependencies()) == 2

    def test_filter_by_source(self):
        eng = _engine()
        eng.register_dependency("web", "api")
        eng.register_dependency("api", "db")
        results = eng.list_dependencies(source="web")
        assert len(results) == 1

    def test_filter_by_target(self):
        eng = _engine()
        eng.register_dependency("web", "db")
        eng.register_dependency("api", "db")
        results = eng.list_dependencies(target="db")
        assert len(results) == 2


# -------------------------------------------------------------------
# build_graph
# -------------------------------------------------------------------


class TestBuildGraph:
    def test_empty_graph(self):
        eng = _engine()
        g = eng.build_graph()
        assert g.total_services == 0
        assert g.total_edges == 0

    def test_simple_graph(self):
        eng = _engine()
        eng.register_dependency("web", "api")
        eng.register_dependency("api", "db")
        g = eng.build_graph()
        assert g.total_services == 3
        assert g.total_edges == 2
        assert g.health == GraphHealth.HEALTHY

    def test_graph_with_cycle(self):
        eng = _engine()
        eng.register_dependency("a", "b")
        eng.register_dependency("b", "c")
        eng.register_dependency("c", "a")
        g = eng.build_graph()
        assert g.health == GraphHealth.HAS_CYCLES
        assert len(g.cycles) >= 1


# -------------------------------------------------------------------
# detect_cycles
# -------------------------------------------------------------------


class TestDetectCycles:
    def test_no_cycles(self):
        eng = _engine()
        eng.register_dependency("a", "b")
        eng.register_dependency("b", "c")
        assert len(eng.detect_cycles()) == 0

    def test_simple_cycle(self):
        eng = _engine()
        eng.register_dependency("a", "b")
        eng.register_dependency("b", "a")
        cycles = eng.detect_cycles()
        assert len(cycles) >= 1


# -------------------------------------------------------------------
# find_critical_path
# -------------------------------------------------------------------


class TestFindCriticalPath:
    def test_single_node(self):
        eng = _engine()
        eng.register_dependency("web", "api")
        path = eng.find_critical_path("api")
        assert path == ["api"]

    def test_chain(self):
        eng = _engine()
        eng.register_dependency("web", "api")
        eng.register_dependency("api", "db")
        path = eng.find_critical_path("web")
        assert path[0] == "web"
        assert len(path) >= 2

    def test_critical_edges_preferred(self):
        eng = _engine()
        eng.register_dependency(
            "web",
            "api",
            criticality=DependencyCriticality.CRITICAL,
        )
        eng.register_dependency(
            "web",
            "cache",
            criticality=DependencyCriticality.LOW,
        )
        path = eng.find_critical_path("web")
        assert "api" in path


# -------------------------------------------------------------------
# identify_single_points
# -------------------------------------------------------------------


class TestIdentifySinglePoints:
    def test_no_single_points(self):
        eng = _engine()
        eng.register_dependency("a", "b")
        results = eng.identify_single_points()
        assert len(results) == 0

    def test_with_single_point(self):
        eng = _engine()
        eng.register_dependency("web", "db")
        eng.register_dependency("api", "db")
        eng.register_dependency("worker", "db")
        results = eng.identify_single_points()
        assert "db" in results


# -------------------------------------------------------------------
# calculate_blast_radius
# -------------------------------------------------------------------


class TestCalculateBlastRadius:
    def test_leaf_node(self):
        eng = _engine()
        eng.register_dependency("web", "api")
        result = eng.calculate_blast_radius("web")
        assert result["total_affected"] >= 0

    def test_central_node(self):
        eng = _engine()
        eng.register_dependency("web", "api")
        eng.register_dependency("api", "db")
        eng.register_dependency("worker", "api")
        result = eng.calculate_blast_radius("api")
        assert result["total_affected"] >= 1

    def test_isolated_node(self):
        eng = _engine()
        eng.register_dependency("a", "b")
        result = eng.calculate_blast_radius("x")
        assert result["total_affected"] == 0


# -------------------------------------------------------------------
# generate_map_report
# -------------------------------------------------------------------


class TestGenerateMapReport:
    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_map_report()
        assert report.total_services == 0
        assert report.total_edges == 0

    def test_healthy_report(self):
        eng = _engine()
        eng.register_dependency("web", "api")
        eng.register_dependency("api", "db")
        report = eng.generate_map_report()
        assert report.total_services == 3
        assert report.total_edges == 2
        assert report.graph_health == GraphHealth.HEALTHY

    def test_report_with_issues(self):
        eng = _engine()
        eng.register_dependency("a", "b")
        eng.register_dependency("b", "c")
        eng.register_dependency("c", "a")
        report = eng.generate_map_report()
        assert len(report.issues) > 0
        assert len(report.recommendations) > 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.register_dependency("web", "api")
        eng.build_graph()
        eng.clear_data()
        assert len(eng._edges) == 0
        assert len(eng._graphs) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_edges"] == 0
        assert stats["total_services"] == 0

    def test_populated(self):
        eng = _engine()
        eng.register_dependency("web", "api")
        eng.register_dependency("api", "db")
        stats = eng.get_stats()
        assert stats["total_edges"] == 2
        assert stats["total_services"] == 3
        assert "web" in stats["services"]
        assert "api" in stats["services"]
        assert "db" in stats["services"]
