"""OS vendor advisory feeds: Ubuntu USN and Red Hat RHSA.

Provides CVE sources for OS-specific security advisories.
"""

from typing import Any

import structlog

from shieldops.agents.security.protocols import CVESource

logger = structlog.get_logger()

SEVERITY_THRESHOLDS: dict[str, float] = {
    "critical": 9.0,
    "high": 7.0,
    "medium": 4.0,
    "low": 0.1,
}


class UbuntuUSNSource(CVESource):
    """CVE source backed by Ubuntu Security Notices (USN).

    Queries the Ubuntu security notices JSON feed.

    Args:
        base_url: Ubuntu security notices API URL.
    """

    source_name = "ubuntu_usn"

    def __init__(
        self,
        base_url: str = "https://ubuntu.com/security/notices.json",
    ) -> None:
        self._base_url = base_url
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(
                headers={"Accept": "application/json"},
                timeout=30,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def scan(
        self,
        resource_id: str,
        severity_threshold: str = "medium",
    ) -> list[dict[str, Any]]:
        """Scan for Ubuntu USNs matching a package name."""
        min_score = SEVERITY_THRESHOLDS.get(severity_threshold.lower(), 4.0)

        logger.info(
            "ubuntu_usn_scan_start",
            resource_id=resource_id,
            severity_threshold=severity_threshold,
        )

        try:
            raw = await self._fetch_notices(resource_id)
        except Exception as e:
            logger.error("ubuntu_usn_scan_failed", resource_id=resource_id, error=str(e))
            return []

        findings: list[dict[str, Any]] = []
        for notice in raw:
            parsed = self._parse_notice(notice, resource_id)
            for finding in parsed:
                if finding["cvss_score"] >= min_score:
                    findings.append(finding)

        findings.sort(key=lambda f: f["cvss_score"], reverse=True)

        logger.info(
            "ubuntu_usn_scan_complete",
            resource_id=resource_id,
            total_notices=len(raw),
            findings=len(findings),
        )
        return findings

    async def _fetch_notices(self, package: str) -> list[dict[str, Any]]:
        client = self._ensure_client()
        response = await client.get(
            self._base_url,
            params={"details": package, "limit": 50},
        )
        response.raise_for_status()
        data = response.json()
        notices: list[dict[str, Any]] = data.get("notices", [])
        return notices

    def _parse_notice(self, notice: dict[str, Any], resource_id: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        usn_id = notice.get("id", "")
        title = notice.get("title", "")
        description = notice.get("description", "")
        published = notice.get("published", "")
        priority = notice.get("priority", "medium")

        severity = self._priority_to_severity(priority)
        cvss_score = self._severity_to_score(severity)

        cves = notice.get("cves", [])
        if cves:
            for cve_id in cves:
                findings.append(
                    {
                        "cve_id": cve_id if isinstance(cve_id, str) else cve_id.get("id", usn_id),
                        "usn_id": usn_id,
                        "severity": severity,
                        "cvss_score": cvss_score,
                        "package_name": resource_id,
                        "installed_version": "",
                        "fixed_version": "",
                        "affected_resource": resource_id,
                        "description": (title or description)[:500],
                        "published": published,
                        "source": "ubuntu_usn",
                    }
                )
        else:
            findings.append(
                {
                    "cve_id": usn_id,
                    "usn_id": usn_id,
                    "severity": severity,
                    "cvss_score": cvss_score,
                    "package_name": resource_id,
                    "installed_version": "",
                    "fixed_version": "",
                    "affected_resource": resource_id,
                    "description": (title or description)[:500],
                    "published": published,
                    "source": "ubuntu_usn",
                }
            )

        return findings

    @staticmethod
    def _priority_to_severity(priority: str) -> str:
        return {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "negligible": "low",
        }.get(priority.lower(), "medium")

    @staticmethod
    def _severity_to_score(severity: str) -> float:
        return {"critical": 9.5, "high": 7.5, "medium": 5.0, "low": 2.0}.get(severity, 5.0)


class RedHatRHSASource(CVESource):
    """CVE source backed by Red Hat Security Data API (RHSA).

    Queries Red Hat's security data API for advisories.

    Args:
        base_url: Red Hat security data API URL.
    """

    source_name = "redhat_rhsa"

    def __init__(
        self,
        base_url: str = "https://access.redhat.com/labs/securitydataapi",
    ) -> None:
        self._base_url = base_url
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(
                headers={"Accept": "application/json"},
                timeout=30,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def scan(
        self,
        resource_id: str,
        severity_threshold: str = "medium",
    ) -> list[dict[str, Any]]:
        """Scan for Red Hat advisories matching a package name."""
        min_score = SEVERITY_THRESHOLDS.get(severity_threshold.lower(), 4.0)

        logger.info(
            "redhat_rhsa_scan_start",
            resource_id=resource_id,
            severity_threshold=severity_threshold,
        )

        try:
            raw = await self._fetch_advisories(resource_id)
        except Exception as e:
            logger.error("redhat_rhsa_scan_failed", resource_id=resource_id, error=str(e))
            return []

        findings: list[dict[str, Any]] = []
        for advisory in raw:
            finding = self._parse_advisory(advisory, resource_id)
            if finding and finding["cvss_score"] >= min_score:
                findings.append(finding)

        findings.sort(key=lambda f: f["cvss_score"], reverse=True)

        logger.info(
            "redhat_rhsa_scan_complete",
            resource_id=resource_id,
            total=len(raw),
            findings=len(findings),
        )
        return findings

    async def _fetch_advisories(self, package: str) -> list[dict[str, Any]]:
        client = self._ensure_client()
        response = await client.get(
            f"{self._base_url}/cve.json",
            params={"package": package, "per_page": 50},
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return data
        result: list[dict[str, Any]] = data.get("data", data.get("advisories", []))
        return result

    def _parse_advisory(self, advisory: dict[str, Any], resource_id: str) -> dict[str, Any] | None:
        cve_id = advisory.get("CVE", advisory.get("cve_id", ""))
        severity = advisory.get("severity", "moderate").lower()

        if severity == "moderate":
            severity = "medium"
        elif severity == "important":
            severity = "high"

        cvss_score = advisory.get("cvss3_score", advisory.get("cvss_score", 0.0))
        if isinstance(cvss_score, str):
            try:
                cvss_score = float(cvss_score)
            except ValueError:
                cvss_score = self._severity_to_score(severity)
        if cvss_score == 0.0:
            cvss_score = self._severity_to_score(severity)

        return {
            "cve_id": cve_id,
            "rhsa_id": advisory.get("RHSA", advisory.get("advisory_id", "")),
            "severity": severity,
            "cvss_score": cvss_score,
            "package_name": advisory.get("affected_package", resource_id),
            "installed_version": "",
            "fixed_version": advisory.get("fix_version", ""),
            "affected_resource": resource_id,
            "description": advisory.get("bugzilla_description", advisory.get("synopsis", ""))[:500],
            "published": advisory.get("public_date", ""),
            "source": "redhat_rhsa",
        }

    @staticmethod
    def _severity_to_score(severity: str) -> float:
        return {"critical": 9.5, "high": 7.5, "medium": 5.0, "low": 2.0}.get(severity, 5.0)
