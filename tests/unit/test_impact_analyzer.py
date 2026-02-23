"""Tests for shieldops.topology.impact_analyzer — ServiceDependencyImpactAnalyzer.

Covers:
- ImpactLevel, DependencyDirection, SimulationStatus enums
- ServiceDependency, ImpactPath, ImpactSimulation model defaults
- add_dependency (basic, unique IDs, eviction at max)
- remove_dependency (success, not found)
- simulate_failure (no deps, downstream chain, upstream chain, both directions, cycle handling)
- get_impact_paths (basic, not found)
- get_simulation (found, not found)
- list_simulations (all, filter by status)
- list_dependencies (all, filter by service)
- get_critical_services (basic, min threshold)
- get_stats (empty, populated)
- Impact levels (none, low, medium, high, critical)
"""

from __future__ import annotations

from shieldops.topology.impact_analyzer import (
    DependencyDirection,
    ImpactLevel,
    ImpactPath,
    ImpactSimulation,
    ServiceDependency,
    ServiceDependencyImpactAnalyzer,
    SimulationStatus,
)


def _analyzer(**kw) -> ServiceDependencyImpactAnalyzer:
    return ServiceDependencyImpactAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ImpactLevel (5 values)

    def test_impact_level_none(self):
        assert ImpactLevel.NONE == "none"

    def test_impact_level_low(self):
        assert ImpactLevel.LOW == "low"

    def test_impact_level_medium(self):
        assert ImpactLevel.MEDIUM == "medium"

    def test_impact_level_high(self):
        assert ImpactLevel.HIGH == "high"

    def test_impact_level_critical(self):
        assert ImpactLevel.CRITICAL == "critical"

    # DependencyDirection (3 values)

    def test_direction_upstream(self):
        assert DependencyDirection.UPSTREAM == "upstream"

    def test_direction_downstream(self):
        assert DependencyDirection.DOWNSTREAM == "downstream"

    def test_direction_both(self):
        assert DependencyDirection.BOTH == "both"

    # SimulationStatus (4 values)

    def test_status_pending(self):
        assert SimulationStatus.PENDING == "pending"

    def test_status_running(self):
        assert SimulationStatus.RUNNING == "running"

    def test_status_completed(self):
        assert SimulationStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert SimulationStatus.FAILED == "failed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_service_dependency_defaults(self):
        dep = ServiceDependency(source_service="a", target_service="b")
        assert dep.id
        assert dep.source_service == "a"
        assert dep.target_service == "b"
        assert dep.dependency_type == "runtime"
        assert dep.criticality == 3
        assert dep.created_at > 0

    def test_impact_path_defaults(self):
        path = ImpactPath()
        assert path.path == []
        assert path.impact_level == ImpactLevel.NONE
        assert path.depth == 0

    def test_impact_simulation_defaults(self):
        sim = ImpactSimulation(failed_service="web")
        assert sim.id
        assert sim.failed_service == "web"
        assert sim.direction == DependencyDirection.DOWNSTREAM
        assert sim.status == SimulationStatus.PENDING
        assert sim.affected_services == []
        assert sim.impact_paths == []
        assert sim.overall_impact == ImpactLevel.NONE
        assert sim.created_at > 0
        assert sim.completed_at is None


# ---------------------------------------------------------------------------
# add_dependency
# ---------------------------------------------------------------------------


class TestAddDependency:
    def test_basic_add(self):
        a = _analyzer()
        dep = a.add_dependency("api", "db")
        assert dep.source_service == "api"
        assert dep.target_service == "db"
        assert dep.dependency_type == "runtime"

    def test_unique_ids(self):
        a = _analyzer()
        d1 = a.add_dependency("api", "db")
        d2 = a.add_dependency("api", "cache")
        assert d1.id != d2.id

    def test_evicts_at_max(self):
        a = _analyzer(max_dependencies=2)
        d1 = a.add_dependency("a", "b")
        a.add_dependency("c", "d")
        a.add_dependency("e", "f")
        # d1 should have been evicted
        deps = a.list_dependencies()
        ids = {d.id for d in deps}
        assert d1.id not in ids
        assert len(deps) == 2


# ---------------------------------------------------------------------------
# remove_dependency
# ---------------------------------------------------------------------------


class TestRemoveDependency:
    def test_remove_success(self):
        a = _analyzer()
        dep = a.add_dependency("api", "db")
        assert a.remove_dependency(dep.id) is True
        assert a.list_dependencies() == []

    def test_remove_not_found(self):
        a = _analyzer()
        assert a.remove_dependency("nonexistent") is False


# ---------------------------------------------------------------------------
# simulate_failure
# ---------------------------------------------------------------------------


