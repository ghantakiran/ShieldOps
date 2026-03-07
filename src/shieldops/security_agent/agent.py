"""SecurityAgent — orchestrates CVE scanning, secret detection, and cert monitoring."""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog

from shieldops.security_agent.cert_monitor import CertificateMonitor
from shieldops.security_agent.cve_scanner import CVEScanner
from shieldops.security_agent.models import (
    SecurityScanResult,
)
from shieldops.security_agent.secret_detector import SecretDetector

logger = structlog.get_logger(__name__)


class SecurityAgent:
    """Top-level orchestrator that runs all three security scanners."""

    def __init__(self) -> None:
        self.cve_scanner = CVEScanner()
        self.secret_detector = SecretDetector()
        self.cert_monitor = CertificateMonitor()
        # In-memory store keyed by scan_id for report retrieval.
        self._results: dict[str, SecurityScanResult] = {}

    # ------------------------------------------------------------------
    # Full scan
    # ------------------------------------------------------------------

    async def run_full_scan(
        self,
        namespace: str,
        images: list[str] | None = None,
        domains: list[str] | None = None,
        repo_path: str | None = None,
    ) -> SecurityScanResult:
        """Orchestrate CVE, secret, and certificate scans.

        Parameters
        ----------
        namespace:
            Kubernetes namespace for cluster-level scans.
        images:
            Explicit container image refs to scan. If empty, the scanner
            will enumerate images from pods in *namespace*.
        domains:
            Domain names whose TLS certificates should be checked.
        repo_path:
            Local filesystem path to a source repository for secret scanning.

        Returns
        -------
        SecurityScanResult
            Aggregated findings from all scanners.
        """
        scan_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        logger.info("security_agent.scan_start", scan_id=scan_id)

        # --- CVE scanning ---
        if images:
            all_vulns = []
            for img in images:
                vulns = await self.cve_scanner.scan_container_image(img, namespace=namespace)
                all_vulns.extend(vulns)
        else:
            all_vulns = await self.cve_scanner.scan_kubernetes_cluster(namespace)
        all_vulns = self.cve_scanner.prioritize_vulnerabilities(all_vulns)

        # --- Secret detection ---
        all_secrets = []
        if repo_path:
            all_secrets.extend(await self.secret_detector.scan_repository(repo_path))
        all_secrets.extend(await self.secret_detector.scan_kubernetes_configmaps(namespace))
        all_secrets.extend(await self.secret_detector.scan_environment_variables(namespace))

        # --- Certificate monitoring ---
        all_certs = []
        if domains:
            for domain in domains:
                cert_status = await self.cert_monitor.check_certificate(domain)
                all_certs.append(cert_status)
        k8s_certs = await self.cert_monitor.scan_kubernetes_secrets(namespace)
        all_certs.extend(k8s_certs)

        expiring = await self.cert_monitor.get_expiring_certificates(days_threshold=30)

        # --- Build result ---
        completed_at = datetime.utcnow()

        severity_counts: dict[str, int] = {}
        for v in all_vulns:
            key = v.severity.value
            severity_counts[key] = severity_counts.get(key, 0) + 1

        summary: dict[str, int | str] = {
            "total_vulnerabilities": len(all_vulns),
            "total_secrets": len(all_secrets),
            "total_certificates": len(all_certs),
            "expiring_certificates": len(expiring),
            **severity_counts,
        }

        result = SecurityScanResult(
            scan_id=scan_id,
            scan_type="full",
            started_at=started_at,
            completed_at=completed_at,
            vulnerabilities=all_vulns,
            secrets=all_secrets,
            certificates=all_certs,
            summary=summary,
        )

        self._results[scan_id] = result

        logger.info(
            "security_agent.scan_complete",
            scan_id=scan_id,
            vulns=len(all_vulns),
            secrets=len(all_secrets),
            certs=len(all_certs),
        )
        return result

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_security_report(self, result: SecurityScanResult) -> str:
        """Produce a Markdown security report from scan results."""
        lines: list[str] = [
            f"# Security Scan Report — {result.scan_id}",
            "",
            f"**Scan type:** {result.scan_type}  ",
            f"**Started:** {result.started_at.isoformat()}  ",
            f"**Completed:** {result.completed_at.isoformat() if result.completed_at else 'N/A'}  ",
            "",
            "## Summary",
            "",
        ]

        for key, value in result.summary.items():
            lines.append(f"- **{key}:** {value}")
        lines.append("")

        # --- Vulnerabilities ---
        lines.append("## Vulnerabilities")
        lines.append("")
        if result.vulnerabilities:
            lines.append("| CVE | Package | Installed | Fixed | Severity | CVSS |")
            lines.append("|-----|---------|-----------|-------|----------|------|")
            for v in result.vulnerabilities:
                fixed = v.fixed_version or "N/A"
                lines.append(
                    f"| {v.cve_id} | {v.package_name} | "
                    f"{v.installed_version} | {fixed} | "
                    f"{v.severity.value} | {v.cvss_score:.1f} |"
                )
        else:
            lines.append("No vulnerabilities found.")
        lines.append("")

        # --- Secrets ---
        lines.append("## Secret Findings")
        lines.append("")
        if result.secrets:
            lines.append("| Type | Location | Severity | Masked Snippet |")
            lines.append("|------|----------|----------|----------------|")
            for s in result.secrets:
                lines.append(
                    f"| {s.finding_type.value} | {s.location} | "
                    f"{s.severity.value} | "
                    f"`{s.snippet_masked[:60]}` |"
                )
        else:
            lines.append("No hardcoded secrets detected.")
        lines.append("")

        # --- Certificates ---
        lines.append("## Certificates")
        lines.append("")
        if result.certificates:
            lines.append("| Domain | Issuer | Expires | Days Left | Status |")
            lines.append("|--------|--------|---------|-----------|--------|")
            for c in result.certificates:
                expires = c.not_after.strftime("%Y-%m-%d") if c.not_after else "N/A"
                status = "EXPIRED" if c.is_expired else "valid"
                lines.append(
                    f"| {c.domain} | {c.issuer} | {expires} | {c.days_until_expiry} | {status} |"
                )
        else:
            lines.append("No certificates scanned.")
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_result(self, scan_id: str) -> SecurityScanResult | None:
        """Retrieve a cached scan result by ID."""
        return self._results.get(scan_id)

    async def close(self) -> None:
        """Release resources held by sub-scanners."""
        await self.cve_scanner.close()
