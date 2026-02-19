"""Infrastructure as Code (IaC) security scanner.

Wraps **checkov** for scanning Terraform, Kubernetes manifests, Dockerfiles,
Helm charts, and other IaC configurations for security misconfigurations.
"""

import asyncio
import json
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.security.protocols import ScannerType, SecurityScanner

logger = structlog.get_logger()

# Maps checkov severity labels to ShieldOps normalized values
CHECKOV_SEVERITY_MAP: dict[str, str] = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "INFO": "low",
}

# Check-ID / name fragments that suggest higher impact
_CRITICAL_PATTERNS = frozenset({"encryption", "public", "logging_disabled", "root", "admin"})
_HIGH_PATTERNS = frozenset({"default", "unrestricted", "wildcard", "privilege", "rotation"})

_SEVERITY_SORT_KEY: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}

# File extensions that indicate a single-file scan (``--file``) rather than a
# directory scan (``--directory``).
_SINGLE_FILE_EXTENSIONS = frozenset({".tf", ".yaml", ".yml", ".json", ".dockerfile"})


class IaCScanner(SecurityScanner):
    """Scan IaC configurations for security misconfigurations using **checkov**.

    Supports Terraform, Kubernetes manifests, Dockerfiles, Helm charts, and
    any other framework that checkov understands.  Results from multiple
    frameworks are merged into a single finding list.

    Args:
        checkov_path: Filesystem path or name of the ``checkov`` binary.
        timeout: Maximum seconds before the scan is aborted.
        skip_checks: List of check IDs to suppress (e.g. ``["CKV_K8S_8"]``).
        frameworks: IaC frameworks to scan. Defaults to
            ``["terraform", "kubernetes", "dockerfile", "helm"]``.
    """

    scanner_name = "checkov"
    scanner_type = ScannerType.IAC

    def __init__(
        self,
        checkov_path: str = "checkov",
        timeout: int = 600,
        skip_checks: list[str] | None = None,
        frameworks: list[str] | None = None,
    ) -> None:
        self._checkov_path = checkov_path
        self._timeout = timeout
        self._skip_checks: list[str] = skip_checks or []
        self._frameworks: list[str] = frameworks or [
            "terraform",
            "kubernetes",
            "dockerfile",
            "helm",
        ]

    async def scan(self, target: str, **options: Any) -> list[dict[str, Any]]:
        """Scan an IaC directory or file for security misconfigurations.

        Args:
            target: Path to an IaC directory **or** a single IaC file.
                Files with known IaC extensions (``.tf``, ``.yaml``, ``.yml``,
                ``.json``, ``.dockerfile``) trigger ``--file`` mode; all other
                paths use ``--directory`` mode.
            **options:
                frameworks (list[str]): Override the instance-level framework list.
                skip_checks (list[str]): Additional check IDs to suppress for
                    this specific scan.

        Returns:
            List of finding dicts for all failed checks, sorted by severity
            descending.  Passed checks are not included.
        """
        logger.info("checkov_scan_started", target=target)

        # Determine whether this is a file or directory scan
        is_single_file = any(target.endswith(ext) for ext in _SINGLE_FILE_EXTENSIONS)
        target_flag = "--file" if is_single_file else "--directory"

        cmd = [
            self._checkov_path,
            target_flag,
            target,
            "--output",
            "json",
            "--compact",
            "--quiet",
        ]

        frameworks: list[str] = options.get("frameworks", self._frameworks)
        if frameworks:
            cmd.extend(["--framework", ",".join(frameworks)])

        skip_checks: list[str] = list(self._skip_checks) + list(options.get("skip_checks", []))
        if skip_checks:
            cmd.extend(["--skip-check", ",".join(skip_checks)])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)

            if not stdout:
                logger.info("checkov_no_output", target=target)
                return []

            # checkov may emit a JSON list (one item per framework) or a single dict
            raw: Any = json.loads(stdout.decode())
            if isinstance(raw, list):
                all_findings: list[dict[str, Any]] = []
                for framework_result in raw:
                    if isinstance(framework_result, dict):
                        all_findings.extend(self._parse_results(framework_result, target))
                return all_findings

            if isinstance(raw, dict):
                return self._parse_results(raw, target)

            return []

        except TimeoutError:
            logger.error("checkov_timeout", target=target, timeout=self._timeout)
            return []
        except FileNotFoundError:
            logger.error("checkov_not_found", path=self._checkov_path)
            return []
        except json.JSONDecodeError as exc:
            logger.error("checkov_json_error", error=str(exc))
            return []

    def _parse_results(self, raw: dict[str, Any], target: str) -> list[dict[str, Any]]:
        """Translate a single-framework checkov JSON result into findings.

        Args:
            raw: Parsed checkov JSON for one framework (contains a ``results``
                key with ``failed_checks`` and ``passed_checks``).
            target: Original scan target (used for logging and finding metadata).

        Returns:
            Finding list for the framework, sorted by severity descending.
        """
        findings: list[dict[str, Any]] = []
        check_type: str = raw.get("check_type", "unknown")
        results = raw.get("results", {})

        for failed in results.get("failed_checks", []):
            check_id: str = failed.get("check_id", "UNKNOWN")

            # checkov nests check metadata differently depending on version
            check_meta: dict[str, Any] = failed.get("check", {})
            check_name: str = check_meta.get("name", failed.get("name", "Unknown check"))
            severity = self._determine_severity(failed, check_id, check_name)

            file_path: str = failed.get("file_path", "")
            resource: str = failed.get("resource", "")
            file_line_range: list[int] = failed.get("file_line_range", [])
            guideline: str = failed.get("guideline", check_meta.get("guideline", ""))

            line_info = (
                f" (lines {file_line_range[0]}-{file_line_range[1]})"
                if len(file_line_range) >= 2
                else ""
            )

            findings.append(
                {
                    "finding_id": f"iac-{uuid4().hex[:12]}",
                    "scanner_type": ScannerType.IAC.value,
                    "severity": severity,
                    "title": f"[{check_id}] {check_name}",
                    "description": (
                        f"IaC misconfiguration in {check_type} resource '{resource}' "
                        f"at {file_path}{line_info}"
                    ),
                    "affected_resource": (
                        f"{target}/{file_path}:{resource}" if file_path else target
                    ),
                    "remediation": (
                        guideline
                        if guideline
                        else f"Fix {check_id}: {check_name}. Review the {check_type} configuration."
                    ),
                    "metadata": {
                        "check_id": check_id,
                        "check_type": check_type,
                        "resource": resource,
                        "file_path": file_path,
                        "file_line_range": file_line_range,
                        "guideline": guideline,
                        "evaluations": failed.get("evaluations"),
                        "bc_check_id": failed.get("bc_check_id", ""),
                    },
                }
            )

        findings.sort(key=lambda f: _SEVERITY_SORT_KEY.get(f["severity"], 0), reverse=True)

        # Count passed checks (checkov may give a list or an int)
        passed_raw = results.get("passed_checks", [])
        passed_count = passed_raw if isinstance(passed_raw, int) else len(passed_raw)

        logger.info(
            "checkov_scan_completed",
            target=target,
            check_type=check_type,
            passed=passed_count,
            failed=len(findings),
        )
        return findings

    @staticmethod
    def _determine_severity(check: dict[str, Any], check_id: str, check_name: str) -> str:
        """Resolve a severity label for a failed check.

        Priority order:
        1. Explicit severity field on the failed-check or nested check object.
        2. Heuristic based on patterns in the check ID and name.
        3. Default: ``medium``.
        """
        raw_severity: str = check.get("severity") or check.get("check", {}).get("severity", "")
        if raw_severity:
            mapped = CHECKOV_SEVERITY_MAP.get(raw_severity.upper())
            if mapped:
                return mapped

        # Heuristic: scan the combined check ID + name for known risk patterns
        combined = f"{check_id} {check_name}".lower()
        if any(p in combined for p in _CRITICAL_PATTERNS):
            # "public" is critical on its own; others in the critical set are high
            return "critical" if "public" in combined else "high"
        if any(p in combined for p in _HIGH_PATTERNS):
            return "high"
        return "medium"
