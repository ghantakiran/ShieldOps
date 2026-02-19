"""Tests for the Kubernetes security scanner.

Tests cover:
- RBAC wildcard detection and default SA binding checks
- Pod security context (privileged, hostNetwork, hostPID, hostIPC, runAsRoot)
- Resource limit checks
- Service account token automount checks
- No kubernetes connector registered
- Environment fallback for unknown targets
"""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from shieldops.connectors.base import ConnectorRouter
from shieldops.integrations.scanners.k8s_security import (
    K8sSecurityScanner,
    _parse_label_json,
)
from shieldops.models.base import Environment, Resource


def _make_resource(
    resource_id: str,
    labels: dict[str, str] | None = None,
    resource_type: str = "pod",
) -> Resource:
    return Resource(
        id=resource_id,
        name=resource_id,
        resource_type=resource_type,
        environment=Environment.PRODUCTION,
        provider="kubernetes",
        labels=labels or {},
    )


def _make_binding(
    binding_id: str,
    role_name: str,
    rules: list[dict[str, Any]],
    subjects: list[dict[str, Any]] | None = None,
) -> Resource:
    return _make_resource(
        binding_id,
        labels={
            "role_name": role_name,
            "rules": json.dumps(rules),
            "subjects": json.dumps(subjects or []),
        },
        resource_type="cluster_role_binding",
    )


@pytest.fixture
def k8s_connector() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def scanner(k8s_connector: AsyncMock) -> K8sSecurityScanner:
    router = ConnectorRouter()
    router._connectors["kubernetes"] = k8s_connector
    return K8sSecurityScanner(connector_router=router)


# ============================================================================
# Initialization
# ============================================================================


class TestInit:
    def test_scanner_name(self) -> None:
        router = ConnectorRouter()
        scanner = K8sSecurityScanner(connector_router=router)
        assert scanner.scanner_name == "k8s-security"

    def test_no_k8s_connector_returns_empty(self) -> None:
        router = ConnectorRouter()
        scanner = K8sSecurityScanner(connector_router=router)

        import asyncio

        findings = asyncio.get_event_loop().run_until_complete(scanner.scan("production"))
        assert findings == []


# ============================================================================
# RBAC checks
# ============================================================================


