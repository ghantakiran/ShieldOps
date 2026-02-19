"""Kubernetes security scanner.

Checks RBAC configuration, pod security standards, resource limits, and
service-account hygiene via the Kubernetes connector abstraction.

All resource metadata is read from the :attr:`~shieldops.models.base.Resource.labels`
dict (``dict[str, str]``), so connector implementations must serialise complex
structures (e.g. RBAC rules, subjects lists) as JSON strings under well-known
label keys.  This module parses those JSON strings internally.
"""

import json
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.security.protocols import ScannerType, SecurityScanner
from shieldops.connectors.base import ConnectorRouter, InfraConnector
from shieldops.models.base import Environment, Resource

logger = structlog.get_logger()

_SEVERITY_SORT_KEY: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}

# Kubernetes system namespaces excluded from policy-gap checks
_SYSTEM_NAMESPACES = frozenset(
    {
        "kube-system",
        "kube-public",
        "kube-node-lease",
        "default",
    }
)


def _parse_label_json(value: str, fallback: Any) -> Any:
    """Safely parse a JSON-encoded string from a resource label.

    Returns *fallback* if the value is empty, not a string, or invalid JSON.
    """
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


class K8sSecurityScanner(SecurityScanner):
    """Scan Kubernetes clusters for security misconfigurations.

    Checks performed:

    - **RBAC** — wildcard verb/resource permissions and default service-account
      bindings to admin roles.
    - **Pod security** — privileged containers, host-namespace sharing
      (``hostNetwork``, ``hostPID``, ``hostIPC``), and containers running as root.
    - **Resource limits** — pods that lack CPU/memory resource limits.
    - **Service accounts** — pods using the default SA with the API token
      auto-mounted.

    Args:
        connector_router: Populated :class:`~shieldops.connectors.base.ConnectorRouter`
            with a ``kubernetes`` provider registered.
    """

    scanner_name = "k8s-security"
    scanner_type = ScannerType.K8S_SECURITY

    def __init__(self, connector_router: ConnectorRouter) -> None:
        self._router = connector_router

    async def scan(self, target: str, **options: Any) -> list[dict[str, Any]]:
        """Scan a Kubernetes cluster for security issues.

        Args:
            target: Environment name (``production``, ``staging``, ``development``).
                An unrecognised value falls back to ``production``.
            **options:
                check_types (list[str]): Subset of checks to run.  Valid values:
                    ``rbac``, ``pod_security``, ``resource_limits``,
                    ``service_accounts``.  Defaults to all four.

        Returns:
            Merged list of finding dicts sorted by severity descending.
        """
        logger.info("k8s_security_scan_started", target=target)

        try:
            env = Environment(target)
        except ValueError:
            logger.debug("k8s_security_unknown_env", target=target, fallback="production")
            env = Environment.PRODUCTION

        try:
            connector = self._router.get("kubernetes")
        except ValueError:
            logger.warning("k8s_security_scan_no_connector")
            return []

        check_types: list[str] = options.get(
            "check_types",
            ["rbac", "pod_security", "resource_limits", "service_accounts"],
        )

        findings: list[dict[str, Any]] = []

        if "rbac" in check_types:
            findings.extend(await self._check_rbac(connector, env))

        if "pod_security" in check_types:
            findings.extend(await self._check_pod_security(connector, env))

        if "resource_limits" in check_types:
            findings.extend(await self._check_resource_limits(connector, env))

        if "service_accounts" in check_types:
            findings.extend(await self._check_service_accounts(connector, env))

        findings.sort(key=lambda f: _SEVERITY_SORT_KEY.get(f["severity"], 0), reverse=True)

        logger.info(
            "k8s_security_scan_completed",
            target=target,
            findings_count=len(findings),
        )
        return findings

    # ------------------------------------------------------------------
    # RBAC checks
    # ------------------------------------------------------------------

    async def _check_rbac(
        self, connector: InfraConnector, env: Environment
    ) -> list[dict[str, Any]]:
        """Check ClusterRoleBindings for overly permissive RBAC rules.

        Connector must expose ``cluster_role_binding`` resources with labels:
            - ``role_name`` (str): Name of the bound ClusterRole.
            - ``subjects`` (JSON list of subject dicts).
            - ``rules`` (JSON list of policy rule dicts with ``verbs``,
              ``resources``, and ``apiGroups`` keys).
        """
        findings: list[dict[str, Any]] = []

        try:
            bindings = await connector.list_resources("cluster_role_binding", env)
        except Exception as exc:
            logger.debug("k8s_rbac_check_skipped", error=str(exc))
            return []

        for binding in bindings:
            role_name: str = binding.labels.get("role_name", "")
            subjects: list[dict[str, Any]] = _parse_label_json(
                binding.labels.get("subjects", "[]"), []
            )
            rules: list[dict[str, Any]] = _parse_label_json(binding.labels.get("rules", "[]"), [])

            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                verbs: list[str] = rule.get("verbs", [])
                resources: list[str] = rule.get("resources", [])
                api_groups: list[str] = rule.get("apiGroups", [])

                if "*" in verbs and "*" in resources:
                    findings.append(
                        self._make_finding(
                            severity="critical",
                            title=f"Wildcard RBAC permissions: {binding.id}",
                            description=(
                                f"ClusterRoleBinding '{binding.id}' grants wildcard verbs on "
                                f"wildcard resources via role '{role_name}'. "
                                "This is equivalent to cluster-admin access."
                            ),
                            affected_resource=f"kubernetes:clusterrolebinding/{binding.id}",
                            remediation=(
                                "Apply the principle of least privilege. Replace wildcard "
                                "verbs and resource patterns with specific permissions."
                            ),
                            metadata={
                                "binding_name": binding.id,
                                "role_name": role_name,
                                "subjects": subjects,
                                "verbs": verbs,
                                "resources": resources,
                                "api_groups": api_groups,
                            },
                        )
                    )

            # Flag default service-account bindings to roles containing "admin"
            for subject in subjects:
                if not isinstance(subject, dict):
                    continue
                if (
                    subject.get("name") == "default"
                    and subject.get("kind") == "ServiceAccount"
                    and "admin" in role_name.lower()
                ):
                    findings.append(
                        self._make_finding(
                            severity="high",
                            title=f"Default SA bound to admin role: {binding.id}",
                            description=(
                                f"The default ServiceAccount in namespace "
                                f"'{subject.get('namespace', 'unknown')}' is bound to "
                                f"admin role '{role_name}' via binding '{binding.id}'."
                            ),
                            affected_resource=f"kubernetes:clusterrolebinding/{binding.id}",
                            remediation=(
                                "Create a dedicated ServiceAccount with minimal permissions "
                                "and remove the binding from the default SA."
                            ),
                            metadata={
                                "binding_name": binding.id,
                                "role_name": role_name,
                                "subject": subject,
                            },
                        )
                    )

        return findings

    # ------------------------------------------------------------------
    # Pod security checks
    # ------------------------------------------------------------------

    async def _check_pod_security(
        self, connector: InfraConnector, env: Environment
    ) -> list[dict[str, Any]]:
        """Check pods for insecure security-context settings.

        Connector must expose ``pod`` resources with boolean-string labels:
            - ``privileged`` — container runs in privileged mode.
            - ``host_network`` / ``host_pid`` / ``host_ipc`` — host-namespace sharing.
            - ``run_as_root`` — container UID is 0.
        """
        findings: list[dict[str, Any]] = []

        try:
            pods = await connector.list_resources("pod", env)
        except Exception as exc:
            logger.debug("k8s_pod_security_check_skipped", error=str(exc))
            return []

        for pod in pods:
            findings.extend(self._check_pod_security_context(pod))

        return findings

    def _check_pod_security_context(self, pod: Resource) -> list[dict[str, Any]]:
        """Evaluate security-context labels for a single pod."""
        findings: list[dict[str, Any]] = []
        labels = pod.labels or {}

        if self._is_truthy(labels.get("privileged", "false")):
            findings.append(
                self._make_finding(
                    severity="critical",
                    title=f"Privileged container: {pod.id}",
                    description=(
                        f"Pod '{pod.id}' runs with a privileged security context. "
                        "This grants full host access and bypasses all Linux security controls."
                    ),
                    affected_resource=f"kubernetes:pod/{pod.id}",
                    remediation=(
                        "Remove 'privileged: true' from the security context. "
                        "Use specific Linux capabilities (e.g. NET_ADMIN) instead."
                    ),
                    metadata={"pod": pod.id, "check": "privileged"},
                )
            )

        for host_ns in ("host_network", "host_pid", "host_ipc"):
            if self._is_truthy(labels.get(host_ns, "false")):
                ns_display = host_ns.replace("host_", "host ")
                findings.append(
                    self._make_finding(
                        severity="high",
                        title=f"Host namespace sharing: {pod.id} ({host_ns})",
                        description=(
                            f"Pod '{pod.id}' shares the {ns_display} namespace with the host."
                        ),
                        affected_resource=f"kubernetes:pod/{pod.id}",
                        remediation=(
                            f"Disable {host_ns} unless absolutely required by the workload."
                        ),
                        metadata={"pod": pod.id, "check": host_ns},
                    )
                )

        if self._is_truthy(labels.get("run_as_root", "false")):
            findings.append(
                self._make_finding(
                    severity="high",
                    title=f"Container runs as root: {pod.id}",
                    description=(
                        f"Pod '{pod.id}' runs as root user (UID 0), increasing the blast radius "
                        "of any container escape."
                    ),
                    affected_resource=f"kubernetes:pod/{pod.id}",
                    remediation=(
                        "Set 'runAsNonRoot: true' and specify a non-zero 'runAsUser' "
                        "in the pod's security context."
                    ),
                    metadata={"pod": pod.id, "check": "run_as_root"},
                )
            )

        return findings

    # ------------------------------------------------------------------
    # Resource-limit checks
    # ------------------------------------------------------------------

    async def _check_resource_limits(
        self, connector: InfraConnector, env: Environment
    ) -> list[dict[str, Any]]:
        """Flag pods that have no CPU/memory resource limits defined.

        Connector must expose ``pod`` resources with a ``has_resource_limits``
        boolean-string label.  Absence of the label is treated as *true*
        (limits present) to avoid false positives when the connector does not
        yet surface this information.
        """
        findings: list[dict[str, Any]] = []

        try:
            pods = await connector.list_resources("pod", env)
        except Exception as exc:
            logger.debug("k8s_resource_limits_check_skipped", error=str(exc))
            return []

        for pod in pods:
            labels = pod.labels or {}
            has_limits = self._is_truthy(labels.get("has_resource_limits", "true"))
            if not has_limits:
                findings.append(
                    self._make_finding(
                        severity="medium",
                        title=f"Missing resource limits: {pod.id}",
                        description=(
                            f"Pod '{pod.id}' has no CPU or memory resource limits defined. "
                            "Unbounded resource consumption can cause node-level denial-of-service."
                        ),
                        affected_resource=f"kubernetes:pod/{pod.id}",
                        remediation=(
                            "Add 'resources.limits.cpu' and 'resources.limits.memory' "
                            "to every container spec in the pod."
                        ),
                        metadata={"pod": pod.id, "check": "resource_limits"},
                    )
                )

        return findings

    # ------------------------------------------------------------------
    # Service-account checks
    # ------------------------------------------------------------------

    async def _check_service_accounts(
        self, connector: InfraConnector, env: Environment
    ) -> list[dict[str, Any]]:
        """Flag pods that use the default ServiceAccount with auto-mounted tokens.

        Connector must expose ``pod`` resources with labels:
            - ``service_account`` (str): Name of the pod's service account.
            - ``automount_sa_token`` (str): ``"true"`` / ``"false"``.
        """
        findings: list[dict[str, Any]] = []

        try:
            pods = await connector.list_resources("pod", env)
        except Exception as exc:
            logger.debug("k8s_service_account_check_skipped", error=str(exc))
            return []

        for pod in pods:
            labels = pod.labels or {}
            sa_name: str = labels.get("service_account", "default")
            automount: bool = self._is_truthy(labels.get("automount_sa_token", "true"))

            if sa_name == "default" and automount:
                findings.append(
                    self._make_finding(
                        severity="medium",
                        title=f"Default SA with automounted token: {pod.id}",
                        description=(
                            f"Pod '{pod.id}' uses the default ServiceAccount and has the "
                            "Kubernetes API token automatically mounted. This grants "
                            "unnecessary cluster API access to any process in the pod."
                        ),
                        affected_resource=f"kubernetes:pod/{pod.id}",
                        remediation=(
                            "Create a dedicated ServiceAccount for the workload, or set "
                            "'automountServiceAccountToken: false' if API access is not required."
                        ),
                        metadata={
                            "pod": pod.id,
                            "service_account": sa_name,
                            "automount_token": str(automount),
                        },
                    )
                )

        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_finding(
        *,
        severity: str,
        title: str,
        description: str,
        affected_resource: str,
        remediation: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a standardised security finding dict."""
        return {
            "finding_id": f"k8s-{uuid4().hex[:12]}",
            "scanner_type": ScannerType.K8S_SECURITY.value,
            "severity": severity,
            "title": title,
            "description": description,
            "affected_resource": affected_resource,
            "remediation": remediation,
            "metadata": metadata,
        }

    @staticmethod
    def _is_truthy(value: str) -> bool:
        """Return True if *value* is a string representation of a truthy boolean."""
        return str(value).lower() in ("true", "yes", "1")