class TestSimulateFailure:
    def test_no_deps(self):
        a = _analyzer()
        sim = a.simulate_failure("web")
        assert sim.status == SimulationStatus.COMPLETED
        assert sim.affected_services == []
        assert sim.overall_impact == ImpactLevel.NONE

    def test_downstream_chain(self):
        a = _analyzer()
        a.add_dependency("api", "db")
        a.add_dependency("db", "storage")
        sim = a.simulate_failure("api", DependencyDirection.DOWNSTREAM)
        assert "db" in sim.affected_services
        assert "storage" in sim.affected_services
        assert sim.status == SimulationStatus.COMPLETED
        assert len(sim.impact_paths) >= 2

    def test_upstream_chain(self):
        a = _analyzer()
        a.add_dependency("api", "db")
        a.add_dependency("web", "api")
        sim = a.simulate_failure("db", DependencyDirection.UPSTREAM)
        assert "api" in sim.affected_services
        assert sim.status == SimulationStatus.COMPLETED

    def test_both_directions(self):
        a = _analyzer()
        a.add_dependency("api", "db")
        a.add_dependency("web", "api")
        sim = a.simulate_failure("api", DependencyDirection.BOTH)
        # downstream: db; upstream: web
        assert "db" in sim.affected_services
        assert "web" in sim.affected_services

    def test_cycle_handling(self):
        a = _analyzer()
        a.add_dependency("a", "b")
        a.add_dependency("b", "c")
        a.add_dependency("c", "a")
        # Should not hang due to cycle detection
        sim = a.simulate_failure("a", DependencyDirection.DOWNSTREAM)
        assert sim.status == SimulationStatus.COMPLETED
        assert "b" in sim.affected_services
        assert "c" in sim.affected_services


# ---------------------------------------------------------------------------
# get_impact_paths
# ---------------------------------------------------------------------------


class TestGetImpactPaths:
    def test_basic(self):
        a = _analyzer()
        a.add_dependency("api", "db")
        sim = a.simulate_failure("api")
        paths = a.get_impact_paths(sim.id)
        assert len(paths) >= 1
        assert paths[0].depth >= 1

    def test_not_found(self):
        a = _analyzer()
        assert a.get_impact_paths("nonexistent") == []


# ---------------------------------------------------------------------------
# get_simulation
# ---------------------------------------------------------------------------


class TestGetSimulation:
    def test_found(self):
        a = _analyzer()
        sim = a.simulate_failure("web")
        found = a.get_simulation(sim.id)
        assert found is not None
        assert found.id == sim.id

    def test_not_found(self):
        a = _analyzer()
        assert a.get_simulation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_simulations
# ---------------------------------------------------------------------------


class TestListSimulations:
    def test_list_all(self):
        a = _analyzer()
        a.simulate_failure("svc-a")
        a.simulate_failure("svc-b")
        sims = a.list_simulations()
        assert len(sims) == 2

    def test_filter_by_status(self):
        a = _analyzer()
        a.simulate_failure("svc-a")
        a.simulate_failure("svc-b")
        completed = a.list_simulations(status=SimulationStatus.COMPLETED)
        assert len(completed) == 2
        pending = a.list_simulations(status=SimulationStatus.PENDING)
        assert len(pending) == 0


# ---------------------------------------------------------------------------
# list_dependencies
# ---------------------------------------------------------------------------


class TestListDependencies:
    def test_list_all(self):
        a = _analyzer()
        a.add_dependency("api", "db")
        a.add_dependency("web", "api")
        deps = a.list_dependencies()
        assert len(deps) == 2

    def test_filter_by_service(self):
        a = _analyzer()
        a.add_dependency("api", "db")
        a.add_dependency("web", "api")
        a.add_dependency("web", "cache")
        # "api" appears as source and target
        deps = a.list_dependencies(service="api")
        assert len(deps) == 2


# ---------------------------------------------------------------------------
# get_critical_services
# ---------------------------------------------------------------------------


class TestGetCriticalServices:
    def test_basic(self):
        a = _analyzer()
        a.add_dependency("svc-a", "db")
        a.add_dependency("svc-b", "db")
        a.add_dependency("svc-c", "db")
        critical = a.get_critical_services(min_dependents=3)
        assert len(critical) == 1
        assert critical[0]["service"] == "db"
        assert critical[0]["dependent_count"] == 3

    def test_min_threshold(self):
        a = _analyzer()
        a.add_dependency("svc-a", "db")
        a.add_dependency("svc-b", "db")
        # Only 2 dependents; threshold is 3
        critical = a.get_critical_services(min_dependents=3)
        assert len(critical) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        a = _analyzer()
        stats = a.get_stats()
        assert stats["total_dependencies"] == 0
        assert stats["total_simulations"] == 0
        assert stats["simulation_status_distribution"] == {}
        assert stats["impact_distribution"] == {}

    def test_populated(self):
        a = _analyzer()
        a.add_dependency("api", "db")
        a.add_dependency("api", "cache")
        a.simulate_failure("api")
        stats = a.get_stats()
        assert stats["total_dependencies"] == 2
        assert stats["total_simulations"] == 1
        assert SimulationStatus.COMPLETED in stats["simulation_status_distribution"]


# ---------------------------------------------------------------------------
# Impact level thresholds
# ---------------------------------------------------------------------------


class TestImpactLevels:
    def test_none_impact_no_affected(self):
        a = _analyzer()
        sim = a.simulate_failure("isolated")
        assert sim.overall_impact == ImpactLevel.NONE

    def test_low_impact_up_to_2(self):
        a = _analyzer()
        a.add_dependency("root", "a")
        a.add_dependency("root", "b")
        sim = a.simulate_failure("root")
        assert sim.overall_impact == ImpactLevel.LOW

    def test_medium_impact_up_to_5(self):
        a = _analyzer()
        for i in range(4):
            a.add_dependency("root", f"svc-{i}")
        sim = a.simulate_failure("root")
        # 4 affected services => medium
        assert sim.overall_impact == ImpactLevel.MEDIUM
