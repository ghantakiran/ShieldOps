"""Tests for shieldops.policy.tenant_isolation — TenantResourceIsolationManager."""

from __future__ import annotations

import pytest

from shieldops.policy.tenant_isolation import (
    IsolationLevel,
    IsolationViolation,
    ResourceType,
    TenantBoundary,
    TenantResourceIsolationManager,
    ViolationSeverity,
)


def _manager(**kw) -> TenantResourceIsolationManager:
    return TenantResourceIsolationManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # IsolationLevel (4 values)

    def test_isolation_level_none(self):
        assert IsolationLevel.NONE == "none"

    def test_isolation_level_soft(self):
        assert IsolationLevel.SOFT == "soft"

    def test_isolation_level_hard(self):
        assert IsolationLevel.HARD == "hard"

    def test_isolation_level_strict(self):
        assert IsolationLevel.STRICT == "strict"

    # ResourceType (5 values)

    def test_resource_type_cpu(self):
        assert ResourceType.CPU == "cpu"

    def test_resource_type_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_resource_type_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_resource_type_network(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_type_pods(self):
        assert ResourceType.PODS == "pods"

    # ViolationSeverity (4 values)

    def test_violation_severity_info(self):
        assert ViolationSeverity.INFO == "info"

    def test_violation_severity_warning(self):
        assert ViolationSeverity.WARNING == "warning"

    def test_violation_severity_critical(self):
        assert ViolationSeverity.CRITICAL == "critical"

    def test_violation_severity_breach(self):
        assert ViolationSeverity.BREACH == "breach"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_tenant_boundary_defaults(self):
        boundary = TenantBoundary(tenant_name="team-alpha")
        assert boundary.id
        assert boundary.tenant_name == "team-alpha"
        assert boundary.namespace == ""
        assert boundary.isolation_level == IsolationLevel.SOFT
        assert boundary.resource_limits == {}
        assert boundary.resource_usage == {}
        assert boundary.tags == []
        assert boundary.created_at > 0
        assert boundary.updated_at > 0

    def test_isolation_violation_defaults(self):
        violation = IsolationViolation(
            tenant_id="t-1",
            resource_type=ResourceType.CPU,
            severity=ViolationSeverity.WARNING,
        )
        assert violation.id
        assert violation.tenant_id == "t-1"
        assert violation.resource_type == ResourceType.CPU
        assert violation.severity == ViolationSeverity.WARNING
        assert violation.limit_value == 0.0
        assert violation.actual_value == 0.0
        assert violation.message == ""
        assert violation.detected_at > 0


# ---------------------------------------------------------------------------
# register_tenant
# ---------------------------------------------------------------------------


class TestRegisterTenant:
    def test_basic_register(self):
        mgr = _manager()
        tenant = mgr.register_tenant("team-alpha")
        assert tenant.tenant_name == "team-alpha"
        assert tenant.isolation_level == IsolationLevel.SOFT
        assert mgr.get_tenant(tenant.id) is not None

    def test_register_assigns_unique_ids(self):
        mgr = _manager()
        t1 = mgr.register_tenant("team-a")
        t2 = mgr.register_tenant("team-b")
        assert t1.id != t2.id

    def test_register_with_extra_fields(self):
        mgr = _manager()
        tenant = mgr.register_tenant(
            "team-beta",
            namespace="beta-ns",
            isolation_level=IsolationLevel.HARD,
            resource_limits={"cpu": 4.0, "memory": 8.0},
            tags=["production"],
        )
        assert tenant.namespace == "beta-ns"
        assert tenant.isolation_level == IsolationLevel.HARD
        assert tenant.resource_limits == {"cpu": 4.0, "memory": 8.0}
        assert tenant.tags == ["production"]

    def test_evicts_at_max_tenants(self):
        mgr = _manager(max_tenants=3)
        ids = []
        for i in range(4):
            tenant = mgr.register_tenant(f"team-{i}")
            ids.append(tenant.id)
        assert mgr.get_tenant(ids[0]) is None
        assert mgr.get_tenant(ids[3]) is not None
        assert len(mgr.list_tenants()) == 3


# ---------------------------------------------------------------------------
# update_usage
# ---------------------------------------------------------------------------


class TestUpdateUsage:
    def test_basic_update(self):
        mgr = _manager()
        tenant = mgr.register_tenant("team-alpha")
        result = mgr.update_usage(tenant.id, ResourceType.CPU, 2.5)
        assert result is not None
        assert result.resource_usage["cpu"] == 2.5

    def test_update_not_found(self):
        mgr = _manager()
        result = mgr.update_usage("nonexistent", ResourceType.CPU, 1.0)
        assert result is None


# ---------------------------------------------------------------------------
# check_limits
# ---------------------------------------------------------------------------


class TestCheckLimits:
    def test_no_violations_under_limit(self):
        mgr = _manager()
        tenant = mgr.register_tenant(
            "team-alpha",
            resource_limits={"cpu": 4.0},
        )
        mgr.update_usage(tenant.id, ResourceType.CPU, 3.0)
        violations = mgr.check_limits(tenant.id)
        assert violations == []

    def test_warning_severity(self):
        mgr = _manager()
        tenant = mgr.register_tenant(
            "team-alpha",
            resource_limits={"cpu": 4.0},
        )
        # ratio = 4.5 / 4.0 = 1.125 -> > 1.0 and <= 1.2 -> WARNING
        mgr.update_usage(tenant.id, ResourceType.CPU, 4.5)
        violations = mgr.check_limits(tenant.id)
        assert len(violations) == 1
        assert violations[0].severity == ViolationSeverity.WARNING

    def test_critical_severity(self):
        mgr = _manager()
        tenant = mgr.register_tenant(
            "team-alpha",
            resource_limits={"cpu": 4.0},
        )
        # ratio = 5.5 / 4.0 = 1.375 -> > 1.2 and <= 1.5 -> CRITICAL
        mgr.update_usage(tenant.id, ResourceType.CPU, 5.5)
        violations = mgr.check_limits(tenant.id)
        assert len(violations) == 1
        assert violations[0].severity == ViolationSeverity.CRITICAL

    def test_breach_severity(self):
        mgr = _manager()
        tenant = mgr.register_tenant(
            "team-alpha",
            resource_limits={"cpu": 4.0},
        )
        # ratio = 7.0 / 4.0 = 1.75 -> > 1.5 -> BREACH
        mgr.update_usage(tenant.id, ResourceType.CPU, 7.0)
        violations = mgr.check_limits(tenant.id)
        assert len(violations) == 1
        assert violations[0].severity == ViolationSeverity.BREACH
        assert violations[0].limit_value == 4.0
        assert violations[0].actual_value == 7.0

    def test_check_limits_not_found(self):
        mgr = _manager()
        violations = mgr.check_limits("nonexistent")
        assert violations == []

    def test_multiple_resource_violations(self):
        mgr = _manager()
        tenant = mgr.register_tenant(
            "team-alpha",
            resource_limits={"cpu": 4.0, "memory": 8.0},
        )
        mgr.update_usage(tenant.id, ResourceType.CPU, 7.0)
        mgr.update_usage(tenant.id, ResourceType.MEMORY, 10.0)
        violations = mgr.check_limits(tenant.id)
        assert len(violations) == 2


# ---------------------------------------------------------------------------
# get_tenant
# ---------------------------------------------------------------------------


class TestGetTenant:
    def test_found(self):
        mgr = _manager()
        tenant = mgr.register_tenant("team-alpha")
        result = mgr.get_tenant(tenant.id)
        assert result is not None
        assert result.id == tenant.id

    def test_not_found(self):
        mgr = _manager()
        assert mgr.get_tenant("nonexistent") is None


# ---------------------------------------------------------------------------
# list_tenants
# ---------------------------------------------------------------------------


class TestListTenants:
    def test_list_all(self):
        mgr = _manager()
        mgr.register_tenant("team-a")
        mgr.register_tenant("team-b")
        mgr.register_tenant("team-c")
        assert len(mgr.list_tenants()) == 3

    def test_filter_by_isolation_level(self):
        mgr = _manager()
        mgr.register_tenant("team-a", isolation_level=IsolationLevel.SOFT)
        mgr.register_tenant("team-b", isolation_level=IsolationLevel.HARD)
        mgr.register_tenant("team-c", isolation_level=IsolationLevel.SOFT)
        results = mgr.list_tenants(isolation_level=IsolationLevel.SOFT)
        assert len(results) == 2
        assert all(t.isolation_level == IsolationLevel.SOFT for t in results)


# ---------------------------------------------------------------------------
# list_violations
# ---------------------------------------------------------------------------


class TestListViolations:
    def test_list_all_violations(self):
        mgr = _manager()
        t1 = mgr.register_tenant("team-a", resource_limits={"cpu": 4.0})
        t2 = mgr.register_tenant("team-b", resource_limits={"cpu": 4.0})
        mgr.update_usage(t1.id, ResourceType.CPU, 7.0)
        mgr.update_usage(t2.id, ResourceType.CPU, 5.0)
        mgr.check_limits(t1.id)
        mgr.check_limits(t2.id)
        all_violations = mgr.list_violations()
        assert len(all_violations) == 2

    def test_filter_by_tenant_id(self):
        mgr = _manager()
        t1 = mgr.register_tenant("team-a", resource_limits={"cpu": 4.0})
        t2 = mgr.register_tenant("team-b", resource_limits={"cpu": 4.0})
        mgr.update_usage(t1.id, ResourceType.CPU, 7.0)
        mgr.update_usage(t2.id, ResourceType.CPU, 5.0)
        mgr.check_limits(t1.id)
        mgr.check_limits(t2.id)
        results = mgr.list_violations(tenant_id=t1.id)
        assert len(results) == 1
        assert results[0].tenant_id == t1.id

    def test_filter_by_severity(self):
        mgr = _manager()
        t1 = mgr.register_tenant(
            "team-a",
            resource_limits={"cpu": 4.0},
        )
        # BREACH ratio
        mgr.update_usage(t1.id, ResourceType.CPU, 7.0)
        mgr.check_limits(t1.id)
        results = mgr.list_violations(severity=ViolationSeverity.BREACH)
        assert len(results) == 1
        assert results[0].severity == ViolationSeverity.BREACH


# ---------------------------------------------------------------------------
# delete_tenant
# ---------------------------------------------------------------------------


class TestDeleteTenant:
    def test_delete_success(self):
        mgr = _manager()
        tenant = mgr.register_tenant("team-alpha")
        assert mgr.delete_tenant(tenant.id) is True
        assert mgr.get_tenant(tenant.id) is None

    def test_delete_not_found(self):
        mgr = _manager()
        assert mgr.delete_tenant("nonexistent") is False


# ---------------------------------------------------------------------------
# get_utilization_report
# ---------------------------------------------------------------------------


class TestGetUtilizationReport:
    def test_basic_report(self):
        mgr = _manager()
        tenant = mgr.register_tenant(
            "team-alpha",
            resource_limits={"cpu": 4.0, "memory": 8.0},
        )
        mgr.update_usage(tenant.id, ResourceType.CPU, 2.0)
        mgr.update_usage(tenant.id, ResourceType.MEMORY, 4.0)
        report = mgr.get_utilization_report()
        assert len(report) == 1
        assert report[0]["tenant_name"] == "team-alpha"
        assert report[0]["utilization"]["cpu"] == pytest.approx(0.5, abs=1e-4)
        assert report[0]["utilization"]["memory"] == pytest.approx(0.5, abs=1e-4)

    def test_empty_report(self):
        mgr = _manager()
        report = mgr.get_utilization_report()
        assert report == []


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        mgr = _manager()
        stats = mgr.get_stats()
        assert stats["total_tenants"] == 0
        assert stats["total_violations"] == 0
        assert stats["isolation_level_distribution"] == {}
        assert stats["violation_severity_distribution"] == {}

    def test_stats_populated(self):
        mgr = _manager()
        t1 = mgr.register_tenant(
            "team-a",
            isolation_level=IsolationLevel.SOFT,
            resource_limits={"cpu": 4.0},
        )
        mgr.register_tenant(
            "team-b",
            isolation_level=IsolationLevel.HARD,
        )
        mgr.update_usage(t1.id, ResourceType.CPU, 7.0)
        mgr.check_limits(t1.id)

        stats = mgr.get_stats()
        assert stats["total_tenants"] == 2
        assert stats["total_violations"] == 1
        assert stats["isolation_level_distribution"][IsolationLevel.SOFT] == 1
        assert stats["isolation_level_distribution"][IsolationLevel.HARD] == 1
        assert stats["violation_severity_distribution"][ViolationSeverity.BREACH] == 1
