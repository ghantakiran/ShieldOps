"""Tests for Git repository security scanners (gitleaks and osv-scanner).

Tests cover:
- GitSecretScanner: initialization, scan, severity classification, redaction
- GitDependencyScanner: initialization, scan, severity determination, fixed version
- Error handling: timeout, binary not found, JSON parse errors, unexpected exit codes
"""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from shieldops.agents.security.protocols import ScannerType
from shieldops.integrations.scanners.git_scanner import (
    GitDependencyScanner,
    GitSecretScanner,
)


def _make_gitleaks_finding(
    rule_id: str = "generic-api-key",
    file: str = "config.py",
    secret: str = "sk_live_abc123",
    match: str = "API_KEY=sk_live_abc123",
) -> dict[str, Any]:
    return {
        "RuleID": rule_id,
        "File": file,
        "Secret": secret,
        "Match": match,
        "StartLine": 10,
        "EndLine": 10,
        "Commit": "abc123",
        "Author": "dev@example.com",
        "Date": "2024-01-15",
        "Tags": [],
        "Entropy": 3.5,
    }


def _make_osv_result(
    vuln_id: str = "GHSA-1234",
    cve_alias: str | None = "CVE-2024-1234",
    pkg_name: str = "requests",
    pkg_version: str = "2.28.0",
    severity_score: float | None = 7.5,
    fixed_version: str | None = "2.29.0",
) -> dict[str, Any]:
    """Build a mock osv-scanner JSON result."""
    aliases = [cve_alias] if cve_alias else []
    severity_entries = []
    if severity_score is not None:
        severity_entries = [{"type": "CVSS_V3", "score": f"CVSS:3.1/{severity_score}"}]

    affected = []
    if fixed_version:
        affected = [
            {
                "package": {"name": pkg_name},
                "ranges": [{"events": [{"fixed": fixed_version}]}],
            }
        ]

    return {
        "results": [
            {
                "source": {"path": "requirements.txt"},
                "packages": [
                    {
                        "package": {
                            "name": pkg_name,
                            "version": pkg_version,
                            "ecosystem": "PyPI",
                        },
                        "vulnerabilities": [
                            {
                                "id": vuln_id,
                                "aliases": aliases,
                                "summary": f"Test vulnerability in {pkg_name}",
                                "details": "Detailed description of the vulnerability",
                                "severity": severity_entries,
                                "affected": affected,
                                "references": [{"url": "https://example.com"}],
                            }
                        ],
                    }
                ],
            }
        ],
    }


@pytest.fixture
def secret_scanner() -> GitSecretScanner:
    return GitSecretScanner(timeout=10)


@pytest.fixture
def dep_scanner() -> GitDependencyScanner:
    return GitDependencyScanner(timeout=10)


# ============================================================================
# GitSecretScanner - Initialization
# ============================================================================


class TestGitSecretScannerInit:
    def test_scanner_name(self) -> None:
        scanner = GitSecretScanner()
        assert scanner.scanner_name == "gitleaks"

    def test_scanner_type(self) -> None:
        assert GitSecretScanner.scanner_type == ScannerType.SECRET

    def test_defaults(self) -> None:
        scanner = GitSecretScanner()
        assert scanner._gitleaks_path == "gitleaks"
        assert scanner._timeout == 300
        assert scanner._config_path is None

    def test_custom_config(self) -> None:
        scanner = GitSecretScanner(config_path="/etc/gitleaks.toml")
        assert scanner._config_path == "/etc/gitleaks.toml"


# ============================================================================
# GitSecretScanner - Scan
# ============================================================================


