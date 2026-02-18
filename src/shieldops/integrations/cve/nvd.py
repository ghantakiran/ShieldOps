"""NVD (National Vulnerability Database) CVE source implementation.

Uses the NIST NVD API 2.0 to scan for known CVEs by keyword (package name)
and filter by CVSS v3.1 severity threshold.
"""

import asyncio
from typing import Any

import structlog

from shieldops.agents.security.protocols import CVESource

logger = structlog.get_logger()

# CVSS v3.1 severity thresholds per NVD specification
SEVERITY_THRESHOLDS: dict[str, float] = {
    "critical": 9.0,
    "high": 7.0,
    "medium": 4.0,
    "low": 0.1,
    "none": 0.0,
}

# NVD API 2.0 rate limits: 5 requests per 30s without key, 50 with key
_DEFAULT_PAGE_SIZE = 20
_DEFAULT_TIMEOUT = 30


class NVDCVESource(CVESource):
    """CVE source backed by the NIST National Vulnerability Database API 2.0.

    Supports searching vulnerabilities by keyword (typically a package or
    library name) and filtering results by CVSS v3.1 severity.

    Args:
        api_key: Optional NVD API key for higher rate limits.
        base_url: NVD API base URL (override for testing).
        timeout: HTTP request timeout in seconds.
    """

    source_name = "nvd"

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://services.nvd.nist.gov/rest/json/cves/2.0",
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._session: Any = None

    def _ensure_session(self) -> Any:
        """Lazily initialize an httpx AsyncClient."""
        if self._session is None:
            import httpx

            headers: dict[str, str] = {"Accept": "application/json"}
            if self._api_key:
                headers["apiKey"] = self._api_key
            self._session = httpx.AsyncClient(
                headers=headers,
                timeout=self._timeout,
            )
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    async def scan(
        self,
        resource_id: str,
        severity_threshold: str = "medium",
    ) -> list[dict[str, Any]]:
        """Scan for CVEs matching a resource/package name.

        Queries the NVD API using the resource_id as a keyword search term,
        then filters results to those at or above the given severity threshold.

        Args:
            resource_id: Package or library name to search for (e.g. "openssl").
            severity_threshold: Minimum severity level ("critical", "high",
                "medium", "low", "none").

        Returns:
            List of finding dicts with standardized keys.
        """
        threshold = severity_threshold.lower()
        min_score = SEVERITY_THRESHOLDS.get(threshold, 4.0)

        logger.info(
            "nvd_scan_start",
            resource_id=resource_id,
            severity_threshold=threshold,
            min_cvss_score=min_score,
        )

        try:
            raw_cves = await self._fetch_cves(resource_id)
        except Exception as e:
            logger.error("nvd_scan_failed", resource_id=resource_id, error=str(e))
            return []

        findings: list[dict[str, Any]] = []
        for cve_item in raw_cves:
            finding = self._parse_cve(cve_item, resource_id)
            if finding and finding["cvss_score"] >= min_score:
                findings.append(finding)

        findings.sort(key=lambda f: f["cvss_score"], reverse=True)

        logger.info(
            "nvd_scan_complete",
            resource_id=resource_id,
            total_cves=len(raw_cves),
            findings_above_threshold=len(findings),
        )

        return findings

    async def _fetch_cves(
        self,
        keyword: str,
        start_index: int = 0,
        results_per_page: int = _DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """Fetch CVEs from NVD API 2.0 with keyword search.

        Handles pagination if total results exceed page size.
        """
        session = self._ensure_session()

        params: dict[str, Any] = {
            "keywordSearch": keyword,
            "startIndex": start_index,
            "resultsPerPage": results_per_page,
        }

        response = await session.get(self._base_url, params=params)
        response.raise_for_status()
        data = response.json()

        vulnerabilities: list[dict[str, Any]] = data.get("vulnerabilities", [])
        total_results: int = data.get("totalResults", 0)

        # Paginate if there are more results (limit to 3 pages to avoid rate limits)
        if total_results > start_index + results_per_page and start_index == 0:
            pages_to_fetch = min(
                2,  # max 2 additional pages
                (total_results - results_per_page) // results_per_page + 1,
            )
            for page in range(1, pages_to_fetch + 1):
                # Respect rate limits: sleep between requests
                await asyncio.sleep(0.5 if self._api_key else 6.0)
                next_page = await self._fetch_cves(
                    keyword,
                    start_index=page * results_per_page,
                    results_per_page=results_per_page,
                )
                vulnerabilities.extend(next_page)

        return vulnerabilities

    def _parse_cve(self, cve_item: dict[str, Any], resource_id: str) -> dict[str, Any] | None:
        """Parse a single NVD API 2.0 vulnerability item into a standardized finding.

        Returns None if the CVE lacks usable CVSS data.
        """
        cve_data = cve_item.get("cve", {})
        cve_id: str = cve_data.get("id", "")

        # Extract CVSS v3.1 score (prefer primary metric)
        metrics = cve_data.get("metrics", {})
        cvss_score = 0.0
        severity = "unknown"

        # Try CVSS v3.1 first, then v3.0, then v2.0
        for metric_key in ("cvssMetricV31", "cvssMetricV30"):
            metric_list = metrics.get(metric_key, [])
            if metric_list:
                primary = metric_list[0]
                cvss_data = primary.get("cvssData", {})
                cvss_score = cvss_data.get("baseScore", 0.0)
                severity = cvss_data.get("baseSeverity", "UNKNOWN").lower()
                break

        if cvss_score == 0.0:
            # Fall back to CVSS v2
            v2_list = metrics.get("cvssMetricV2", [])
            if v2_list:
                cvss_data = v2_list[0].get("cvssData", {})
                cvss_score = cvss_data.get("baseScore", 0.0)
                severity = self._score_to_severity(cvss_score)

        if cvss_score == 0.0:
            return None

        # Extract description (prefer English)
        descriptions = cve_data.get("descriptions", [])
        description = ""
        for desc in descriptions:
            if desc.get("lang") == "en":
                description = desc.get("value", "")
                break
        if not description and descriptions:
            description = descriptions[0].get("value", "")

        # Extract affected package info from CPE matches
        package_name = resource_id
        installed_version = ""
        fixed_version = ""

        configurations = cve_data.get("configurations", [])
        for config in configurations:
            for node in config.get("nodes", []):
                for cpe_match in node.get("cpeMatch", []):
                    criteria: str = cpe_match.get("criteria", "")
                    if resource_id.lower() in criteria.lower():
                        parts = criteria.split(":")
                        if len(parts) >= 6:
                            package_name = parts[4] if parts[4] != "*" else resource_id
                            installed_version = parts[5] if parts[5] != "*" else ""
                        version_end = cpe_match.get(
                            "versionEndExcluding",
                            cpe_match.get("versionEndIncluding", ""),
                        )
                        if version_end:
                            fixed_version = version_end
                        break

        return {
            "cve_id": cve_id,
            "severity": severity,
            "cvss_score": cvss_score,
            "package_name": package_name,
            "installed_version": installed_version,
            "fixed_version": fixed_version,
            "affected_resource": resource_id,
            "description": description[:500],
            "published": cve_data.get("published", ""),
            "last_modified": cve_data.get("lastModified", ""),
            "source": "nvd",
        }

    @staticmethod
    def _score_to_severity(score: float) -> str:
        """Convert a CVSS score to a severity label."""
        if score >= 9.0:
            return "critical"
        elif score >= 7.0:
            return "high"
        elif score >= 4.0:
            return "medium"
        elif score >= 0.1:
            return "low"
        return "none"
