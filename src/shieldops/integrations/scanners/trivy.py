"""Trivy container image vulnerability scanner integration.

Wraps the Trivy CLI/server API for scanning container images for CVEs.
Supports both local CLI execution and remote Trivy server mode.
"""

import asyncio
import json
from datetime import datetime
from typing import Any

import structlog

from shieldops.agents.security.protocols import CVESource

logger = structlog.get_logger()

# Maps Trivy severity labels to normalized lowercase values
SEVERITY_ORDER: dict[str, str] = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "UNKNOWN": "low",
}

# Numeric levels used for threshold filtering (higher = more severe)
SEVERITY_THRESHOLD_MAP: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


class TrivyCVESource(CVESource):
    """Trivy-based container image CVE scanner.

    Can operate in two modes:

    1. CLI mode: Runs ``trivy image`` locally (default).
    2. Server mode: Queries a Trivy server via its Twirp HTTP API.

    Args:
        server_url: Base URL of a Trivy server (e.g. ``http://trivy:4954``).
            When set, server mode is used; otherwise the local CLI is invoked.
        timeout: Maximum seconds to wait for a scan to complete.
        trivy_path: Filesystem path or name of the ``trivy`` binary.
        cache_dir: Optional override for Trivy's vulnerability DB cache directory.
    """

    source_name = "trivy"

    def __init__(
        self,
        server_url: str | None = None,
        timeout: int = 300,
        trivy_path: str = "trivy",
        cache_dir: str | None = None,
    ) -> None:
        self._server_url = server_url
        self._timeout = timeout
        self._trivy_path = trivy_path
        self._cache_dir = cache_dir

    async def scan(
        self,
        resource_id: str,
        severity_threshold: str = "medium",
    ) -> list[dict[str, Any]]:
        """Scan a container image for CVEs.

        Args:
            resource_id: Container image reference (e.g. ``nginx:1.25``,
                ``registry.example.com/app:v2``).
            severity_threshold: Minimum severity to include in results.
                One of ``critical``, ``high``, ``medium``, ``low``.

        Returns:
            List of standardized finding dicts, sorted by CVSS score descending.
        """
        logger.info("trivy_scan_started", image=resource_id, threshold=severity_threshold)

        if self._server_url:
            raw_results = await self._scan_via_server(resource_id)
        else:
            raw_results = await self._scan_via_cli(resource_id)

        findings = self._parse_results(raw_results, resource_id, severity_threshold)

        logger.info(
            "trivy_scan_completed",
            image=resource_id,
            findings_count=len(findings),
        )
        return findings

    async def _scan_via_cli(self, image: str) -> dict[str, Any]:
        """Run ``trivy image`` and return parsed JSON output.

        Returns an empty ``{"Results": []}`` on any failure so callers receive
        a safe default rather than an exception.
        """
        cmd = [
            self._trivy_path,
            "image",
            "--format",
            "json",
            "--severity",
            "CRITICAL,HIGH,MEDIUM,LOW",
            "--quiet",
        ]
        if self._cache_dir:
            cmd.extend(["--cache-dir", self._cache_dir])
        cmd.append(image)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)

            if proc.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "unknown error"
                logger.error("trivy_cli_failed", returncode=proc.returncode, error=error_msg)
                return {"Results": []}

            return json.loads(stdout.decode()) if stdout else {"Results": []}

        except TimeoutError:
            logger.error("trivy_cli_timeout", image=image, timeout=self._timeout)
            return {"Results": []}
        except FileNotFoundError:
            logger.error("trivy_not_found", path=self._trivy_path)
            return {"Results": []}
        except json.JSONDecodeError as exc:
            logger.error("trivy_json_parse_error", error=str(exc))
            return {"Results": []}

    async def _scan_via_server(self, image: str) -> dict[str, Any]:
        """Query a running Trivy server via its Twirp HTTP API.

        Returns an empty ``{"Results": []}`` on any failure.
        """
        import httpx

        url = f"{self._server_url}/twirp/trivy.scanner.v1.Scanner/Scan"
        payload: dict[str, Any] = {
            "target": image,
            "options": {
                "vuln_type": ["os", "library"],
                "scanners": ["vuln"],
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("trivy_server_http_error", status=exc.response.status_code, image=image)
            return {"Results": []}
        except Exception as exc:
            logger.error("trivy_server_error", error=str(exc), image=image)
            return {"Results": []}

    def _parse_results(
        self,
        raw: dict[str, Any],
        image: str,
        severity_threshold: str,
    ) -> list[dict[str, Any]]:
        """Translate Trivy JSON output into the ShieldOps standard finding schema.

        Args:
            raw: Parsed Trivy JSON response (dict with a ``Results`` list).
            image: Original image reference used as a fallback resource label.
            severity_threshold: Findings below this level are filtered out.

        Returns:
            Findings sorted by CVSS score descending.
        """
        findings: list[dict[str, Any]] = []
        threshold_level = SEVERITY_THRESHOLD_MAP.get(severity_threshold, 2)

        for result in raw.get("Results", []):
            target = result.get("Target", image)
            target_type = result.get("Type", "unknown")

            for vuln in result.get("Vulnerabilities", []):
                trivy_sev = vuln.get("Severity", "UNKNOWN")
                normalized_sev = SEVERITY_ORDER.get(trivy_sev, "low")
                sev_level = SEVERITY_THRESHOLD_MAP.get(normalized_sev, 1)

                if sev_level < threshold_level:
                    continue

                # Derive CVSS score: prefer the highest V3 score, fall back to V2,
                # then estimate from severity label.
                cvss_score = 0.0
                cvss_data = vuln.get("CVSS", {})
                for source_scores in cvss_data.values():
                    if isinstance(source_scores, dict):
                        score = source_scores.get("V3Score", source_scores.get("V2Score", 0.0))
                        cvss_score = max(cvss_score, float(score))
                if cvss_score == 0.0:
                    cvss_score = self._severity_to_cvss(normalized_sev)

                # Parse publication date if present
                published_at: datetime | None = None
                pub_date = vuln.get("PublishedDate")
                if pub_date:
                    try:
                        published_at = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass

                findings.append(
                    {
                        "cve_id": vuln.get("VulnerabilityID", "UNKNOWN"),
                        "severity": normalized_sev,
                        "cvss_score": min(10.0, max(0.0, cvss_score)),
                        "package_name": vuln.get("PkgName", "unknown"),
                        "installed_version": vuln.get("InstalledVersion", "unknown"),
                        "fixed_version": vuln.get("FixedVersion"),
                        "affected_resource": f"{image} ({target})",
                        "description": vuln.get("Title", vuln.get("Description", ""))[:500],
                        "published_at": published_at,
                        "source": "trivy",
                        "target_type": target_type,
                        "references": vuln.get("References", [])[:5],
                        "data_source": vuln.get("DataSource", {}),
                    }
                )

        findings.sort(key=lambda f: f["cvss_score"], reverse=True)
        return findings

    @staticmethod
    def _severity_to_cvss(severity: str) -> float:
        """Estimate a representative CVSS score when no numeric score is available."""
        return {"critical": 9.5, "high": 7.5, "medium": 5.0, "low": 2.5}.get(severity, 0.0)
