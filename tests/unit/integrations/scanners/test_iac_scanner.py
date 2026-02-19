"""Tests for the IaC (checkov) security scanner.

Tests cover:
- Initialization and class attributes
- Scan with directory vs file target
- Single-framework and multi-framework JSON output parsing
- Severity determination (explicit, heuristic, default)
- Error handling (timeout, not found, bad JSON)
- Skip-checks and framework overrides
"""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from shieldops.agents.security.protocols import ScannerType
from shieldops.integrations.scanners.iac_scanner import (
    CHECKOV_SEVERITY_MAP,
    IaCScanner,
)


def _make_checkov_result(
    failed_checks: list[dict[str, Any]] | None = None,
    passed_checks: list[dict[str, Any]] | int = 0,
    check_type: str = "terraform",
) -> dict[str, Any]:
    """Build a single-framework checkov JSON result."""
    return {
        "check_type": check_type,
        "results": {
            "failed_checks": failed_checks or [],
            "passed_checks": passed_checks,
        },
    }


def _make_failed_check(
    check_id: str = "CKV_AWS_18",
    check_name: str = "Ensure S3 bucket has logging enabled",
    severity: str | None = None,
    file_path: str = "/main.tf",
    resource: str = "aws_s3_bucket.data",
    guideline: str = "https://docs.checkov.io/CKV_AWS_18",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "check_id": check_id,
        "name": check_name,
        "file_path": file_path,
        "resource": resource,
        "file_line_range": [10, 25],
        "guideline": guideline,
        "check": {"name": check_name, "guideline": guideline},
    }
    if severity:
        result["severity"] = severity
    return result


@pytest.fixture
def scanner() -> IaCScanner:
    return IaCScanner(timeout=10, skip_checks=["CKV_K8S_8"])


# ============================================================================
# Initialization
# ============================================================================


class TestInit:
    def test_scanner_name(self) -> None:
        assert IaCScanner.scanner_name == "checkov"

    def test_scanner_type(self) -> None:
        assert IaCScanner.scanner_type == ScannerType.IAC

    def test_defaults(self) -> None:
        s = IaCScanner()
        assert s._checkov_path == "checkov"
        assert s._timeout == 600
        assert s._skip_checks == []
        assert "terraform" in s._frameworks

    def test_custom_frameworks(self) -> None:
        s = IaCScanner(frameworks=["terraform"])
        assert s._frameworks == ["terraform"]


# ============================================================================
# Scan - happy paths
# ============================================================================