class TestGitSecretScannerScan:
    @pytest.mark.asyncio
    async def test_scan_returns_findings(self, secret_scanner: GitSecretScanner) -> None:
        raw = [_make_gitleaks_finding()]
        mock_proc = AsyncMock()
        mock_proc.returncode = 1  # 1 = findings present
        mock_proc.communicate = AsyncMock(return_value=(json.dumps(raw).encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await secret_scanner.scan("/repo/path")

        assert len(findings) == 1
        assert "***REDACTED***" in findings[0]["description"]

    @pytest.mark.asyncio
    async def test_scan_clean_repo_returns_empty(self, secret_scanner: GitSecretScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0  # clean
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await secret_scanner.scan("/clean/repo")

        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_error_exit_returns_empty(self, secret_scanner: GitSecretScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 2  # error
        mock_proc.communicate = AsyncMock(return_value=(b"", b"fatal error"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await secret_scanner.scan("/repo")

        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_timeout_returns_empty(self, secret_scanner: GitSecretScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await secret_scanner.scan("/slow/repo")

        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_binary_not_found(self, secret_scanner: GitSecretScanner) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            findings = await secret_scanner.scan("/repo")

        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_bad_json(self, secret_scanner: GitSecretScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"not json", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await secret_scanner.scan("/repo")

        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_with_branch_option(self, secret_scanner: GitSecretScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await secret_scanner.scan("/repo", branch="main")

        call_args = mock_exec.call_args[0]
        assert "--branch" in call_args
        assert "main" in call_args


# ============================================================================
# GitSecretScanner - Severity classification
# ============================================================================


class TestSecretSeverityClassification:
    def test_aws_access_key_is_critical(self) -> None:
        assert GitSecretScanner._classify_severity("aws-access-key-id", []) == "critical"

    def test_private_key_is_critical(self) -> None:
        assert GitSecretScanner._classify_severity("private-key", []) == "critical"

    def test_generic_api_key_is_high(self) -> None:
        assert GitSecretScanner._classify_severity("generic-api-key", []) == "high"

    def test_slack_token_is_high(self) -> None:
        assert GitSecretScanner._classify_severity("slack-token", []) == "high"

    def test_keyword_heuristic_token(self) -> None:
        assert GitSecretScanner._classify_severity("some-token-thing", []) == "high"

    def test_keyword_heuristic_password(self) -> None:
        assert GitSecretScanner._classify_severity("my-password-rule", []) == "high"

    def test_unknown_rule_is_medium(self) -> None:
        assert GitSecretScanner._classify_severity("unrecognized-rule", []) == "medium"


# ============================================================================
# GitDependencyScanner - Initialization
# ============================================================================


class TestGitDependencyScannerInit:
    def test_scanner_name(self) -> None:
        scanner = GitDependencyScanner()
        assert scanner.scanner_name == "osv-scanner"

    def test_scanner_type(self) -> None:
        assert GitDependencyScanner.scanner_type == ScannerType.CVE


# ============================================================================
# GitDependencyScanner - Scan
# ============================================================================


class TestGitDependencyScannerScan:
    @pytest.mark.asyncio
    async def test_scan_returns_findings(self, dep_scanner: GitDependencyScanner) -> None:
        raw = _make_osv_result()
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(json.dumps(raw).encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await dep_scanner.scan("/project")

        assert len(findings) == 1
        assert "CVE-2024-1234" in findings[0]["title"]
        assert findings[0]["scanner_type"] == ScannerType.CVE.value

    @pytest.mark.asyncio
    async def test_scan_clean_returns_empty(self, dep_scanner: GitDependencyScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await dep_scanner.scan("/clean-project")

        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_with_lockfile_option(self, dep_scanner: GitDependencyScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await dep_scanner.scan("/project", lockfile="package-lock.json")

        call_args = mock_exec.call_args[0]
        assert "--lockfile" in call_args
        assert "package-lock.json" in call_args

    @pytest.mark.asyncio
    async def test_scan_hard_error_returns_empty(self, dep_scanner: GitDependencyScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 128
        mock_proc.communicate = AsyncMock(return_value=(b"", b"no lockfile"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await dep_scanner.scan("/project")

        assert findings == []


# ============================================================================
# GitDependencyScanner - Severity determination
# ============================================================================


class TestDependencySeverity:
    def test_critical_from_cvss(self) -> None:
        assert (
            GitDependencyScanner._determine_severity(
                {"severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/9.8"}]}
            )
            == "critical"
        )

    def test_high_from_cvss(self) -> None:
        assert (
            GitDependencyScanner._determine_severity(
                {"severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/7.5"}]}
            )
            == "high"
        )

    def test_medium_from_cvss(self) -> None:
        assert (
            GitDependencyScanner._determine_severity(
                {"severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/5.0"}]}
            )
            == "medium"
        )

    def test_low_from_cvss(self) -> None:
        assert (
            GitDependencyScanner._determine_severity(
                {"severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/2.0"}]}
            )
            == "low"
        )

    def test_fallback_to_database_specific(self) -> None:
        assert (
            GitDependencyScanner._determine_severity({"database_specific": {"severity": "HIGH"}})
            == "high"
        )

    def test_default_medium(self) -> None:
        assert GitDependencyScanner._determine_severity({}) == "medium"

    def test_fixed_version_extracted(self) -> None:
        vuln = {
            "affected": [
                {
                    "package": {"name": "requests"},
                    "ranges": [{"events": [{"fixed": "2.29.0"}]}],
                }
            ],
        }
        assert GitDependencyScanner._get_fixed_version(vuln, "requests") == "2.29.0"

    def test_fixed_version_none_when_missing(self) -> None:
        assert GitDependencyScanner._get_fixed_version({}, "requests") is None
