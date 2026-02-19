"""Git repository security scanners.

Two scanners are provided:

- :class:`GitSecretScanner`: Detects hardcoded secrets via **gitleaks**.
- :class:`GitDependencyScanner`: Finds vulnerable dependencies via **osv-scanner** (SCA).
"""

import asyncio
import json
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.security.protocols import ScannerType, SecurityScanner

logger = structlog.get_logger()

# Rule IDs (lowercased) that map to CRITICAL severity
_CRITICAL_RULE_FRAGMENTS = frozenset(
    {
        "aws-access-key-id",
        "aws-secret-access-key",
        "gcp-service-account",
        "azure-storage-key",
        "private-key",
        "github-pat",
        "gitlab-pat",
    }
)

# Rule IDs (lowercased) that map to HIGH severity
_HIGH_RULE_FRAGMENTS = frozenset(
    {
        "generic-api-key",
        "slack-token",
        "stripe-api-key",
        "twilio-api-key",
        "sendgrid-api-key",
        "database-url",
    }
)

_SEVERITY_SORT_KEY: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class GitSecretScanner(SecurityScanner):
    """Detect hardcoded secrets in git repositories using **gitleaks**.

    gitleaks exits 0 when clean and 1 when findings are present.  Any other
    exit code is treated as a tool-level error and an empty list is returned.

    Args:
        gitleaks_path: Filesystem path or name of the ``gitleaks`` binary.
        timeout: Maximum seconds before the scan is aborted.
        config_path: Optional path to a custom gitleaks configuration file.
    """

    scanner_name = "gitleaks"
    scanner_type = ScannerType.SECRET

    def __init__(
        self,
        gitleaks_path: str = "gitleaks",
        timeout: int = 300,
        config_path: str | None = None,
    ) -> None:
        self._gitleaks_path = gitleaks_path
        self._timeout = timeout
        self._config_path = config_path

    async def scan(self, target: str, **options: Any) -> list[dict[str, Any]]:
        """Scan a git repository for hardcoded secrets.

        Args:
            target: Filesystem path to a local git repository.
            **options:
                branch (str): Restrict scan to a specific branch.
                commit_range (str): Restrict scan to a commit range
                    (passed via ``--log-opts``).

        Returns:
            List of secret finding dicts sorted by severity descending.
            Secrets are **redacted** in the returned output — only a
            ``***REDACTED***`` placeholder is stored.
        """
        logger.info("gitleaks_scan_started", target=target)

        cmd = [
            self._gitleaks_path,
            "detect",
            "--source",
            target,
            "--report-format",
            "json",
            "--report-path",
            "/dev/stdout",
            "--no-banner",
        ]

        if self._config_path:
            cmd.extend(["--config", self._config_path])

        branch = options.get("branch")
        if branch:
            cmd.extend(["--branch", str(branch)])

        commit_range = options.get("commit_range")
        if commit_range:
            cmd.extend(["--log-opts", f"--all {commit_range}"])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)

            # Exit 0 → clean; Exit 1 → findings; anything else → error
            if proc.returncode not in (0, 1):
                error_msg = stderr.decode().strip() if stderr else "unknown error"
                logger.error("gitleaks_failed", returncode=proc.returncode, error=error_msg)
                return []

            if not stdout or proc.returncode == 0:
                logger.info("gitleaks_scan_clean", target=target)
                return []

            raw_findings: list[dict[str, Any]] = json.loads(stdout.decode())
            findings = self._parse_findings(raw_findings, target)

            logger.info(
                "gitleaks_scan_completed",
                target=target,
                findings_count=len(findings),
            )
            return findings

        except TimeoutError:
            logger.error("gitleaks_timeout", target=target, timeout=self._timeout)
            return []
        except FileNotFoundError:
            logger.error("gitleaks_not_found", path=self._gitleaks_path)
            return []
        except json.JSONDecodeError as exc:
            logger.error("gitleaks_json_error", error=str(exc))
            return []

    def _parse_findings(self, raw: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
        """Convert raw gitleaks output to the ShieldOps standard finding schema.

        Secrets in the ``Match`` field are replaced with ``***REDACTED***`` to
        prevent sensitive values from being stored in downstream systems.
        """
        findings: list[dict[str, Any]] = []

        for item in raw:
            rule_id: str = item.get("RuleID", "unknown")
            severity = self._classify_severity(rule_id, item.get("Tags", []))

            match_text: str = item.get("Match", "")
            secret: str = item.get("Secret", "")
            redacted_match = match_text.replace(secret, "***REDACTED***") if secret else match_text

            file_path: str = item.get("File", "unknown")
            start_line = item.get("StartLine")

            findings.append(
                {
                    "finding_id": f"secret-{uuid4().hex[:12]}",
                    "scanner_type": ScannerType.SECRET.value,
                    "severity": severity,
                    "title": f"Hardcoded secret detected: {rule_id}",
                    "description": (
                        f"Secret of type '{rule_id}' found in {file_path} "
                        f"at line {start_line or '?'}. "
                        f"Match: {redacted_match[:100]}"
                    ),
                    "affected_resource": f"{target}:{file_path}",
                    "remediation": (
                        f"Remove the hardcoded {rule_id} from the source code. "
                        "Use environment variables or a secret manager instead. "
                        "Rotate the exposed credential immediately."
                    ),
                    "metadata": {
                        "rule_id": rule_id,
                        "file": file_path,
                        "start_line": start_line,
                        "end_line": item.get("EndLine"),
                        "commit": item.get("Commit", ""),
                        "author": item.get("Author", ""),
                        "date": item.get("Date", ""),
                        "tags": item.get("Tags", []),
                        "entropy": item.get("Entropy", 0.0),
                    },
                }
            )

        findings.sort(key=lambda f: _SEVERITY_SORT_KEY.get(f["severity"], 0), reverse=True)
        return findings

    @staticmethod
    def _classify_severity(rule_id: str, tags: list[str]) -> str:
        """Map a gitleaks rule ID to a ShieldOps severity level.

        Priority: explicit rule-fragment match → keyword heuristic → ``medium``.
        """
        rule_lower = rule_id.lower()

        if any(fragment in rule_lower for fragment in _CRITICAL_RULE_FRAGMENTS):
            return "critical"
        if any(fragment in rule_lower for fragment in _HIGH_RULE_FRAGMENTS):
            return "high"
        if any(kw in rule_lower for kw in ("key", "token", "password", "secret", "credential")):
            return "high"
        return "medium"


class GitDependencyScanner(SecurityScanner):
    """Scan project dependencies for known CVEs using **osv-scanner**.

    osv-scanner exits 0 when clean and 1 when vulnerable packages are found.
    Exit code 128 indicates a hard error (e.g. no lockfile found).

    Args:
        osv_scanner_path: Filesystem path or name of the ``osv-scanner`` binary.
        timeout: Maximum seconds before the scan is aborted.
    """

    scanner_name = "osv-scanner"
    scanner_type = ScannerType.CVE

    def __init__(
        self,
        osv_scanner_path: str = "osv-scanner",
        timeout: int = 300,
    ) -> None:
        self._osv_scanner_path = osv_scanner_path
        self._timeout = timeout

    async def scan(self, target: str, **options: Any) -> list[dict[str, Any]]:
        """Scan a project directory for vulnerable dependencies.

        Args:
            target: Filesystem path to the project directory containing lockfiles.
            **options:
                lockfile (str): Scan a specific lockfile instead of discovering
                    lockfiles recursively under *target*.

        Returns:
            List of dependency finding dicts sorted by severity descending.
        """
        logger.info("osv_scanner_started", target=target)

        lockfile: str | None = options.get("lockfile")
        if lockfile:
            cmd = [
                self._osv_scanner_path,
                "--format",
                "json",
                "--lockfile",
                lockfile,
            ]
        else:
            cmd = [
                self._osv_scanner_path,
                "--format",
                "json",
                "--recursive",
                target,
            ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)

            # Exit 0 → clean; Exit 1 → vulnerabilities found; 128 → hard error
            if proc.returncode not in (0, 1):
                error_msg = stderr.decode().strip() if stderr else "unknown error"
                logger.error("osv_scanner_failed", returncode=proc.returncode, error=error_msg)
                return []

            if not stdout or proc.returncode == 0:
                logger.info("osv_scanner_clean", target=target)
                return []

            raw: dict[str, Any] = json.loads(stdout.decode())
            findings = self._parse_results(raw, target)

            logger.info("osv_scanner_completed", target=target, findings_count=len(findings))
            return findings

        except TimeoutError:
            logger.error("osv_scanner_timeout", target=target, timeout=self._timeout)
            return []
        except FileNotFoundError:
            logger.error("osv_scanner_not_found", path=self._osv_scanner_path)
            return []
        except json.JSONDecodeError as exc:
            logger.error("osv_scanner_json_error", error=str(exc))
            return []

    def _parse_results(self, raw: dict[str, Any], target: str) -> list[dict[str, Any]]:
        """Convert osv-scanner JSON output to the ShieldOps standard finding schema."""
        findings: list[dict[str, Any]] = []

        for result in raw.get("results", []):
            source_path: str = result.get("source", {}).get("path", target)

            for pkg in result.get("packages", []):
                pkg_info = pkg.get("package", {})
                pkg_name: str = pkg_info.get("name", "unknown")
                pkg_version: str = pkg_info.get("version", "unknown")
                pkg_ecosystem: str = pkg_info.get("ecosystem", "unknown")

                for vuln in pkg.get("vulnerabilities", []):
                    vuln_id: str = vuln.get("id", "UNKNOWN")
                    aliases: list[str] = vuln.get("aliases", [])
                    # Prefer a CVE alias if one exists; otherwise use the OSV ID
                    cve_id = next((a for a in aliases if a.startswith("CVE-")), vuln_id)

                    severity = self._determine_severity(vuln)
                    fixed_version = self._get_fixed_version(vuln, pkg_name)

                    findings.append(
                        {
                            "finding_id": f"dep-{uuid4().hex[:12]}",
                            "scanner_type": ScannerType.CVE.value,
                            "severity": severity,
                            "title": (
                                f"{cve_id}: {vuln.get('summary', 'Vulnerable dependency')[:200]}"
                            ),
                            "description": vuln.get("details", vuln.get("summary", ""))[:500],
                            "affected_resource": f"{target} ({source_path})",
                            "remediation": (
                                f"Update {pkg_name} from {pkg_version} to {fixed_version}"
                                if fixed_version
                                else (
                                    f"No fix available yet for {pkg_name} {pkg_version}. "
                                    f"Monitor {vuln_id} for upstream patches."
                                )
                            ),
                            "metadata": {
                                "vuln_id": vuln_id,
                                "cve_id": cve_id,
                                "package_name": pkg_name,
                                "package_version": pkg_version,
                                "ecosystem": pkg_ecosystem,
                                "fixed_version": fixed_version,
                                "source_path": source_path,
                                "aliases": aliases,
                                "references": [
                                    ref.get("url")
                                    for ref in vuln.get("references", [])[:5]
                                    if ref.get("url")
                                ],
                            },
                        }
                    )

        findings.sort(key=lambda f: _SEVERITY_SORT_KEY.get(f["severity"], 0), reverse=True)
        return findings

    @staticmethod
    def _determine_severity(vuln: dict[str, Any]) -> str:
        """Derive a severity label from OSV severity entries or database metadata.

        Attempts to parse a numeric CVSS score from the ``severity`` list first,
        then falls back to ``database_specific.severity``, and finally defaults
        to ``medium``.
        """
        for severity_entry in vuln.get("severity", []):
            if "CVSS" not in severity_entry.get("type", ""):
                continue
            score_str: str = severity_entry.get("score", "")
            # CVSS vectors encode the score as one of the slash-delimited tokens
            for part in score_str.split("/"):
                try:
                    score = float(part)
                    if score >= 9.0:
                        return "critical"
                    if score >= 7.0:
                        return "high"
                    if score >= 4.0:
                        return "medium"
                    return "low"
                except ValueError:
                    continue

        db_severity: str = vuln.get("database_specific", {}).get("severity", "")
        if db_severity and db_severity.lower() in ("critical", "high", "medium", "low"):
            return db_severity.lower()

        return "medium"

    @staticmethod
    def _get_fixed_version(vuln: dict[str, Any], pkg_name: str) -> str | None:
        """Extract the earliest fixed version from OSV affected ranges for *pkg_name*."""
        for affected in vuln.get("affected", []):
            if affected.get("package", {}).get("name") != pkg_name:
                continue
            for rng in affected.get("ranges", []):
                for event in rng.get("events", []):
                    if "fixed" in event:
                        return event["fixed"]
        return None
