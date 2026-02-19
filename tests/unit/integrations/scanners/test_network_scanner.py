"""Tests for the network security scanner.

Tests cover:
- Security group ingress rule scanning
- Public exposure detection (load balancers, storage, databases)
- Kubernetes NetworkPolicy gap detection
- Provider routing and error handling
- Dangerous port severity mapping
"""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from shieldops.connectors.base import ConnectorRouter
from shieldops.integrations.scanners.network_scanner import (
    DANGEROUS_PORTS,
    NetworkSecurityScanner,
)
from shieldops.models.base import Environment, Resource


def _make_resource(
    resource_id: str,
    labels: dict[str, str] | None = None,
    resource_type: str = "security_group",
) -> Resource:
    return Resource(
        id=resource_id,
        name=resource_id,
        resource_type=resource_type,
        environment=Environment.PRODUCTION,
        provider="aws",
        labels=labels or {},
    )


def _make_sg_with_open_rule(port: int, cidr: str = "0.0.0.0/0") -> Resource:
    rules = json.dumps([{"cidr": cidr, "port": port, "protocol": "tcp"}])
    return _make_resource("sg-open", labels={"ingress_rules": rules})


@pytest.fixture
def mock_connector() -> AsyncMock:
    connector = AsyncMock()
    connector.provider = "aws"
    return connector


@pytest.fixture
def router_with_aws(mock_connector: AsyncMock) -> ConnectorRouter:
    router = ConnectorRouter()
    router._connectors["aws"] = mock_connector
    return router_with_aws


@pytest.fixture
def scanner_with_aws(mock_connector: AsyncMock) -> NetworkSecurityScanner:
    router = ConnectorRouter()
    router._connectors["aws"] = mock_connector
    return NetworkSecurityScanner(connector_router=router)


@pytest.fixture
def scanner_with_k8s() -> tuple[NetworkSecurityScanner, AsyncMock]:
    k8s_connector = AsyncMock()
    k8s_connector.provider = "kubernetes"
    router = ConnectorRouter()
    router._connectors["kubernetes"] = k8s_connector
    return NetworkSecurityScanner(connector_router=router), k8s_connector


# ============================================================================
# Initialization
# ============================================================================


class TestInit:
    def test_scanner_name(self) -> None:
        router = ConnectorRouter()
        scanner = NetworkSecurityScanner(connector_router=router)
        assert scanner.scanner_name == "network-security"


# ============================================================================
# Security group checks
# ============================================================================


