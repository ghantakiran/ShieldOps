"""Network security scanner using cloud provider APIs.

Checks security groups, firewall rules, open ports, and network exposure via
the :class:`~shieldops.connectors.base.ConnectorRouter` abstraction.  Each
provider connector's :meth:`~shieldops.connectors.base.InfraConnector.list_resources`
is called with well-known resource types; providers that do not support a
given resource type should raise an exception which is caught and skipped.
"""

import json
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.security.protocols import ScannerType, SecurityScanner
from shieldops.connectors.base import ConnectorRouter, InfraConnector
from shieldops.models.base import Environment

logger = structlog.get_logger()

# Mapping of TCP port → (service name, default severity when publicly exposed)
DANGEROUS_PORTS: dict[int, tuple[str, str]] = {
    22: ("SSH", "high"),
    23: ("Telnet", "critical"),
    25: ("SMTP", "medium"),
    135: ("MS-RPC", "high"),
    139: ("NetBIOS", "high"),
    445: ("SMB", "critical"),
    1433: ("MSSQL", "high"),
    1521: ("Oracle DB", "high"),
    3306: ("MySQL", "high"),
    3389: ("RDP", "critical"),
    5432: ("PostgreSQL", "high"),
    5900: ("VNC", "critical"),
    6379: ("Redis", "critical"),
    9200: ("Elasticsearch", "high"),
    11211: ("Memcached", "high"),
    27017: ("MongoDB", "critical"),
}

# CIDR blocks that indicate unrestricted (public-internet) access
OPEN_CIDR_BLOCKS: frozenset[str] = frozenset({"0.0.0.0/0", "::/0"})

