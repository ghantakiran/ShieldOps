"""Secret detection — scans repos, configmaps, and pod env vars."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from shieldops.security_agent.models import (
    FindingType,
    SecretFinding,
    VulnerabilitySeverity,
)

logger = structlog.get_logger(__name__)

# -----------------------------------------------------------------------
# Compiled regex patterns for common secret types
# -----------------------------------------------------------------------

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str], FindingType, VulnerabilitySeverity]] = [
    (
        "AWS Access Key ID",
        re.compile(r"(?:^|[^A-Z0-9])(?:AKIA[0-9A-Z]{16})(?:$|[^A-Z0-9])"),
        FindingType.API_KEY,
        VulnerabilitySeverity.CRITICAL,
    ),
    (
        "AWS Secret Access Key",
        re.compile(
            r"(?:aws_secret_access_key|secret_access_key|aws_secret)\s*"
            r"[=:]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"
        ),
        FindingType.API_KEY,
        VulnerabilitySeverity.CRITICAL,
    ),
    (
        "GitHub Personal Access Token",
        re.compile(r"ghp_[A-Za-z0-9_]{36,}"),
        FindingType.TOKEN,
        VulnerabilitySeverity.HIGH,
    ),
    (
        "GitHub OAuth Token",
        re.compile(r"gho_[A-Za-z0-9_]{36,}"),
        FindingType.TOKEN,
        VulnerabilitySeverity.HIGH,
    ),
    (
        "Generic API Key assignment",
        re.compile(
            r"(?:api[_-]?key|apikey)\s*[=:]\s*['\"]([A-Za-z0-9_\-]{20,})['\"]",
            re.IGNORECASE,
        ),
        FindingType.API_KEY,
        VulnerabilitySeverity.HIGH,
    ),
    (
        "Private Key header",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
        FindingType.PRIVATE_KEY,
        VulnerabilitySeverity.CRITICAL,
    ),
    (
        "Password in config",
        re.compile(
            r"(?:password|passwd|pwd)\s*[=:]\s*['\"]([^'\"]{8,})['\"]",
            re.IGNORECASE,
        ),
        FindingType.PASSWORD,
        VulnerabilitySeverity.HIGH,
    ),
    (
        "JWT Token",
        re.compile(
            r"eyJ[A-Za-z0-9_-]{10,}\."
            r"eyJ[A-Za-z0-9_-]{10,}\."
            r"[A-Za-z0-9_-]{10,}"
        ),
        FindingType.TOKEN,
        VulnerabilitySeverity.HIGH,
    ),
    (
        "Generic Secret assignment",
        re.compile(
            r"(?:secret|token|auth_token|access_token)\s*[=:]\s*"
            r"['\"]([A-Za-z0-9_\-/+=]{16,})['\"]",
            re.IGNORECASE,
        ),
        FindingType.TOKEN,
        VulnerabilitySeverity.MEDIUM,
    ),
]

# File extensions worth scanning (skip binaries, images, etc.)
_SCANNABLE_EXTENSIONS: set[str] = {
    ".py",
    ".js",
    ".ts",
    ".go",
    ".java",
    ".rb",
    ".rs",
    ".sh",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".properties",
    ".tf",
    ".hcl",
    ".xml",
    ".gradle",
}

# Paths that should always be skipped.
_SKIP_DIRS: set[str] = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}


def _mask_snippet(line: str, max_len: int = 120) -> str:
    """Return a masked version of a line containing a secret."""
    truncated = line.strip()[:max_len]
    # Replace long alphanumeric runs (likely the secret value) with ***
    return re.sub(r"[A-Za-z0-9/+=_\-]{12,}", "***REDACTED***", truncated)


class SecretDetector:
    """Detects hardcoded secrets in source repos and Kubernetes resources."""

    # ------------------------------------------------------------------
    # Repository scanning
    # ------------------------------------------------------------------

    async def scan_repository(self, repo_path: str) -> list[SecretFinding]:
        """Walk *repo_path* and scan text files for secret patterns.

        Returns a list of :class:`SecretFinding` instances with masked
        snippets — the raw secret value is never stored.
        """
        logger.info("secret_scan.repo_start", repo_path=repo_path)
        root = Path(repo_path)
        if not root.is_dir():
            logger.error("secret_scan.invalid_path", repo_path=repo_path)
            return []

        findings: list[SecretFinding] = []

        # Run blocking file I/O in a thread to stay async-friendly.
        file_list = await asyncio.to_thread(self._collect_files, root)

        for file_path in file_list:
            try:
                content = await asyncio.to_thread(file_path.read_text, "utf-8", "replace")
            except Exception:
                logger.debug("secret_scan.read_error", path=str(file_path))
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                for _name, pattern, finding_type, sev in _SECRET_PATTERNS:
                    if pattern.search(line):
                        findings.append(
                            SecretFinding(
                                finding_type=finding_type,
                                location=f"{repo_path}:{file_path.name}",
                                file_path=str(file_path),
                                line_number=line_no,
                                snippet_masked=_mask_snippet(line),
                                severity=sev,
                                detected_at=datetime.utcnow(),
                            )
                        )

        logger.info(
            "secret_scan.repo_complete",
            repo_path=repo_path,
            findings=len(findings),
        )
        return findings

    # ------------------------------------------------------------------
    # Kubernetes configmap scanning
    # ------------------------------------------------------------------

    async def scan_kubernetes_configmaps(self, namespace: str) -> list[SecretFinding]:
        """Check ConfigMaps in *namespace* for accidentally stored secrets."""
        logger.info("secret_scan.configmaps_start", namespace=namespace)
        raw = await self._kubectl_json("get", "configmaps", "-n", namespace, "-o", "json")
        if raw is None:
            return []

        findings: list[SecretFinding] = []
        items: list[dict[str, Any]] = raw.get("items", [])

        for cm in items:
            cm_name = cm.get("metadata", {}).get("name", "unknown")
            data: dict[str, str] = cm.get("data", {})
            for key, value in data.items():
                for _name, pattern, finding_type, sev in _SECRET_PATTERNS:
                    if pattern.search(value):
                        findings.append(
                            SecretFinding(
                                finding_type=finding_type,
                                location=(f"configmap/{cm_name}/{key} in {namespace}"),
                                file_path=f"configmap:{cm_name}",
                                snippet_masked=_mask_snippet(value),
                                severity=sev,
                                detected_at=datetime.utcnow(),
                            )
                        )

        logger.info(
            "secret_scan.configmaps_complete",
            namespace=namespace,
            findings=len(findings),
        )
        return findings

    # ------------------------------------------------------------------
    # Kubernetes pod env-var scanning
    # ------------------------------------------------------------------

    async def scan_environment_variables(self, namespace: str) -> list[SecretFinding]:
        """Inspect pod specs for plaintext secrets in env vars."""
        logger.info("secret_scan.envvars_start", namespace=namespace)
        raw = await self._kubectl_json("get", "pods", "-n", namespace, "-o", "json")
        if raw is None:
            return []

        findings: list[SecretFinding] = []
        for pod in raw.get("items", []):
            pod_name = pod.get("metadata", {}).get("name", "unknown")
            containers = pod.get("spec", {}).get("containers", [])
            for container in containers:
                for env in container.get("env", []):
                    value = env.get("value", "")
                    if not value:
                        continue
                    for _name, pattern, ftype, sev in _SECRET_PATTERNS:
                        if pattern.search(value):
                            findings.append(
                                SecretFinding(
                                    finding_type=ftype,
                                    location=(
                                        f"pod/{pod_name}/"
                                        f"{container.get('name', '?')}/"
                                        f"env:{env.get('name', '?')} "
                                        f"in {namespace}"
                                    ),
                                    file_path=f"pod:{pod_name}",
                                    snippet_masked=_mask_snippet(value),
                                    severity=sev,
                                    detected_at=datetime.utcnow(),
                                )
                            )

        logger.info(
            "secret_scan.envvars_complete",
            namespace=namespace,
            findings=len(findings),
        )
        return findings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_files(root: Path) -> list[Path]:
        """Collect scannable files under *root* (sync, for thread use)."""
        files: list[Path] = []
        for path in root.rglob("*"):
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.is_file() and path.suffix in _SCANNABLE_EXTENSIONS:
                files.append(path)
        return files

    @staticmethod
    async def _kubectl_json(*args: str) -> dict[str, Any] | None:
        """Run a kubectl command and return parsed JSON, or None on error."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "kubectl",
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(
                    "secret_scan.kubectl_error",
                    args=args,
                    stderr=stderr.decode(errors="replace")[:500],
                )
                return None
            result: dict[str, Any] = json.loads(stdout.decode())
            return result
        except FileNotFoundError:
            logger.error("secret_scan.kubectl_not_found")
            return None
        except Exception:
            logger.exception("secret_scan.kubectl_unexpected")
            return None
