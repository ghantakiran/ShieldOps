"""CVE scanning via Grype (Anchore) for container images and Kubernetes pods."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import httpx
import structlog

from shieldops.security_agent.models import (
    VulnerabilityRecord,
    VulnerabilitySeverity,
    VulnerabilityStatus,
)

logger = structlog.get_logger(__name__)

# Maps grype severity strings to our enum.
_SEVERITY_MAP: dict[str, VulnerabilitySeverity] = {
    "Critical": VulnerabilitySeverity.CRITICAL,
    "High": VulnerabilitySeverity.HIGH,
    "Medium": VulnerabilitySeverity.MEDIUM,
    "Low": VulnerabilitySeverity.LOW,
    "Negligible": VulnerabilitySeverity.INFO,
    "Unknown": VulnerabilitySeverity.INFO,
}


class CVEScanner:
    """Scans container images for known CVEs using the Grype CLI."""

    def __init__(self, grype_path: str = "grype") -> None:
        self._grype = grype_path
        self._http = httpx.AsyncClient(timeout=30.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scan_container_image(
        self, image: str, namespace: str = ""
    ) -> list[VulnerabilityRecord]:
        """Run ``grype`` against *image* and return parsed findings.

        The scan shells out to the Grype CLI with JSON output, then maps
        each match to a :class:`VulnerabilityRecord`.
        """
        logger.info("cve_scan.start", image=image, namespace=namespace)
        try:
            proc = await asyncio.create_subprocess_exec(
                self._grype,
                image,
                "-o",
                "json",
                "--quiet",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode not in (0, 1):
                # grype returns 1 when vulnerabilities are found
                logger.error(
                    "cve_scan.grype_error",
                    image=image,
                    returncode=proc.returncode,
                    stderr=stderr.decode(errors="replace")[:500],
                )
                return []

            return self._parse_grype_output(stdout.decode(), image=image, namespace=namespace)
        except FileNotFoundError:
            logger.error(
                "cve_scan.grype_not_found",
                hint="Install grype: https://github.com/anchore/grype",
            )
            return []
        except Exception:
            logger.exception("cve_scan.unexpected_error", image=image)
            return []

    async def scan_kubernetes_cluster(self, namespace: str) -> list[VulnerabilityRecord]:
        """Iterate pods in *namespace*, extract unique images, and scan each.

        Requires ``kubectl`` access to the target cluster.
        """
        logger.info("cve_scan.k8s_start", namespace=namespace)
        images = await self._list_pod_images(namespace)
        if not images:
            logger.warning("cve_scan.no_images", namespace=namespace)
            return []

        all_vulns: list[VulnerabilityRecord] = []
        for img in images:
            vulns = await self.scan_container_image(img, namespace=namespace)
            all_vulns.extend(vulns)

        logger.info(
            "cve_scan.k8s_complete",
            namespace=namespace,
            images_scanned=len(images),
            total_vulns=len(all_vulns),
        )
        return all_vulns

    async def get_fix_recommendations(self, vuln: VulnerabilityRecord) -> dict[str, str]:
        """Return remediation steps for a single vulnerability."""
        steps: dict[str, str] = {
            "cve_id": vuln.cve_id,
            "package": vuln.package_name,
            "current_version": vuln.installed_version,
        }

        if vuln.fixed_version:
            steps["action"] = (
                f"Upgrade {vuln.package_name} from {vuln.installed_version} to {vuln.fixed_version}"
            )
            steps["priority"] = (
                "immediate"
                if vuln.severity
                in (
                    VulnerabilitySeverity.CRITICAL,
                    VulnerabilitySeverity.HIGH,
                )
                else "scheduled"
            )
        else:
            steps["action"] = (
                f"No fix available for {vuln.cve_id}. Apply compensating controls or WAF rules."
            )
            steps["priority"] = "monitor"

        return steps

    def prioritize_vulnerabilities(
        self, vulns: list[VulnerabilityRecord]
    ) -> list[VulnerabilityRecord]:
        """Sort vulnerabilities by CVSS score descending, then severity."""
        severity_order = {
            VulnerabilitySeverity.CRITICAL: 0,
            VulnerabilitySeverity.HIGH: 1,
            VulnerabilitySeverity.MEDIUM: 2,
            VulnerabilitySeverity.LOW: 3,
            VulnerabilitySeverity.INFO: 4,
        }
        return sorted(
            vulns,
            key=lambda v: (-v.cvss_score, severity_order.get(v.severity, 5)),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_grype_output(
        self, raw: str, *, image: str, namespace: str
    ) -> list[VulnerabilityRecord]:
        """Parse Grype JSON output into VulnerabilityRecord list."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("cve_scan.json_parse_error", image=image)
            return []

        matches: list[dict[str, Any]] = data.get("matches", [])
        records: list[VulnerabilityRecord] = []

        for match in matches:
            vuln_data = match.get("vulnerability", {})
            artifact = match.get("artifact", {})
            fix_versions = vuln_data.get("fix", {}).get("versions", [])

            severity_str = vuln_data.get("severity", "Unknown")
            severity = _SEVERITY_MAP.get(severity_str, VulnerabilitySeverity.INFO)

            cvss_entries = vuln_data.get("cvss", [])
            cvss_score = 0.0
            if cvss_entries:
                metrics = cvss_entries[0].get("metrics", {})
                cvss_score = float(metrics.get("baseScore", 0.0))

            records.append(
                VulnerabilityRecord(
                    cve_id=vuln_data.get("id", "UNKNOWN"),
                    package_name=artifact.get("name", "unknown"),
                    installed_version=artifact.get("version", "unknown"),
                    fixed_version=fix_versions[0] if fix_versions else None,
                    severity=severity,
                    description=vuln_data.get("description", ""),
                    cvss_score=cvss_score,
                    affected_service=image,
                    namespace=namespace,
                    detected_at=datetime.utcnow(),
                    status=VulnerabilityStatus.OPEN,
                )
            )

        logger.info(
            "cve_scan.parsed",
            image=image,
            total_matches=len(records),
        )
        return records

    async def _list_pod_images(self, namespace: str) -> list[str]:
        """Use ``kubectl`` to extract unique container images in a namespace."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "kubectl",
                "get",
                "pods",
                "-n",
                namespace,
                "-o",
                "jsonpath={.items[*].spec.containers[*].image}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            raw = stdout.decode().strip()
            if not raw:
                return []
            return list(set(raw.split()))
        except FileNotFoundError:
            logger.error("cve_scan.kubectl_not_found")
            return []
        except Exception:
            logger.exception("cve_scan.list_images_error", namespace=namespace)
            return []

    async def close(self) -> None:
        """Clean up the HTTP client."""
        await self._http.aclose()
