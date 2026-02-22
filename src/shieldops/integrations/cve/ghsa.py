"""GitHub Advisory Database (GHSA) CVE source.

Uses the GitHub GraphQL API to query security advisories for
open-source packages across multiple ecosystems.
"""

from typing import Any

import structlog

from shieldops.agents.security.protocols import CVESource

logger = structlog.get_logger()

# GitHub ecosystem identifiers
ECOSYSTEM_MAP: dict[str, str] = {
    "pip": "PIP",
    "python": "PIP",
    "npm": "NPM",
    "node": "NPM",
    "go": "GO",
    "golang": "GO",
    "maven": "MAVEN",
    "java": "MAVEN",
    "nuget": "NUGET",
    "dotnet": "NUGET",
    "rubygems": "RUBYGEMS",
    "ruby": "RUBYGEMS",
    "composer": "COMPOSER",
    "php": "COMPOSER",
    "rust": "RUST",
    "cargo": "RUST",
}

SEVERITY_MAP: dict[str, str] = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MODERATE": "medium",
    "LOW": "low",
}

SEVERITY_THRESHOLDS: dict[str, float] = {
    "critical": 9.0,
    "high": 7.0,
    "medium": 4.0,
    "low": 0.1,
}

_GRAPHQL_QUERY = """
query($keyword: String!, $ecosystem: SecurityAdvisoryEcosystem, $first: Int!) {
  securityVulnerabilities(
    first: $first,
    package: $keyword,
    ecosystem: $ecosystem,
    orderBy: {field: UPDATED_AT, direction: DESC}
  ) {
    nodes {
      advisory {
        ghsaId
        summary
        description
        severity
        cvss {
          score
          vectorString
        }
        identifiers {
          type
          value
        }
        publishedAt
        updatedAt
        references {
          url
        }
      }
      package {
        name
        ecosystem
      }
      vulnerableVersionRange
      firstPatchedVersion {
        identifier
      }
    }
  }
}
"""


class GHSACVESource(CVESource):
    """CVE source backed by the GitHub Advisory Database (GHSA).

    Queries the GitHub GraphQL API for security advisories affecting
    a given package. Supports ecosystem detection from the resource_id
    format (e.g. "pip:requests" or just "requests").

    Args:
        token: GitHub personal access token.
        base_url: GitHub GraphQL endpoint (override for testing).
    """

    source_name = "ghsa"

    def __init__(
        self,
        token: str = "",
        base_url: str = "https://api.github.com/graphql",
    ) -> None:
        self._token = token
        self._base_url = base_url
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import httpx

            headers: dict[str, str] = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            if self._token:
                headers["Authorization"] = f"bearer {self._token}"
            self._client = httpx.AsyncClient(
                headers=headers,
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
        """Scan for GitHub advisories matching a package name.

        resource_id can be "ecosystem:package" (e.g. "pip:django") or
        just "package" for auto-detection.
        """
        min_score = SEVERITY_THRESHOLDS.get(severity_threshold.lower(), 4.0)

        package, ecosystem = self._parse_resource_id(resource_id)

        logger.info(
            "ghsa_scan_start",
            package=package,
            ecosystem=ecosystem,
            severity_threshold=severity_threshold,
        )

        try:
            raw = await self._fetch_advisories(package, ecosystem)
        except Exception as e:
            logger.error("ghsa_scan_failed", package=package, error=str(e))
            return []

        findings: list[dict[str, Any]] = []
        for node in raw:
            finding = self._parse_advisory(node, resource_id)
            if finding and finding["cvss_score"] >= min_score:
                findings.append(finding)

        findings.sort(key=lambda f: f["cvss_score"], reverse=True)

        logger.info(
            "ghsa_scan_complete",
            package=package,
            total=len(raw),
            findings_above_threshold=len(findings),
        )
        return findings

    def _parse_resource_id(self, resource_id: str) -> tuple[str, str | None]:
        """Parse 'ecosystem:package' or just 'package'."""
        if ":" in resource_id:
            eco, pkg = resource_id.split(":", 1)
            ghsa_eco = ECOSYSTEM_MAP.get(eco.lower())
            return pkg, ghsa_eco
        return resource_id, None

    async def _fetch_advisories(
        self, keyword: str, ecosystem: str | None, first: int = 50
    ) -> list[dict[str, Any]]:
        client = self._ensure_client()

        variables: dict[str, Any] = {"keyword": keyword, "first": first}
        if ecosystem:
            variables["ecosystem"] = ecosystem

        response = await client.post(
            self._base_url,
            json={"query": _GRAPHQL_QUERY, "variables": variables},
        )
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            logger.warning("ghsa_graphql_errors", errors=data["errors"])

        nodes: list[dict[str, Any]] = (
            data.get("data", {}).get("securityVulnerabilities", {}).get("nodes", [])
        )
        return nodes

    def _parse_advisory(self, node: dict[str, Any], resource_id: str) -> dict[str, Any] | None:
        advisory = node.get("advisory", {})
        package_info = node.get("package", {})

        # Extract CVE ID from identifiers (prefer CVE over GHSA)
        cve_id = ""
        ghsa_id = advisory.get("ghsaId", "")
        for ident in advisory.get("identifiers", []):
            if ident.get("type") == "CVE":
                cve_id = ident.get("value", "")
                break
        if not cve_id:
            cve_id = ghsa_id

        # CVSS score
        cvss = advisory.get("cvss", {})
        cvss_score = cvss.get("score", 0.0) if cvss else 0.0

        # Severity
        raw_severity = advisory.get("severity", "MODERATE")
        severity = SEVERITY_MAP.get(raw_severity, "medium")

        # If no CVSS score, infer from severity
        if cvss_score == 0.0:
            cvss_score = {
                "critical": 9.5,
                "high": 7.5,
                "medium": 5.0,
                "low": 2.0,
            }.get(severity, 5.0)

        # Version info
        patched = node.get("firstPatchedVersion")
        fixed_version = patched.get("identifier", "") if patched else ""
        version_range = node.get("vulnerableVersionRange", "")

        return {
            "cve_id": cve_id,
            "ghsa_id": ghsa_id,
            "severity": severity,
            "cvss_score": cvss_score,
            "package_name": package_info.get("name", resource_id),
            "ecosystem": package_info.get("ecosystem", ""),
            "installed_version": version_range,
            "fixed_version": fixed_version,
            "affected_resource": resource_id,
            "description": (advisory.get("summary", "") or advisory.get("description", ""))[:500],
            "published": advisory.get("publishedAt", ""),
            "last_modified": advisory.get("updatedAt", ""),
            "source": "ghsa",
        }
