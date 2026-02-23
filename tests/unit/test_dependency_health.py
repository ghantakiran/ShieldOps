"""Tests for shieldops.observability.dependency_health -- DependencyHealthTracker."""

from __future__ import annotations

import pytest

from shieldops.observability.dependency_health import (
    CascadeAlert,
    DependencyHealthTracker,
    DependencyRecord,
    DependencyStatus,
    DependencyType,
    HealthCheck,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tracker(**kwargs) -> DependencyHealthTracker:
    return DependencyHealthTracker(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dependency_status_healthy(self):
        assert DependencyStatus.HEALTHY == "healthy"

    def test_dependency_status_degraded(self):
        assert DependencyStatus.DEGRADED == "degraded"

    def test_dependency_status_down(self):
        assert DependencyStatus.DOWN == "down"

    def test_dependency_status_unknown(self):
        assert DependencyStatus.UNKNOWN == "unknown"

    def test_dependency_type_database(self):
        assert DependencyType.DATABASE == "database"

    def test_dependency_type_api(self):
        assert DependencyType.API == "api"

    def test_dependency_type_queue(self):
        assert DependencyType.QUEUE == "queue"

    def test_dependency_type_cache(self):
        assert DependencyType.CACHE == "cache"

    def test_dependency_type_internal_service(self):
        assert DependencyType.INTERNAL_SERVICE == "internal_service"

    def test_dependency_type_external_service(self):
        assert DependencyType.EXTERNAL_SERVICE == "external_service"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dependency_record_defaults(self):
        r = DependencyRecord(name="pg", dependency_type=DependencyType.DATABASE)
        assert r.id
        assert r.name == "pg"
        assert r.status == DependencyStatus.UNKNOWN
        assert r.upstream_of == []
        assert r.downstream_of == []
        assert r.endpoint == ""
        assert r.metadata == {}
        assert r.created_at > 0

    def test_health_check_defaults(self):
        c = HealthCheck(dependency_id="dep1", status=DependencyStatus.HEALTHY)
        assert c.id
        assert c.latency_ms == 0.0
        assert c.error_message == ""
        assert c.checked_at > 0

    def test_cascade_alert_defaults(self):
        a = CascadeAlert(root_dependency_id="dep1")
        assert a.id
        assert a.affected_dependencies == []
        assert a.severity == "warning"
        assert a.message == ""
        assert a.detected_at > 0


# ---------------------------------------------------------------------------
# Register dependency
# ---------------------------------------------------------------------------


class TestRegisterDependency:
    def test_register_basic(self):
        t = _tracker()
        dep = t.register_dependency(name="postgres", dependency_type=DependencyType.DATABASE)
        assert dep.name == "postgres"
        assert dep.dependency_type == DependencyType.DATABASE
        assert dep.id

    def test_register_with_all_fields(self):
        t = _tracker()
        dep = t.register_dependency(
            name="redis",
            dependency_type=DependencyType.CACHE,
            upstream_of=["api-svc"],
            downstream_of=["queue-svc"],
            endpoint="redis://localhost:6379",
            metadata={"region": "us-east-1"},
        )
        assert dep.upstream_of == ["api-svc"]
        assert dep.downstream_of == ["queue-svc"]
        assert dep.endpoint == "redis://localhost:6379"
        assert dep.metadata["region"] == "us-east-1"

    def test_register_multiple(self):
        t = _tracker()
        t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        t.register_dependency(name="redis", dependency_type=DependencyType.CACHE)
        assert len(t.list_dependencies()) == 2

    def test_register_filter_by_type(self):
        t = _tracker()
        t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        t.register_dependency(name="redis", dependency_type=DependencyType.CACHE)
        t.register_dependency(name="mysql", dependency_type=DependencyType.DATABASE)
        dbs = t.list_dependencies(dep_type=DependencyType.DATABASE)
        assert len(dbs) == 2


# ---------------------------------------------------------------------------
# Record health check
# ---------------------------------------------------------------------------


class TestRecordHealthCheck:
    def test_record_basic(self):
        t = _tracker()
        dep = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        check = t.record_health_check(dep.id, DependencyStatus.HEALTHY)
        assert check.dependency_id == dep.id
        assert check.status == DependencyStatus.HEALTHY

    def test_record_with_latency_and_error(self):
        t = _tracker()
        dep = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        check = t.record_health_check(
            dep.id, DependencyStatus.DEGRADED, latency_ms=250.0, error_message="slow"
        )
        assert check.latency_ms == 250.0
        assert check.error_message == "slow"

    def test_record_unknown_dep_raises(self):
        t = _tracker()
        with pytest.raises(ValueError, match="Dependency not found"):
            t.record_health_check("nonexistent", DependencyStatus.HEALTHY)

    def test_record_updates_dependency_status(self):
        t = _tracker()
        dep = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        t.record_health_check(dep.id, DependencyStatus.DOWN)
        updated = t.get_dependency(dep.id)
        assert updated is not None
        assert updated.status == DependencyStatus.DOWN

    def test_record_trims_to_max_checks(self):
        t = _tracker(max_checks=3)
        dep = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        for _ in range(5):
            t.record_health_check(dep.id, DependencyStatus.HEALTHY)
        stats = t.get_stats()
        assert stats["total_checks"] == 3


# ---------------------------------------------------------------------------
# Get dependency status
# ---------------------------------------------------------------------------


class TestGetDependencyStatus:
    def test_returns_latest_status(self):
        t = _tracker()
        dep = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        t.record_health_check(dep.id, DependencyStatus.HEALTHY)
        t.record_health_check(dep.id, DependencyStatus.DEGRADED)
        assert t.get_dependency_status(dep.id) == DependencyStatus.DEGRADED

    def test_returns_unknown_for_unknown_dep(self):
        t = _tracker()
        assert t.get_dependency_status("nonexistent") == DependencyStatus.UNKNOWN

    def test_returns_unknown_when_no_checks(self):
        t = _tracker()
        dep = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        assert t.get_dependency_status(dep.id) == DependencyStatus.UNKNOWN


# ---------------------------------------------------------------------------
# Detect cascades
# ---------------------------------------------------------------------------


class TestDetectCascades:
    def test_no_cascades_all_healthy(self):
        t = _tracker()
        dep = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        t.record_health_check(dep.id, DependencyStatus.HEALTHY)
        cascades = t.detect_cascades()
        assert len(cascades) == 0

    def test_no_cascades_below_threshold(self):
        t = _tracker(cascade_threshold=3)
        root = t.register_dependency(name="root-db", dependency_type=DependencyType.DATABASE)
        t.register_dependency(
            name="svc1",
            dependency_type=DependencyType.INTERNAL_SERVICE,
            downstream_of=[root.id],
        )
        t.register_dependency(
            name="svc2",
            dependency_type=DependencyType.INTERNAL_SERVICE,
            downstream_of=[root.id],
        )
        t.record_health_check(root.id, DependencyStatus.DOWN)
        cascades = t.detect_cascades()
        assert len(cascades) == 0

    def test_cascade_when_threshold_met(self):
        t = _tracker(cascade_threshold=2)
        root = t.register_dependency(name="root-db", dependency_type=DependencyType.DATABASE)
        t.register_dependency(
            name="svc1",
            dependency_type=DependencyType.INTERNAL_SERVICE,
            downstream_of=[root.id],
        )
        t.register_dependency(
            name="svc2",
            dependency_type=DependencyType.INTERNAL_SERVICE,
            downstream_of=[root.id],
        )
        t.record_health_check(root.id, DependencyStatus.DOWN)
        cascades = t.detect_cascades()
        assert len(cascades) == 1
        assert cascades[0].root_dependency_id == root.id
        assert len(cascades[0].affected_dependencies) == 2

    def test_cascade_alert_severity_warning(self):
        t = _tracker(cascade_threshold=2)
        root = t.register_dependency(name="root-db", dependency_type=DependencyType.DATABASE)
        for i in range(2):
            t.register_dependency(
                name=f"svc{i}",
                dependency_type=DependencyType.INTERNAL_SERVICE,
                downstream_of=[root.id],
            )
        t.record_health_check(root.id, DependencyStatus.DOWN)
        cascades = t.detect_cascades()
        assert cascades[0].severity == "warning"

    def test_cascade_alert_severity_critical(self):
        t = _tracker(cascade_threshold=2)
        root = t.register_dependency(name="root-db", dependency_type=DependencyType.DATABASE)
        for i in range(4):
            t.register_dependency(
                name=f"svc{i}",
                dependency_type=DependencyType.INTERNAL_SERVICE,
                downstream_of=[root.id],
            )
        t.record_health_check(root.id, DependencyStatus.DOWN)
        cascades = t.detect_cascades()
        assert cascades[0].severity == "critical"

    def test_cascade_alert_message(self):
        t = _tracker(cascade_threshold=2)
        root = t.register_dependency(name="root-db", dependency_type=DependencyType.DATABASE)
        for i in range(2):
            t.register_dependency(
                name=f"svc{i}",
                dependency_type=DependencyType.INTERNAL_SERVICE,
                downstream_of=[root.id],
            )
        t.record_health_check(root.id, DependencyStatus.DOWN)
        cascades = t.detect_cascades()
        assert "root-db" in cascades[0].message
        assert "2" in cascades[0].message

    def test_cascade_not_triggered_for_degraded(self):
        t = _tracker(cascade_threshold=2)
        root = t.register_dependency(name="root-db", dependency_type=DependencyType.DATABASE)
        for i in range(3):
            t.register_dependency(
                name=f"svc{i}",
                dependency_type=DependencyType.INTERNAL_SERVICE,
                downstream_of=[root.id],
            )
        t.record_health_check(root.id, DependencyStatus.DEGRADED)
        cascades = t.detect_cascades()
        assert len(cascades) == 0


# ---------------------------------------------------------------------------
# List dependencies
# ---------------------------------------------------------------------------


class TestListDependencies:
    def test_list_all(self):
        t = _tracker()
        t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        t.register_dependency(name="redis", dependency_type=DependencyType.CACHE)
        assert len(t.list_dependencies()) == 2

    def test_filter_by_status(self):
        t = _tracker()
        dep1 = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        t.register_dependency(name="redis", dependency_type=DependencyType.CACHE)
        t.record_health_check(dep1.id, DependencyStatus.HEALTHY)
        healthy = t.list_dependencies(status=DependencyStatus.HEALTHY)
        assert len(healthy) == 1
        assert healthy[0].name == "pg"

    def test_filter_by_type(self):
        t = _tracker()
        t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        t.register_dependency(name="redis", dependency_type=DependencyType.CACHE)
        caches = t.list_dependencies(dep_type=DependencyType.CACHE)
        assert len(caches) == 1
        assert caches[0].name == "redis"

    def test_filter_by_status_and_type(self):
        t = _tracker()
        dep1 = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        dep2 = t.register_dependency(name="redis", dependency_type=DependencyType.CACHE)
        t.record_health_check(dep1.id, DependencyStatus.HEALTHY)
        t.record_health_check(dep2.id, DependencyStatus.HEALTHY)
        healthy_dbs = t.list_dependencies(
            status=DependencyStatus.HEALTHY, dep_type=DependencyType.DATABASE
        )
        assert len(healthy_dbs) == 1
        assert healthy_dbs[0].name == "pg"

    def test_list_empty(self):
        t = _tracker()
        assert len(t.list_dependencies()) == 0


# ---------------------------------------------------------------------------
# Get dependency
# ---------------------------------------------------------------------------


class TestGetDependency:
    def test_found(self):
        t = _tracker()
        dep = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        result = t.get_dependency(dep.id)
        assert result is not None
        assert result.name == "pg"

    def test_not_found(self):
        t = _tracker()
        assert t.get_dependency("nonexistent") is None


# ---------------------------------------------------------------------------
# Remove dependency
# ---------------------------------------------------------------------------


class TestRemoveDependency:
    def test_remove_success(self):
        t = _tracker()
        dep = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        assert t.remove_dependency(dep.id) is True
        assert t.get_dependency(dep.id) is None

    def test_remove_not_found(self):
        t = _tracker()
        assert t.remove_dependency("nonexistent") is False

    def test_remove_reduces_count(self):
        t = _tracker()
        dep = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        t.register_dependency(name="redis", dependency_type=DependencyType.CACHE)
        t.remove_dependency(dep.id)
        assert len(t.list_dependencies()) == 1


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        t = _tracker()
        s = t.get_stats()
        assert s["total_dependencies"] == 0
        assert s["total_checks"] == 0
        assert s["healthy_count"] == 0
        assert s["degraded_count"] == 0
        assert s["down_count"] == 0
        assert s["total_cascades"] == 0

    def test_stats_with_data(self):
        t = _tracker(cascade_threshold=1)
        dep1 = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        dep2 = t.register_dependency(
            name="svc1",
            dependency_type=DependencyType.INTERNAL_SERVICE,
            downstream_of=[dep1.id],
        )
        t.record_health_check(dep1.id, DependencyStatus.HEALTHY)
        t.record_health_check(dep2.id, DependencyStatus.DEGRADED)
        s = t.get_stats()
        assert s["total_dependencies"] == 2
        assert s["total_checks"] == 2
        assert s["healthy_count"] == 1
        assert s["degraded_count"] == 1
        assert s["down_count"] == 0

    def test_stats_counts_down(self):
        t = _tracker()
        dep = t.register_dependency(name="pg", dependency_type=DependencyType.DATABASE)
        t.record_health_check(dep.id, DependencyStatus.DOWN)
        s = t.get_stats()
        assert s["down_count"] == 1

    def test_stats_cascade_count(self):
        t = _tracker(cascade_threshold=1)
        root = t.register_dependency(name="root-db", dependency_type=DependencyType.DATABASE)
        t.register_dependency(
            name="svc1",
            dependency_type=DependencyType.INTERNAL_SERVICE,
            downstream_of=[root.id],
        )
        t.record_health_check(root.id, DependencyStatus.DOWN)
        t.detect_cascades()
        s = t.get_stats()
        assert s["total_cascades"] == 1