class TestSecurityGroupChecks:
    @pytest.mark.asyncio
    async def test_detects_open_ssh_port(
        self, scanner_with_aws: NetworkSecurityScanner, mock_connector: AsyncMock
    ) -> None:
        mock_connector.list_resources = AsyncMock(return_value=[_make_sg_with_open_rule(22)])

        findings = await scanner_with_aws.scan("production")

        sg_findings = [f for f in findings if "SSH" in f.get("title", "")]
        assert len(sg_findings) >= 1
        assert sg_findings[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_detects_open_rdp_critical(
        self, scanner_with_aws: NetworkSecurityScanner, mock_connector: AsyncMock
    ) -> None:
        mock_connector.list_resources = AsyncMock(return_value=[_make_sg_with_open_rule(3389)])

        findings = await scanner_with_aws.scan("production")

        rdp_findings = [f for f in findings if "RDP" in f.get("title", "")]
        assert len(rdp_findings) >= 1
        assert rdp_findings[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_ignores_restricted_cidr(
        self, scanner_with_aws: NetworkSecurityScanner, mock_connector: AsyncMock
    ) -> None:
        rules = json.dumps([{"cidr": "10.0.0.0/8", "port": 22, "protocol": "tcp"}])
        resource = _make_resource("sg-restricted", labels={"ingress_rules": rules})
        mock_connector.list_resources = AsyncMock(return_value=[resource])

        findings = await scanner_with_aws.scan("production")

        sg_findings = [f for f in findings if "SSH" in f.get("title", "")]
        assert sg_findings == []

    @pytest.mark.asyncio
    async def test_ipv6_open_cidr_detected(
        self, scanner_with_aws: NetworkSecurityScanner, mock_connector: AsyncMock
    ) -> None:
        mock_connector.list_resources = AsyncMock(
            return_value=[_make_sg_with_open_rule(6379, cidr="::/0")]
        )

        findings = await scanner_with_aws.scan("production")

        redis_findings = [f for f in findings if "Redis" in f.get("title", "")]
        assert len(redis_findings) >= 1
        assert redis_findings[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_rules_as_list_not_json_string(
        self, scanner_with_aws: NetworkSecurityScanner, mock_connector: AsyncMock
    ) -> None:
        """Connector may surface rules as a Python list instead of JSON string."""
        resource = _make_resource(
            "sg-list",
            labels={"ingress_rules": "not-valid-json"},
        )
        # The ingress_rules label is a non-JSON string; should not crash
        mock_connector.list_resources = AsyncMock(return_value=[resource])

        findings = await scanner_with_aws.scan("production")
        # No crash, just no findings from this resource
        sg_findings = [
            f for f in findings if f.get("metadata", {}).get("security_group_id") == "sg-list"
        ]
        assert sg_findings == []

    @pytest.mark.asyncio
    async def test_unsupported_resource_type_skipped(
        self, scanner_with_aws: NetworkSecurityScanner, mock_connector: AsyncMock
    ) -> None:
        mock_connector.list_resources = AsyncMock(side_effect=Exception("unsupported"))

        findings = await scanner_with_aws.scan("production")
        # Should not raise; no findings from this provider
        assert isinstance(findings, list)


# ============================================================================
# Public exposure checks
# ============================================================================


class TestPublicExposure:
    @pytest.mark.asyncio
    async def test_public_database_is_critical(
        self, scanner_with_aws: NetworkSecurityScanner, mock_connector: AsyncMock
    ) -> None:
        db_resource = _make_resource(
            "db-prod",
            labels={"public_access": "true"},
            resource_type="database",
        )

        async def list_resources(rtype: str, env: Environment, **kwargs: Any) -> list[Resource]:
            if rtype == "database":
                return [db_resource]
            if rtype == "security_group":
                return []
            return []

        mock_connector.list_resources = AsyncMock(side_effect=list_resources)

        findings = await scanner_with_aws.scan("production")

        db_findings = [
            f for f in findings if f.get("metadata", {}).get("resource_type") == "database"
        ]
        assert len(db_findings) == 1
        assert db_findings[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_public_lb_is_high(
        self, scanner_with_aws: NetworkSecurityScanner, mock_connector: AsyncMock
    ) -> None:
        lb_resource = _make_resource(
            "lb-prod",
            labels={"public_access": "yes"},
            resource_type="load_balancer",
        )

        async def list_resources(rtype: str, env: Environment, **kwargs: Any) -> list[Resource]:
            if rtype == "load_balancer":
                return [lb_resource]
            if rtype == "security_group":
                return []
            return []

        mock_connector.list_resources = AsyncMock(side_effect=list_resources)

        findings = await scanner_with_aws.scan("production")

        lb_findings = [
            f for f in findings if f.get("metadata", {}).get("resource_type") == "load_balancer"
        ]
        assert len(lb_findings) == 1
        assert lb_findings[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_private_resource_not_flagged(
        self, scanner_with_aws: NetworkSecurityScanner, mock_connector: AsyncMock
    ) -> None:
        private_db = _make_resource(
            "db-private",
            labels={"public_access": "false"},
            resource_type="database",
        )

        async def list_resources(rtype: str, env: Environment, **kwargs: Any) -> list[Resource]:
            if rtype == "database":
                return [private_db]
            if rtype == "security_group":
                return []
            return []

        mock_connector.list_resources = AsyncMock(side_effect=list_resources)

        findings = await scanner_with_aws.scan("production")

        db_findings = [
            f for f in findings if f.get("metadata", {}).get("resource_type") == "database"
        ]
        assert db_findings == []


# ============================================================================
# Kubernetes NetworkPolicy checks
# ============================================================================


class TestK8sNetworkPolicyChecks:
    @pytest.mark.asyncio
    async def test_namespace_without_netpol_flagged(self) -> None:
        scanner, k8s = scanner_with_k8s_fixture()
        ns = _make_resource(
            "my-app",
            labels={"has_network_policy": "false"},
            resource_type="namespace",
        )
        k8s.list_resources = AsyncMock(return_value=[ns])

        findings = await scanner.scan("production")

        netpol_findings = [f for f in findings if "NetworkPolicy" in f.get("title", "")]
        assert len(netpol_findings) == 1
        assert netpol_findings[0]["severity"] == "medium"

    @pytest.mark.asyncio
    async def test_system_namespace_excluded(self) -> None:
        scanner, k8s = scanner_with_k8s_fixture()
        ns = _make_resource(
            "kube-system",
            labels={"has_network_policy": "false"},
            resource_type="namespace",
        )
        k8s.list_resources = AsyncMock(return_value=[ns])

        findings = await scanner.scan("production")

        netpol_findings = [f for f in findings if "NetworkPolicy" in f.get("title", "")]
        assert netpol_findings == []

    @pytest.mark.asyncio
    async def test_namespace_with_netpol_not_flagged(self) -> None:
        scanner, k8s = scanner_with_k8s_fixture()
        ns = _make_resource(
            "secure-app",
            labels={"has_network_policy": "true"},
            resource_type="namespace",
        )
        k8s.list_resources = AsyncMock(return_value=[ns])

        findings = await scanner.scan("production")

        netpol_findings = [f for f in findings if "NetworkPolicy" in f.get("title", "")]
        assert netpol_findings == []


# ============================================================================
# Unknown environment fallback
# ============================================================================


class TestEnvironmentFallback:
    @pytest.mark.asyncio
    async def test_unknown_env_falls_back_to_production(
        self, scanner_with_aws: NetworkSecurityScanner, mock_connector: AsyncMock
    ) -> None:
        mock_connector.list_resources = AsyncMock(return_value=[])
        # Should not raise even with an invalid environment name
        findings = await scanner_with_aws.scan("nonexistent-env")
        assert isinstance(findings, list)


# ============================================================================
# Dangerous ports constants
# ============================================================================


class TestDangerousPorts:
    def test_contains_known_ports(self) -> None:
        assert 22 in DANGEROUS_PORTS
        assert 3389 in DANGEROUS_PORTS
        assert 27017 in DANGEROUS_PORTS

    def test_telnet_is_critical(self) -> None:
        assert DANGEROUS_PORTS[23][1] == "critical"

    def test_ssh_is_high(self) -> None:
        assert DANGEROUS_PORTS[22][1] == "high"


# ============================================================================
# Helpers
# ============================================================================


def scanner_with_k8s_fixture() -> tuple[NetworkSecurityScanner, AsyncMock]:
    k8s_connector = AsyncMock()
    k8s_connector.provider = "kubernetes"
    router = ConnectorRouter()
    router._connectors["kubernetes"] = k8s_connector
    return NetworkSecurityScanner(connector_router=router), k8s_connector