_SEVERITY_SORT_KEY: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class NetworkSecurityScanner(SecurityScanner):
    """Scan network security configurations via cloud and Kubernetes APIs.

    Checks performed:

    - **Security groups / firewall rules** — ingress rules that permit
      unrestricted access (``0.0.0.0/0`` or ``::/0``) to well-known dangerous
      ports.
    - **Publicly exposed resources** — load balancers, storage buckets, and
      databases whose ``public_access`` label is truthy.
    - **Kubernetes NetworkPolicy gaps** — namespaces (excluding system
      namespaces) that have no ``NetworkPolicy`` defined.

    Args:
        connector_router: Populated :class:`~shieldops.connectors.base.ConnectorRouter`
            with at least one registered provider connector.
    """

    scanner_name = "network-security"
    scanner_type = ScannerType.NETWORK

    def __init__(self, connector_router: ConnectorRouter) -> None:
        self._router = connector_router

    async def scan(self, target: str, **options: Any) -> list[dict[str, Any]]:
        """Scan network security configurations across registered providers.

        Args:
            target: Environment name (``production``, ``staging``, ``development``).
                An unrecognised value falls back to ``production``.
            **options:
                providers (list[str]): Restrict scanning to these provider names.
                    Defaults to all registered providers.
                check_types (list[str]): Reserved for future fine-grained control.

        Returns:
            Merged list of network finding dicts, unsorted (severity varies per check).
        """
        logger.info("network_scan_started", target=target)

        try:
            env = Environment(target)
        except ValueError:
            logger.debug("network_scan_unknown_env", target=target, fallback="production")
            env = Environment.PRODUCTION

        findings: list[dict[str, Any]] = []
        providers: list[str] = options.get("providers") or list(self._router.providers)

        for provider in providers:
            try:
                connector = self._router.get(provider)
            except ValueError:
                logger.debug("network_scan_provider_unavailable", provider=provider)
                continue

            try:
                sg_findings = await self._check_security_groups(connector, provider, env)
                findings.extend(sg_findings)
            except Exception as exc:
                logger.error("network_scan_sg_failed", provider=provider, error=str(exc))

            try:
                exposure_findings = await self._check_public_exposure(connector, provider, env)
                findings.extend(exposure_findings)
            except Exception as exc:
                logger.error("network_scan_exposure_failed", provider=provider, error=str(exc))

        # Kubernetes NetworkPolicy check (provider-agnostic, checked separately)
        if "kubernetes" in self._router.providers:
            try:
                k8s_findings = await self._check_k8s_network_policies(env)
                findings.extend(k8s_findings)
            except Exception as exc:
                logger.error("network_scan_k8s_failed", error=str(exc))

        logger.info("network_scan_completed", target=target, findings_count=len(findings))
        return findings

    async def _check_security_groups(
        self,
        connector: InfraConnector,
        provider: str,
        env: Environment,
    ) -> list[dict[str, Any]]:
        """Identify security-group ingress rules that allow public access.

        Ingress rules are read from the ``ingress_rules`` label key.  The value
        may be a JSON-encoded list of rule objects or a plain Python list
        (depending on how the connector populates labels).

        Each rule object is expected to have:
            - ``cidr`` or ``source`` — the allowed source CIDR block.
            - ``port`` or ``from_port`` — the destination TCP port.
            - ``protocol`` — optional, defaults to ``tcp``.
        """
        findings: list[dict[str, Any]] = []

        try:
            resources = await connector.list_resources("security_group", env)
        except Exception:
            # Provider does not support this resource type — skip silently
            return []

        for resource in resources:
            raw_rules = resource.labels.get("ingress_rules", "[]")
            rules: list[dict[str, Any]] = []
            if isinstance(raw_rules, str):
                try:
                    parsed = json.loads(raw_rules)
                    if isinstance(parsed, list):
                        rules = parsed
                except (json.JSONDecodeError, TypeError):
                    pass
            elif isinstance(raw_rules, list):
                rules = raw_rules  # type: ignore[assignment]

            for rule in rules:
                if not isinstance(rule, dict):
                    continue

                cidr: str = rule.get("cidr", rule.get("source", ""))  # type: ignore[assignment]
                if cidr not in OPEN_CIDR_BLOCKS:
                    continue

                raw_port = rule.get("port", rule.get("from_port", 0))
                try:
                    port = int(raw_port)  # type: ignore[arg-type]
                except (ValueError, TypeError):
                    port = 0

                protocol: str = rule.get("protocol", "tcp")
                port_info = DANGEROUS_PORTS.get(port, (f"Port {port}", "medium"))
                severity = port_info[1] if port in DANGEROUS_PORTS else "medium"

                findings.append(
                    {
                        "finding_id": f"net-{uuid4().hex[:12]}",
                        "scanner_type": ScannerType.NETWORK.value,
                        "severity": severity,
                        "title": f"Public access to {port_info[0]} (port {port})",
                        "description": (
                            f"Security group '{resource.id}' in {provider} allows "
                            f"unrestricted {protocol} ingress to port {port} from {cidr}. "
                            f"This exposes {port_info[0]} to the public internet."
                        ),
                        "affected_resource": f"{provider}:{resource.id}",
                        "remediation": (
                            f"Restrict the ingress rule for port {port} to specific, trusted CIDR "
                            "blocks. Use a VPN or bastion host for administrative access."
                        ),
                        "metadata": {
                            "provider": provider,
                            "security_group_id": resource.id,
                            "port": port,
                            "protocol": protocol,
                            "cidr": cidr,
                            "service": port_info[0],
                            "environment": env.value,
                        },
                    }
                )

        return findings

    async def _check_public_exposure(
        self,
        connector: InfraConnector,
        provider: str,
        env: Environment,
    ) -> list[dict[str, Any]]:
        """Flag resources that have been marked as publicly accessible.

        Reads the ``public_access`` label key; any truthy string value
        (``true``, ``yes``, ``1``) is treated as an exposure signal.
        Databases are rated ``critical``; other resource types are ``high``.
        """
        findings: list[dict[str, Any]] = []

        for resource_type in ("load_balancer", "storage_bucket", "database"):
            try:
                resources = await connector.list_resources(resource_type, env)
            except Exception as exc:
                logger.debug(
                    "resource_type_unsupported", resource_type=resource_type, error=str(exc)
                )
                continue

            for resource in resources:
                is_public = resource.labels.get("public_access", "false")
                if str(is_public).lower() not in ("true", "yes", "1"):
                    continue

                severity = "critical" if resource_type == "database" else "high"
                human_type = resource_type.replace("_", " ").title()

                findings.append(
                    {
                        "finding_id": f"net-{uuid4().hex[:12]}",
                        "scanner_type": ScannerType.NETWORK.value,
                        "severity": severity,
                        "title": f"Publicly accessible {resource_type}: {resource.id}",
                        "description": (
                            f"{human_type} '{resource.id}' in {provider}/{env.value} "
                            "is publicly accessible from the internet."
                        ),
                        "affected_resource": f"{provider}:{resource.id}",
                        "remediation": (
                            f"Disable public access for {resource_type} '{resource.id}'. "
                            "Use private endpoints, VPC peering, or an internal load balancer."
                        ),
                        "metadata": {
                            "provider": provider,
                            "resource_type": resource_type,
                            "resource_id": resource.id,
                            "environment": env.value,
                        },
                    }
                )

        return findings

    async def _check_k8s_network_policies(self, env: Environment) -> list[dict[str, Any]]:
        """Flag Kubernetes namespaces that have no NetworkPolicy defined.

        System namespaces (``kube-system``, ``kube-public``,
        ``kube-node-lease``, ``default``) are excluded from the check.

        The connector is expected to surface a ``has_network_policy`` label
        (string ``"true"`` / ``"false"``) on namespace resources.
        """
        findings: list[dict[str, Any]] = []
        system_namespaces = frozenset(
            {
                "kube-system",
                "kube-public",
                "kube-node-lease",
                "default",
            }
        )

        try:
            connector = self._router.get("kubernetes")
            namespaces = await connector.list_resources("namespace", env)
        except Exception as exc:
            logger.debug("k8s_netpol_check_skipped", error=str(exc))
            return []

        for ns in namespaces:
            ns_name: str = ns.id
            if ns_name in system_namespaces:
                continue

            has_netpol = ns.labels.get("has_network_policy", "false")
            if str(has_netpol).lower() in ("true", "yes", "1"):
                continue

            findings.append(
                {
                    "finding_id": f"net-{uuid4().hex[:12]}",
                    "scanner_type": ScannerType.NETWORK.value,
                    "severity": "medium",
                    "title": f"No NetworkPolicy in namespace '{ns_name}'",
                    "description": (
                        f"Kubernetes namespace '{ns_name}' has no NetworkPolicy defined. "
                        "All pods in the namespace can communicate freely with each other "
                        "and with pods in other namespaces."
                    ),
                    "affected_resource": f"kubernetes:namespace/{ns_name}",
                    "remediation": (
                        f"Create a default-deny NetworkPolicy for namespace '{ns_name}' and "
                        "then explicitly allow only the traffic that is required."
                    ),
                    "metadata": {
                        "namespace": ns_name,
                        "environment": env.value,
                    },
                }
            )

        return findings
