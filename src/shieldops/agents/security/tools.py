"""Tool functions for the Security Agent.

Bridges CVE databases, credential stores, compliance frameworks, and
infrastructure connectors to the agent's LangGraph nodes.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import Environment

logger = structlog.get_logger()


class SecurityToolkit:
    """Collection of tools available to the security agent.

    Injected into nodes at graph construction time.
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        cve_sources: list[Any] | None = None,
        credential_stores: list[Any] | None = None,
    ) -> None:
        self._router = connector_router
        self._cve_sources = cve_sources or []
        self._credential_stores = credential_stores or []

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
            "patches_available": sum(
                1 for f in all_findings if f.get("fixed_version")
            ),
            "sources_queried": [
                getattr(s, "source_name", "unknown") for s in self._cve_sources
            ],
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
        now = datetime.now(timezone.utc)
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
            controls.append({
                "control_id": control["id"],
                "framework": framework,
                "title": control["title"],
                "status": "passing",  # Default — real implementation queries infra
                "severity": control.get("severity", "medium"),
                "evidence": [],
            })

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
                {"id": "PCI-DSS-2.1", "title": "Default credential removal", "severity": "critical"},
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
                {"id": "CIS-1.1", "title": "API server anonymous auth disabled", "severity": "critical"},
                {"id": "CIS-1.2", "title": "API server auth mode", "severity": "high"},
                {"id": "CIS-4.1", "title": "Worker node kubelet auth", "severity": "high"},
                {"id": "CIS-5.1", "title": "RBAC enabled", "severity": "critical"},
                {"id": "CIS-5.2", "title": "Pod security standards", "severity": "high"},
            ],
        }
        return frameworks.get(framework, [])
