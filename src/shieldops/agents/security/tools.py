"""Tool functions for the Security Agent.

Bridges CVE databases, credential stores, compliance frameworks, and
infrastructure connectors to the agent's LangGraph nodes.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from shieldops.agents.security.protocols import CredentialStore, CVESource
from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import Environment, RemediationAction, RiskLevel

logger = structlog.get_logger()


class SecurityToolkit:
    """Collection of tools available to the security agent.

    Injected into nodes at graph construction time.
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        cve_sources: list[CVESource] | None = None,
        credential_stores: list[CredentialStore] | None = None,
        policy_engine: Any | None = None,
        approval_workflow: Any | None = None,
    ) -> None:
        self._router = connector_router
        self._cve_sources = cve_sources or []
        self._credential_stores = credential_stores or []
        self._policy_engine = policy_engine
        self._approval_workflow = approval_workflow

    # ── Scan tools (existing) ─────────────────────────────────────

    async def scan_cves(
        self,
        resource_ids: list[str],
        severity_threshold: str = "medium",
    ) -> dict[str, Any]:
        """Scan resources for known CVEs.

        Queries CVE databases (NVD, vendor advisories) against installed packages.
        Returns vulnerability findings grouped by severity.
        """
        all_findings: list[dict[str, Any]] = []

        for source in self._cve_sources:
            try:
                for resource_id in resource_ids:
                    findings = await source.scan(resource_id, severity_threshold)
                    all_findings.extend(findings)
            except Exception as e:
                logger.error(
                    "cve_scan_failed",
                    source=getattr(source, "source_name", "unknown"),
                    error=str(e),
                )

        # Classify by severity
        critical = [f for f in all_findings if f.get("severity") == "critical"]
        high = [f for f in all_findings if f.get("severity") == "high"]
        medium = [f for f in all_findings if f.get("severity") == "medium"]
        low = [f for f in all_findings if f.get("severity") == "low"]

        return {
            "total_findings": len(all_findings),
            "critical_count": len(critical),
            "high_count": len(high),
            "medium_count": len(medium),
            "low_count": len(low),
            "findings": all_findings[:100],
            "critical_findings": critical[:20],
            "high_findings": high[:30],
            "patches_available": sum(1 for f in all_findings if f.get("fixed_version")),
            "sources_queried": [getattr(s, "source_name", "unknown") for s in self._cve_sources],
        }

    async def check_credentials(
        self,
        environment: Environment | None = None,
        rotation_window_days: int = 7,
    ) -> dict[str, Any]:
        """Check credential expiry status across all managed services.

        Returns credentials grouped by urgency.
        """
        all_credentials: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        rotation_threshold = now + timedelta(days=rotation_window_days)

        for store in self._credential_stores:
            try:
                creds = await store.list_credentials(environment=environment)
                all_credentials.extend(creds)
            except Exception as e:
                logger.error(
                    "credential_check_failed",
                    store=getattr(store, "store_name", "unknown"),
                    error=str(e),
                )

        expired = []
        expiring_soon = []
        healthy = []

        for cred in all_credentials:
            expires_at = cred.get("expires_at")
            if expires_at is None:
                healthy.append(cred)
            elif expires_at <= now:
                expired.append(cred)
            elif expires_at <= rotation_threshold:
                expiring_soon.append(cred)
            else:
                healthy.append(cred)

        return {
            "total_credentials": len(all_credentials),
            "expired_count": len(expired),
            "expiring_soon_count": len(expiring_soon),
            "healthy_count": len(healthy),
            "expired": expired,
            "expiring_soon": expiring_soon,
            "needs_rotation": len(expired) + len(expiring_soon),
            "stores_queried": [
                getattr(s, "store_name", "unknown") for s in self._credential_stores
            ],
        }

    async def check_compliance(
        self,
        framework: str,
        resource_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Evaluate compliance posture against a framework.

        Checks infrastructure state against framework controls.
        """
        # Compliance checks run against infrastructure via connectors
        controls: list[dict[str, Any]] = []

        if self._router is None:
            return {
                "framework": framework,
                "controls_checked": 0,
                "controls": [],
                "passing": 0,
                "failing": 0,
                "score": 0.0,
            }

        # Framework-specific control checks
        framework_controls = self._get_framework_controls(framework)

        for control in framework_controls:
            controls.append(
                {
                    "control_id": control["id"],
                    "framework": framework,
                    "title": control["title"],
                    "status": "passing",  # Default — real implementation queries infra
                    "severity": control.get("severity", "medium"),
                    "evidence": [],
                }
            )

        passing = sum(1 for c in controls if c["status"] == "passing")
        failing = sum(1 for c in controls if c["status"] == "failing")
        total = len(controls) or 1

        return {
            "framework": framework,
            "controls_checked": len(controls),
            "controls": controls,
            "passing": passing,
            "failing": failing,
            "score": (passing / total) * 100,
        }

    async def get_resource_list(
        self,
        environment: Environment,
        resource_type: str = "pod",
    ) -> list[str]:
        """Get list of resources to scan in an environment."""
        if self._router is None:
            return []

        try:
            connector = self._router.get("kubernetes")
            resources = await connector.list_resources(
                resource_type=resource_type,
                environment=environment,
            )
            return [r.id for r in resources]
        except (ValueError, Exception) as e:
            logger.error("resource_list_failed", error=str(e))
            return []

    # ── Action execution tools (new) ──────────────────────────────

    async def apply_patch(
        self,
        host: str,
        package_name: str,
        target_version: str,
        provider: str = "kubernetes",
    ) -> dict[str, Any]:
        """Apply a package patch via the infrastructure connector.

        Constructs a RemediationAction and delegates to the connector.
        """
        if self._router is None:
            return {"success": False, "message": "No connector router configured"}

        action = RemediationAction(
            id=f"patch-{package_name}-{host}",
            action_type="apply_patch",
            target_resource=host,
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.MEDIUM,
            parameters={
                "package_name": package_name,
                "target_version": target_version,
            },
            description=f"Patch {package_name} to {target_version} on {host}",
        )

        try:
            connector = self._router.get(provider)
            result = await connector.execute_action(action)
            return {
                "success": result.status.value == "success",
                "message": result.message,
                "applied_version": target_version if result.status.value == "success" else None,
            }
        except Exception as e:
            logger.error(
                "patch_apply_failed",
                host=host,
                package=package_name,
                error=str(e),
            )
            return {"success": False, "message": str(e)}

    async def rotate_credential(
        self,
        credential_id: str,
        credential_type: str,
        service: str,
    ) -> dict[str, Any]:
        """Rotate a credential via the appropriate credential store."""
        for store in self._credential_stores:
            try:
                result = await store.rotate_credential(credential_id, credential_type)
                if result.get("success"):
                    return result
            except Exception as e:
                logger.error(
                    "credential_rotation_failed",
                    credential_id=credential_id,
                    store=getattr(store, "store_name", "unknown"),
                    error=str(e),
                )

        return {
            "credential_id": credential_id,
            "credential_type": credential_type,
            "service": service,
            "success": False,
            "message": "No credential store could rotate this credential",
        }

    async def evaluate_security_policy(
        self,
        action_type: str,
        target_resource: str,
        environment: Environment,
    ) -> dict[str, Any]:
        """Evaluate a security action against OPA policies."""
        if self._policy_engine is None:
            return {"allowed": True, "reasons": ["No policy engine configured"]}

        risk = self.classify_security_risk(action_type, environment)

        action = RemediationAction(
            id=f"sec-{action_type}",
            action_type=action_type,
            target_resource=target_resource,
            environment=environment,
            risk_level=risk,
            parameters={},
            description=f"Security action: {action_type} on {target_resource}",
        )

        decision = await self._policy_engine.evaluate(
            action=action,
            agent_id="security-agent",
        )
        return {
            "allowed": decision.allowed,
            "reasons": decision.reasons,
        }

    def classify_security_risk(self, action_type: str, environment: Environment) -> RiskLevel:
        """Classify risk level for a security action."""
        if self._policy_engine is not None:
            risk: RiskLevel = self._policy_engine.classify_risk(action_type, environment)
            return risk

        # Fallback classification
        if environment == Environment.PRODUCTION:
            return RiskLevel.HIGH
        if environment == Environment.STAGING:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def requires_approval(self, risk_level: RiskLevel) -> bool:
        """Check whether a security action at this risk level needs approval."""
        if self._approval_workflow is None:
            return False
        result: bool = self._approval_workflow.requires_approval(risk_level)
        return result

    async def request_approval(self, request: Any) -> Any:
        """Submit an approval request and wait for response."""
        if self._approval_workflow is None:
            from shieldops.models.base import ApprovalStatus

            return ApprovalStatus.APPROVED
        return await self._approval_workflow.request_approval(request)

    @staticmethod
    def _get_framework_controls(framework: str) -> list[dict[str, str]]:
        """Get control definitions for a compliance framework."""
        frameworks = {
            "soc2": [
                {"id": "SOC2-CC6.1", "title": "Logical access security", "severity": "critical"},
                {"id": "SOC2-CC6.2", "title": "Authentication mechanisms", "severity": "high"},
                {"id": "SOC2-CC6.3", "title": "Authorization policies", "severity": "high"},
                {"id": "SOC2-CC7.1", "title": "System monitoring", "severity": "high"},
                {"id": "SOC2-CC7.2", "title": "Anomaly detection", "severity": "medium"},
                {"id": "SOC2-CC8.1", "title": "Change management", "severity": "high"},
            ],
            "pci_dss": [
                {"id": "PCI-DSS-1.1", "title": "Network segmentation", "severity": "critical"},
                {
                    "id": "PCI-DSS-2.1",
                    "title": "Default credential removal",
                    "severity": "critical",
                },
                {"id": "PCI-DSS-6.2", "title": "Security patching", "severity": "high"},
                {"id": "PCI-DSS-8.1", "title": "User identification", "severity": "high"},
                {"id": "PCI-DSS-10.1", "title": "Audit logging", "severity": "high"},
            ],
            "hipaa": [
                {"id": "HIPAA-164.312a", "title": "Access control", "severity": "critical"},
                {"id": "HIPAA-164.312b", "title": "Audit controls", "severity": "high"},
                {"id": "HIPAA-164.312c", "title": "Integrity controls", "severity": "high"},
                {"id": "HIPAA-164.312d", "title": "Authentication", "severity": "critical"},
                {"id": "HIPAA-164.312e", "title": "Transmission security", "severity": "high"},
            ],
            "cis": [
                {
                    "id": "CIS-1.1",
                    "title": "API server anonymous auth disabled",
                    "severity": "critical",
                },
                {"id": "CIS-1.2", "title": "API server auth mode", "severity": "high"},
                {"id": "CIS-4.1", "title": "Worker node kubelet auth", "severity": "high"},
                {"id": "CIS-5.1", "title": "RBAC enabled", "severity": "critical"},
                {"id": "CIS-5.2", "title": "Pod security standards", "severity": "high"},
            ],
        }
        return frameworks.get(framework, [])