class TestRBACChecks:
    @pytest.mark.asyncio
    async def test_wildcard_verbs_and_resources_critical(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        binding = _make_binding(
            "admin-binding",
            "cluster-admin",
            rules=[{"verbs": ["*"], "resources": ["*"], "apiGroups": ["*"]}],
        )
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "cluster_role_binding": [binding],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["rbac"])

        wildcard = [f for f in findings if "Wildcard RBAC" in f["title"]]
        assert len(wildcard) == 1
        assert wildcard[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_default_sa_bound_to_admin_role(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        binding = _make_binding(
            "default-admin-binding",
            "cluster-admin",
            rules=[{"verbs": ["get"], "resources": ["pods"], "apiGroups": [""]}],
            subjects=[{"name": "default", "kind": "ServiceAccount", "namespace": "production"}],
        )
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "cluster_role_binding": [binding],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["rbac"])

        sa_findings = [f for f in findings if "Default SA" in f["title"]]
        assert len(sa_findings) == 1
        assert sa_findings[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_no_rbac_issues_clean(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        binding = _make_binding(
            "viewer-binding",
            "viewer",
            rules=[{"verbs": ["get", "list"], "resources": ["pods"], "apiGroups": [""]}],
        )
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "cluster_role_binding": [binding],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["rbac"])
        assert findings == []


# ============================================================================
# Pod security checks
# ============================================================================


class TestPodSecurityChecks:
    @pytest.mark.asyncio
    async def test_privileged_container_critical(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        pod = _make_resource("priv-pod", labels={"privileged": "true"})
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "pod": [pod],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["pod_security"])

        priv = [f for f in findings if "Privileged" in f["title"]]
        assert len(priv) == 1
        assert priv[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_host_network_sharing_high(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        pod = _make_resource("hostnet-pod", labels={"host_network": "true"})
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "pod": [pod],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["pod_security"])

        hostnet = [f for f in findings if "host_network" in f["title"]]
        assert len(hostnet) == 1
        assert hostnet[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_run_as_root_high(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        pod = _make_resource("root-pod", labels={"run_as_root": "true"})
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "pod": [pod],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["pod_security"])

        root = [f for f in findings if "root" in f["title"].lower()]
        assert len(root) == 1
        assert root[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_secure_pod_no_findings(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        pod = _make_resource(
            "safe-pod",
            labels={
                "privileged": "false",
                "host_network": "false",
                "run_as_root": "false",
            },
        )
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "pod": [pod],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["pod_security"])
        assert findings == []


# ============================================================================
# Resource limit checks
# ============================================================================


class TestResourceLimitChecks:
    @pytest.mark.asyncio
    async def test_missing_limits_flagged(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        pod = _make_resource("no-limits-pod", labels={"has_resource_limits": "false"})
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "pod": [pod],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["resource_limits"])

        assert len(findings) == 1
        assert findings[0]["severity"] == "medium"
        assert "resource limits" in findings[0]["title"].lower()

    @pytest.mark.asyncio
    async def test_has_limits_no_finding(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        pod = _make_resource("good-pod", labels={"has_resource_limits": "true"})
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "pod": [pod],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["resource_limits"])
        assert findings == []

    @pytest.mark.asyncio
    async def test_missing_label_defaults_to_true(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        """Absence of has_resource_limits label is treated as true (limits present)."""
        pod = _make_resource("no-label-pod", labels={})
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "pod": [pod],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["resource_limits"])
        assert findings == []


# ============================================================================
# Service account checks
# ============================================================================


class TestServiceAccountChecks:
    @pytest.mark.asyncio
    async def test_default_sa_with_automount_flagged(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        pod = _make_resource(
            "default-sa-pod",
            labels={
                "service_account": "default",
                "automount_sa_token": "true",
            },
        )
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "pod": [pod],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["service_accounts"])

        assert len(findings) == 1
        assert findings[0]["severity"] == "medium"

    @pytest.mark.asyncio
    async def test_custom_sa_not_flagged(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        pod = _make_resource(
            "custom-sa-pod",
            labels={
                "service_account": "my-app-sa",
                "automount_sa_token": "true",
            },
        )
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "pod": [pod],
            }.get(rtype, [])
        )

        findings = await scanner.scan("production", check_types=["service_accounts"])
        assert findings == []


# ============================================================================
# Helpers
# ============================================================================


class TestHelpers:
    def test_is_truthy_true_values(self) -> None:
        assert K8sSecurityScanner._is_truthy("true") is True
        assert K8sSecurityScanner._is_truthy("yes") is True
        assert K8sSecurityScanner._is_truthy("1") is True
        assert K8sSecurityScanner._is_truthy("True") is True

    def test_is_truthy_false_values(self) -> None:
        assert K8sSecurityScanner._is_truthy("false") is False
        assert K8sSecurityScanner._is_truthy("no") is False
        assert K8sSecurityScanner._is_truthy("0") is False
        assert K8sSecurityScanner._is_truthy("") is False

    def test_parse_label_json_valid(self) -> None:
        assert _parse_label_json("[1, 2, 3]", []) == [1, 2, 3]

    def test_parse_label_json_invalid(self) -> None:
        assert _parse_label_json("not json", "fallback") == "fallback"

    def test_parse_label_json_empty(self) -> None:
        assert _parse_label_json("", []) == []


# ============================================================================
# Findings sorting
# ============================================================================


class TestFindingsSorting:
    @pytest.mark.asyncio
    async def test_findings_sorted_by_severity_descending(
        self, scanner: K8sSecurityScanner, k8s_connector: AsyncMock
    ) -> None:
        """Critical findings should appear before medium findings."""
        priv_pod = _make_resource("priv-pod", labels={"privileged": "true"})
        no_limits_pod = _make_resource("no-limits-pod", labels={"has_resource_limits": "false"})
        k8s_connector.list_resources = AsyncMock(
            side_effect=lambda rtype, env, **kw: {
                "pod": [priv_pod, no_limits_pod],
            }.get(rtype, [])
        )

        findings = await scanner.scan(
            "production",
            check_types=["pod_security", "resource_limits"],
        )

        assert len(findings) >= 2
        severities = [f["severity"] for f in findings]
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        numeric = [severity_order[s] for s in severities]
        assert numeric == sorted(numeric, reverse=True)