class TestScan:
    @pytest.mark.asyncio
    async def test_scan_directory_returns_findings(self, scanner: IaCScanner) -> None:
        raw = _make_checkov_result(
            failed_checks=[_make_failed_check()],
            passed_checks=5,
        )
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(json.dumps(raw).encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("/infra/terraform")

        assert len(findings) == 1
        assert findings[0]["scanner_type"] == ScannerType.IAC.value
        assert "CKV_AWS_18" in findings[0]["title"]

    @pytest.mark.asyncio
    async def test_scan_single_file_uses_file_flag(self, scanner: IaCScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(json.dumps(_make_checkov_result()).encode(), b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await scanner.scan("/infra/main.tf")

        call_args = mock_exec.call_args[0]
        assert "--file" in call_args

    @pytest.mark.asyncio
    async def test_scan_directory_uses_directory_flag(self, scanner: IaCScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(json.dumps(_make_checkov_result()).encode(), b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await scanner.scan("/infra/modules")

        call_args = mock_exec.call_args[0]
        assert "--directory" in call_args

    @pytest.mark.asyncio
    async def test_scan_multi_framework_json_list(self, scanner: IaCScanner) -> None:
        """checkov may return a JSON list with one item per framework."""
        results = [
            _make_checkov_result(
                failed_checks=[_make_failed_check("CKV_AWS_1", "Check 1")],
                check_type="terraform",
            ),
            _make_checkov_result(
                failed_checks=[_make_failed_check("CKV_K8S_1", "Check 2")],
                check_type="kubernetes",
            ),
        ]
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(json.dumps(results).encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("/infra")

        assert len(findings) == 2

    @pytest.mark.asyncio
    async def test_scan_no_output_returns_empty(self, scanner: IaCScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("/empty")

        assert findings == []

    @pytest.mark.asyncio
    async def test_skip_checks_included_in_command(self, scanner: IaCScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(json.dumps(_make_checkov_result()).encode(), b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await scanner.scan("/infra", skip_checks=["CKV_AWS_99"])

        call_args = mock_exec.call_args[0]
        assert "--skip-check" in call_args
        # Should include both instance-level and call-level skip checks
        skip_idx = list(call_args).index("--skip-check")
        combined = call_args[skip_idx + 1]
        assert "CKV_K8S_8" in combined
        assert "CKV_AWS_99" in combined


# ============================================================================
# Error handling
# ============================================================================


class TestScanErrors:
    @pytest.mark.asyncio
    async def test_timeout_returns_empty(self, scanner: IaCScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("/slow/dir")

        assert findings == []

    @pytest.mark.asyncio
    async def test_binary_not_found(self, scanner: IaCScanner) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            findings = await scanner.scan("/infra")

        assert findings == []

    @pytest.mark.asyncio
    async def test_bad_json(self, scanner: IaCScanner) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"not json{", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("/infra")

        assert findings == []


# ============================================================================
# Severity determination
# ============================================================================


class TestSeverityDetermination:
    def test_explicit_severity_used(self) -> None:
        check = _make_failed_check(severity="HIGH")
        result = IaCScanner._determine_severity(check, "CKV_AWS_18", "Some check")
        assert result == "high"

    def test_nested_check_severity(self) -> None:
        check = {"check": {"severity": "CRITICAL"}}
        result = IaCScanner._determine_severity(check, "CKV_1", "check")
        assert result == "critical"

    def test_heuristic_public_is_critical(self) -> None:
        result = IaCScanner._determine_severity({}, "CKV_AWS_1", "Ensure bucket not public")
        assert result == "critical"

    def test_heuristic_encryption_is_high(self) -> None:
        result = IaCScanner._determine_severity({}, "CKV_AWS_1", "Enable encryption at rest")
        assert result == "high"

    def test_heuristic_unrestricted_is_high(self) -> None:
        result = IaCScanner._determine_severity({}, "CKV_1", "Unrestricted security group")
        assert result == "high"

    def test_default_medium(self) -> None:
        result = IaCScanner._determine_severity({}, "CKV_MISC", "Some innocuous check")
        assert result == "medium"

    def test_checkov_severity_map_contains_all(self) -> None:
        expected = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
        assert set(CHECKOV_SEVERITY_MAP.keys()) == expected


# ============================================================================
# Parse results
# ============================================================================


class TestParseResults:
    def test_finding_keys_present(self, scanner: IaCScanner) -> None:
        raw = _make_checkov_result(failed_checks=[_make_failed_check()])
        findings = scanner._parse_results(raw, "/infra")

        expected_keys = {
            "finding_id",
            "scanner_type",
            "severity",
            "title",
            "description",
            "affected_resource",
            "remediation",
            "metadata",
        }
        assert expected_keys.issubset(findings[0].keys())

    def test_guideline_used_as_remediation(self, scanner: IaCScanner) -> None:
        check = _make_failed_check(guideline="https://docs.checkov.io/CKV_AWS_18")
        raw = _make_checkov_result(failed_checks=[check])
        findings = scanner._parse_results(raw, "/infra")

        assert findings[0]["remediation"] == "https://docs.checkov.io/CKV_AWS_18"

    def test_fallback_remediation_when_no_guideline(self, scanner: IaCScanner) -> None:
        check = _make_failed_check(guideline="")
        raw = _make_checkov_result(failed_checks=[check])
        findings = scanner._parse_results(raw, "/infra")

        assert "Fix CKV_AWS_18" in findings[0]["remediation"]

    def test_findings_sorted_by_severity(self, scanner: IaCScanner) -> None:
        checks = [
            _make_failed_check("CKV_1", "low check", severity="LOW"),
            _make_failed_check("CKV_2", "critical check", severity="CRITICAL"),
            _make_failed_check("CKV_3", "high check", severity="HIGH"),
        ]
        raw = _make_checkov_result(failed_checks=checks)
        findings = scanner._parse_results(raw, "/infra")

        severities = [f["severity"] for f in findings]
        assert severities == ["critical", "high", "low"]
