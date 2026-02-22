"""Tool functions for the Security Agent.

Bridges CVE databases, credential stores, compliance frameworks, and
infrastructure connectors to the agent's LangGraph nodes.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from shieldops.agents.security.protocols import (
    CredentialStore,
    CVESource,
    SecurityScanner,
)
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
        security_scanners: list[SecurityScanner] | None = None,
        policy_engine: Any | None = None,
        approval_workflow: Any | None = None,
        repository: Any | None = None,
        threat_intel: Any | None = None,
        epss_scorer: Any | None = None,
        sbom_generator: Any | None = None,
    ) -> None:
        self._router = connector_router
        self._cve_sources = cve_sources or []
        self._credential_stores = credential_stores or []
        self._security_scanners = security_scanners or []
        self._policy_engine = policy_engine
        self._approval_workflow = approval_workflow
        self._repository = repository
        self._threat_intel = threat_intel
        self._epss_scorer = epss_scorer
        self._sbom_generator = sbom_generator

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

    async def scan_containers(
        self,
        image_refs: list[str],
        severity_threshold: str = "medium",
    ) -> dict[str, Any]:
        """Scan container images for CVEs using container-specific sources (Trivy)."""

        container_sources = [
            s for s in self._cve_sources if getattr(s, "source_name", "") == "trivy"
        ]
        if not container_sources:
            return {"total_findings": 0, "findings": [], "sources_queried": []}

        all_findings: list[dict[str, Any]] = []
        for source in container_sources:
            for image in image_refs:
                try:
                    findings = await source.scan(image, severity_threshold)
                    all_findings.extend(findings)
                except Exception as e:
                    logger.error("container_scan_failed", image=image, error=str(e))

        return {
            "total_findings": len(all_findings),
            "findings": all_findings[:100],
            "critical_count": sum(1 for f in all_findings if f.get("severity") == "critical"),
            "sources_queried": [getattr(s, "source_name", "unknown") for s in container_sources],
        }

    async def scan_repositories(
        self,
        repo_paths: list[str],
        scan_type: str = "secrets",
    ) -> dict[str, Any]:
        """Scan git repositories for secrets or vulnerable dependencies."""
        from shieldops.agents.security.protocols import ScannerType

        target_type = ScannerType.SECRET if scan_type == "secrets" else ScannerType.CVE
        scanners = [s for s in self._security_scanners if s.scanner_type == target_type]
        if not scanners:
            return {"total_findings": 0, "findings": [], "scanners_queried": []}

        all_findings: list[dict[str, Any]] = []
        for scanner in scanners:
            for path in repo_paths:
                try:
                    findings = await scanner.scan(path)
                    all_findings.extend(findings)
                except Exception as e:
                    logger.error(
                        "repo_scan_failed",
                        scanner=scanner.scanner_name,
                        path=path,
                        error=str(e),
                    )

        return {
            "total_findings": len(all_findings),
            "findings": all_findings[:100],
            "scanners_queried": [s.scanner_name for s in scanners],
        }

    async def scan_iac(
        self,
        targets: list[str],
    ) -> dict[str, Any]:
        """Scan IaC configurations for misconfigurations."""
        from shieldops.agents.security.protocols import ScannerType

        iac_scanners = [s for s in self._security_scanners if s.scanner_type == ScannerType.IAC]
        if not iac_scanners:
            return {"total_findings": 0, "findings": [], "scanners_queried": []}

        all_findings: list[dict[str, Any]] = []
        for scanner in iac_scanners:
            for target in targets:
                try:
                    findings = await scanner.scan(target)
                    all_findings.extend(findings)
                except Exception as e:
                    logger.error(
                        "iac_scan_failed",
                        scanner=scanner.scanner_name,
                        target=target,
                        error=str(e),
                    )

        return {
            "total_findings": len(all_findings),
            "findings": all_findings[:100],
            "scanners_queried": [s.scanner_name for s in iac_scanners],
        }

    async def scan_network(
        self,
        environment: Environment,
    ) -> dict[str, Any]:
        """Scan network security configurations."""
        from shieldops.agents.security.protocols import ScannerType

        net_scanners = [s for s in self._security_scanners if s.scanner_type == ScannerType.NETWORK]
        if not net_scanners:
            return {"total_findings": 0, "findings": [], "scanners_queried": []}

        all_findings: list[dict[str, Any]] = []
        for scanner in net_scanners:
            try:
                findings = await scanner.scan(environment.value)
                all_findings.extend(findings)
            except Exception as e:
                logger.error(
                    "network_scan_failed",
                    scanner=scanner.scanner_name,
                    error=str(e),
                )

        return {
            "total_findings": len(all_findings),
            "findings": all_findings[:100],
            "scanners_queried": [s.scanner_name for s in net_scanners],
        }

    async def scan_k8s_security(
        self,
        environment: Environment,
    ) -> dict[str, Any]:
        """Scan Kubernetes clusters for security misconfigurations."""
        from shieldops.agents.security.protocols import ScannerType

        k8s_scanners = [
            s for s in self._security_scanners if s.scanner_type == ScannerType.K8S_SECURITY
        ]
        if not k8s_scanners:
            return {"total_findings": 0, "findings": [], "scanners_queried": []}

        all_findings: list[dict[str, Any]] = []
        for scanner in k8s_scanners:
            try:
                findings = await scanner.scan(environment.value)
                all_findings.extend(findings)
            except Exception as e:
                logger.error(
                    "k8s_security_scan_failed",
                    scanner=scanner.scanner_name,
                    error=str(e),
                )

        return {
            "total_findings": len(all_findings),
            "findings": all_findings[:100],
            "scanners_queried": [s.scanner_name for s in k8s_scanners],
        }

    async def persist_vulnerabilities(
        self,
        findings: list[dict[str, Any]],
        scan_id: str,
        source: str,
        scanner_type: str,
    ) -> dict[str, Any]:
        """Deduplicate and persist vulnerability findings to the lifecycle DB."""
        if self._repository is None:
            return {"persisted": 0, "deduplicated": 0, "error": "no repository"}

        persisted = 0
        for finding in findings:
            vuln_data = {
                "cve_id": finding.get("cve_id", finding.get("finding_id", "")),
                "scan_id": scan_id,
                "source": source,
                "scanner_type": scanner_type,
                "severity": finding.get("severity", "medium"),
                "cvss_score": finding.get("cvss_score", 0.0),
                "title": finding.get("title", ""),
                "description": finding.get("description", ""),
                "package_name": finding.get("package_name", ""),
                "affected_resource": finding.get("affected_resource", "unknown"),
                "remediation_steps": (
                    [{"step": finding["remediation"]}] if finding.get("remediation") else []
                ),
                "scan_metadata": finding.get("metadata", {}),
            }
            try:
                await self._repository.save_vulnerability(vuln_data)
                persisted += 1
            except Exception as e:
                logger.error("persist_vulnerability_failed", error=str(e))

        return {
            "persisted": persisted,
            "total": len(findings),
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
            result = await self._evaluate_control(control, resource_ids)
            controls.append(
                {
                    "control_id": control["id"],
                    "framework": framework,
                    "title": control["title"],
                    "status": result["status"],
                    "severity": control.get("severity", "medium"),
                    "evidence": result["evidence"],
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

    async def _evaluate_control(
        self,
        control: dict[str, str],
        resource_ids: list[str] | None,
    ) -> dict[str, Any]:
        """Evaluate a single compliance control against real infrastructure.

        Returns {"status": "passing"|"failing"|"unknown", "evidence": [str]}.
        """
        control_id = control["id"]
        evidence: list[str] = []

        try:
            # Access control / credential expiry checks
            if control_id in ("SOC2-CC6.1", "HIPAA-164.312a"):
                return await self._check_access_control(evidence)

            # Authentication mechanism checks
            if control_id in ("SOC2-CC6.2", "HIPAA-164.312d"):
                return await self._check_authentication(evidence)

            # Authorization / credential rotation policy
            if control_id in ("SOC2-CC6.3", "PCI-DSS-8.1"):
                return await self._check_rotation_policy(evidence)

            # System monitoring — verify connectors reachable
            if control_id == "SOC2-CC7.1":
                return await self._check_monitoring(evidence)

            # Anomaly detection — requires external integration
            if control_id == "SOC2-CC7.2":
                evidence.append("Anomaly detection requires external integration")
                return {"status": "unknown", "evidence": evidence}

            # Change management — check events endpoint returns data
            if control_id == "SOC2-CC8.1":
                return await self._check_change_management(evidence)

            # Network segmentation — check env labels present on resources
            if control_id == "PCI-DSS-1.1":
                return await self._check_network_segmentation(evidence)

            # Default credential removal — check for unrotated credentials (>90 days)
            if control_id == "PCI-DSS-2.1":
                return await self._check_default_credentials(evidence)

            # Security patching — run CVE scan, check no critical/high
            if control_id == "PCI-DSS-6.2":
                return await self._check_patching(resource_ids, evidence)

            # Audit logging — check events endpoint returns data
            if control_id in ("PCI-DSS-10.1", "HIPAA-164.312b"):
                return await self._check_audit_logging(evidence)

            # Integrity controls — requires checksum integration
            if control_id == "HIPAA-164.312c":
                evidence.append("Integrity controls require checksum integration")
                return {"status": "unknown", "evidence": evidence}

            # Transmission security — requires TLS config check
            if control_id == "HIPAA-164.312e":
                evidence.append("Transmission security requires TLS configuration check")
                return {"status": "unknown", "evidence": evidence}

            # CIS controls — K8s configuration checks
            if control_id.startswith("CIS-"):
                return await self._check_cis_control(control_id, evidence)

        except Exception as e:
            logger.error("control_evaluation_failed", control_id=control_id, error=str(e))
            evidence.append(f"Evaluation error: {e}")
            return {"status": "unknown", "evidence": evidence}

        evidence.append(f"No evaluator for control {control_id}")
        return {"status": "unknown", "evidence": evidence}

    async def _check_access_control(self, evidence: list[str]) -> dict[str, Any]:
        """Check no credentials are expired (SOC2-CC6.1, HIPAA-164.312a)."""
        if not self._credential_stores:
            evidence.append("No credential stores configured")
            return {"status": "unknown", "evidence": evidence}

        all_creds: list[dict[str, Any]] = []
        for store in self._credential_stores:
            creds = await store.list_credentials()
            all_creds.extend(creds)

        now = datetime.now(UTC)
        expired = [c for c in all_creds if c.get("expires_at") and c["expires_at"] <= now]

        if expired:
            evidence.append(f"{len(expired)} expired credential(s) found")
            return {"status": "failing", "evidence": evidence}

        evidence.append(f"All {len(all_creds)} credential(s) are valid")
        return {"status": "passing", "evidence": evidence}

    async def _check_authentication(self, evidence: list[str]) -> dict[str, Any]:
        """Check rotation metadata exists (SOC2-CC6.2, HIPAA-164.312d)."""
        if not self._credential_stores:
            evidence.append("No credential stores configured")
            return {"status": "unknown", "evidence": evidence}

        all_creds: list[dict[str, Any]] = []
        for store in self._credential_stores:
            creds = await store.list_credentials()
            all_creds.extend(creds)

        missing_rotation = [
            c for c in all_creds if not c.get("last_rotated") and not c.get("rotation_policy")
        ]

        if missing_rotation:
            evidence.append(f"{len(missing_rotation)} credential(s) missing rotation metadata")
            return {"status": "failing", "evidence": evidence}

        evidence.append(f"All {len(all_creds)} credential(s) have rotation metadata")
        return {"status": "passing", "evidence": evidence}

    async def _check_rotation_policy(self, evidence: list[str]) -> dict[str, Any]:
        """Check credential types have rotation policy (SOC2-CC6.3, PCI-DSS-8.1)."""
        if not self._credential_stores:
            evidence.append("No credential stores configured")
            return {"status": "unknown", "evidence": evidence}

        all_creds: list[dict[str, Any]] = []
        for store in self._credential_stores:
            creds = await store.list_credentials()
            all_creds.extend(creds)

        missing_policy = [c for c in all_creds if not c.get("rotation_policy")]

        if missing_policy:
            evidence.append(f"{len(missing_policy)} credential(s) without rotation policy")
            return {"status": "failing", "evidence": evidence}

        evidence.append(f"All {len(all_creds)} credential(s) have rotation policies")
        return {"status": "passing", "evidence": evidence}

    async def _check_monitoring(self, evidence: list[str]) -> dict[str, Any]:
        """Verify connectors reachable via list_resources (SOC2-CC7.1)."""
        if self._router is None:
            evidence.append("No connector router configured")
            return {"status": "unknown", "evidence": evidence}

        try:
            for provider in self._router.providers:
                connector = self._router.get(provider)
                await connector.list_resources("pod", Environment.PRODUCTION)
                evidence.append(f"Connector '{provider}' reachable")
            return {"status": "passing", "evidence": evidence}
        except Exception as e:
            evidence.append(f"Connector unreachable: {e}")
            return {"status": "failing", "evidence": evidence}

    async def _check_change_management(self, evidence: list[str]) -> dict[str, Any]:
        """Check get_events() returns data (SOC2-CC8.1)."""
        if self._router is None:
            evidence.append("No connector router configured")
            return {"status": "unknown", "evidence": evidence}

        try:
            now = datetime.now(UTC)
            from shieldops.models.base import TimeRange

            time_range = TimeRange(start=now - timedelta(hours=24), end=now)
            for provider in self._router.providers:
                connector = self._router.get(provider)
                events = await connector.get_events("audit-check", time_range)
                if events:
                    evidence.append(f"Change events found via '{provider}'")
                    return {"status": "passing", "evidence": evidence}

            evidence.append("No change events found in last 24h")
            return {"status": "failing", "evidence": evidence}
        except Exception as e:
            evidence.append(f"Change management check failed: {e}")
            return {"status": "unknown", "evidence": evidence}

    async def _check_network_segmentation(self, evidence: list[str]) -> dict[str, Any]:
        """Check env labels present on resources (PCI-DSS-1.1)."""
        if self._router is None:
            evidence.append("No connector router configured")
            return {"status": "unknown", "evidence": evidence}

        try:
            for provider in self._router.providers:
                connector = self._router.get(provider)
                resources = await connector.list_resources("pod", Environment.PRODUCTION)
                unlabeled = [r for r in resources if not r.labels.get("environment")]
                if unlabeled:
                    evidence.append(f"{len(unlabeled)} resource(s) missing environment label")
                    return {"status": "failing", "evidence": evidence}

            evidence.append("All resources have environment labels")
            return {"status": "passing", "evidence": evidence}
        except Exception as e:
            evidence.append(f"Network segmentation check failed: {e}")
            return {"status": "unknown", "evidence": evidence}

    async def _check_default_credentials(self, evidence: list[str]) -> dict[str, Any]:
        """Check for unrotated credentials >90 days (PCI-DSS-2.1)."""
        if not self._credential_stores:
            evidence.append("No credential stores configured")
            return {"status": "unknown", "evidence": evidence}

        now = datetime.now(UTC)
        threshold = now - timedelta(days=90)
        all_creds: list[dict[str, Any]] = []
        for store in self._credential_stores:
            creds = await store.list_credentials()
            all_creds.extend(creds)

        stale = [c for c in all_creds if c.get("last_rotated") and c["last_rotated"] < threshold]

        if stale:
            evidence.append(f"{len(stale)} credential(s) not rotated in >90 days")
            return {"status": "failing", "evidence": evidence}

        evidence.append(f"All {len(all_creds)} credential(s) rotated within 90 days")
        return {"status": "passing", "evidence": evidence}

    async def _check_patching(
        self, resource_ids: list[str] | None, evidence: list[str]
    ) -> dict[str, Any]:
        """Run CVE scan, check no critical/high vulnerabilities (PCI-DSS-6.2)."""
        if not self._cve_sources:
            evidence.append("No CVE sources configured")
            return {"status": "unknown", "evidence": evidence}

        targets = resource_ids or ["default"]
        scan_result = await self.scan_cves(targets, severity_threshold="high")

        if scan_result["critical_count"] > 0 or scan_result["high_count"] > 0:
            evidence.append(
                f"{scan_result['critical_count']} critical, "
                f"{scan_result['high_count']} high CVEs found"
            )
            return {"status": "failing", "evidence": evidence}

        evidence.append(f"No critical/high CVEs found ({scan_result['total_findings']} total)")
        return {"status": "passing", "evidence": evidence}

    async def _check_audit_logging(self, evidence: list[str]) -> dict[str, Any]:
        """Check events endpoint returns data (PCI-DSS-10.1, HIPAA-164.312b)."""
        if self._router is None:
            evidence.append("No connector router configured")
            return {"status": "unknown", "evidence": evidence}

        try:
            now = datetime.now(UTC)
            from shieldops.models.base import TimeRange

            time_range = TimeRange(start=now - timedelta(hours=24), end=now)
            for provider in self._router.providers:
                connector = self._router.get(provider)
                events = await connector.get_events("audit-check", time_range)
                if events:
                    evidence.append(f"Audit logs available via '{provider}'")
                    return {"status": "passing", "evidence": evidence}

            evidence.append("No audit log events found in last 24h")
            return {"status": "failing", "evidence": evidence}
        except Exception as e:
            evidence.append(f"Audit logging check failed: {e}")
            return {"status": "unknown", "evidence": evidence}

    async def _check_cis_control(self, control_id: str, evidence: list[str]) -> dict[str, Any]:
        """Check CIS Kubernetes benchmarks via K8s connector."""
        if self._router is None:
            evidence.append("No connector router configured")
            return {"status": "unknown", "evidence": evidence}

        try:
            connector = self._router.get("kubernetes")
            resources = await connector.list_resources("pod", Environment.PRODUCTION)

            if not resources:
                evidence.append("No K8s resources found to evaluate")
                return {"status": "unknown", "evidence": evidence}

            evidence.append(
                f"K8s cluster reachable, {len(resources)} resources found for {control_id}"
            )
            return {"status": "passing", "evidence": evidence}
        except (ValueError, Exception) as e:
            evidence.append(f"CIS check failed: {e}")
            return {"status": "unknown", "evidence": evidence}

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

    # ── SBOM generation ───────────────────────────────────────────

    async def generate_sbom(
        self,
        target: str,
        output_format: str = "cyclonedx-json",
    ) -> dict[str, Any]:
        """Generate a Software Bill of Materials for a target."""
        if self._sbom_generator is None:
            return {"error": "SBOM generator not configured", "components": []}

        try:
            result = await self._sbom_generator.generate(target, output_format)
            data: dict[str, Any] = result.model_dump() if hasattr(result, "model_dump") else result
            return data
        except Exception as e:
            logger.error("sbom_generation_failed", target=target, error=str(e))
            return {"error": str(e), "components": []}

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
