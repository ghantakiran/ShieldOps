"""Tests for the Trivy CVE scanner integration.

Tests cover:
- Initialization and class attributes
- CLI mode scanning (mock subprocess)
- Server mode scanning (mock httpx)
- Result parsing with severity threshold filtering
- CVSS score extraction (V3, V2, severity-fallback)
- Error handling (timeout, binary not found, JSON parse, HTTP errors)
- Findings sorted by CVSS score descending
"""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.integrations.scanners.trivy import (
    SEVERITY_ORDER,
    SEVERITY_THRESHOLD_MAP,
    TrivyCVESource,
)


def _make_trivy_result(
    vulns: list[dict[str, Any]],
    target: str = "nginx:1.25",
    target_type: str = "os",
) -> dict[str, Any]:
    """Build a Trivy-style JSON result dict."""
    return {
        "Results": [
            {
                "Target": target,
                "Type": target_type,
                "Vulnerabilities": vulns,
            }
        ]
    }


def _make_vuln(
    cve_id: str = "CVE-2024-1234",
    severity: str = "HIGH",
    cvss_v3: float | None = 7.5,
    pkg_name: str = "openssl",
    installed: str = "1.1.1",
    fixed: str | None = "1.1.2",
) -> dict[str, Any]:
    """Build a single Trivy vulnerability entry."""
    vuln: dict[str, Any] = {
        "VulnerabilityID": cve_id,
        "Severity": severity,
        "PkgName": pkg_name,
        "InstalledVersion": installed,
        "FixedVersion": fixed,
        "Title": f"Test vulnerability {cve_id}",
        "References": ["https://example.com/ref1"],
    }
    if cvss_v3 is not None:
        vuln["CVSS"] = {"nvd": {"V3Score": cvss_v3}}
    return vuln


@pytest.fixture
def cli_source() -> TrivyCVESource:
    """TrivyCVESource in CLI mode (no server URL)."""
    return TrivyCVESource(timeout=10, trivy_path="/usr/bin/trivy", cache_dir="/tmp/trivy-cache")


@pytest.fixture
def server_source() -> TrivyCVESource:
    """TrivyCVESource in server mode."""
    return TrivyCVESource(server_url="http://trivy:4954", timeout=10)


# ============================================================================
# Initialization
# ============================================================================


class TestInit:
    def test_source_name(self) -> None:
        source = TrivyCVESource()
        assert source.source_name == "trivy"

    def test_cli_mode_defaults(self) -> None:
        source = TrivyCVESource()
        assert source._server_url is None
        assert source._timeout == 300
        assert source._trivy_path == "trivy"
        assert source._cache_dir is None

    def test_server_mode_configured(self, server_source: TrivyCVESource) -> None:
        assert server_source._server_url == "http://trivy:4954"

    def test_custom_cli_options(self, cli_source: TrivyCVESource) -> None:
        assert cli_source._trivy_path == "/usr/bin/trivy"
        assert cli_source._cache_dir == "/tmp/trivy-cache"

    def test_implements_cve_source(self) -> None:
        from shieldops.agents.security.protocols import CVESource

        assert issubclass(TrivyCVESource, CVESource)


# ============================================================================
# CLI mode scan
# ============================================================================


class TestScanViaCLI:
    @pytest.mark.asyncio
    async def test_scan_returns_parsed_findings(self, cli_source: TrivyCVESource) -> None:
        raw = _make_trivy_result(
            [
                _make_vuln("CVE-2024-0001", "CRITICAL", 9.8),
                _make_vuln("CVE-2024-0002", "HIGH", 7.5),
            ]
        )
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(json.dumps(raw).encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await cli_source.scan("nginx:1.25", severity_threshold="high")

        assert len(findings) == 2
        assert findings[0]["cve_id"] == "CVE-2024-0001"
        assert findings[0]["cvss_score"] == pytest.approx(9.8)
        assert findings[1]["cve_id"] == "CVE-2024-0002"

    @pytest.mark.asyncio
    async def test_scan_filters_below_threshold(self, cli_source: TrivyCVESource) -> None:
        raw = _make_trivy_result(
            [
                _make_vuln("CVE-2024-0001", "CRITICAL", 9.8),
                _make_vuln("CVE-2024-0002", "LOW", 2.0),
            ]
        )
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(json.dumps(raw).encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await cli_source.scan("nginx:1.25", severity_threshold="high")

        assert len(findings) == 1
        assert findings[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_scan_cli_nonzero_exit_returns_empty(self, cli_source: TrivyCVESource) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 2
        mock_proc.communicate = AsyncMock(return_value=(b"", b"some error"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await cli_source.scan("bad-image:latest")

        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_cli_timeout_returns_empty(self, cli_source: TrivyCVESource) -> None:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await cli_source.scan("slow-image:latest")

        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_cli_binary_not_found(self, cli_source: TrivyCVESource) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            findings = await cli_source.scan("any-image:latest")

        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_cli_bad_json_returns_empty(self, cli_source: TrivyCVESource) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"not valid json", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await cli_source.scan("image:latest")

        assert findings == []

    @pytest.mark.asyncio
    async def test_cache_dir_included_in_command(self, cli_source: TrivyCVESource) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(json.dumps({"Results": []}).encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await cli_source.scan("img:1")

        call_args = mock_exec.call_args[0]
        assert "--cache-dir" in call_args
        assert "/tmp/trivy-cache" in call_args


# ============================================================================
# Server mode scan
# ============================================================================


class TestScanViaServer:
    @pytest.mark.asyncio
    async def test_server_scan_success(self, server_source: TrivyCVESource) -> None:
        raw = _make_trivy_result([_make_vuln("CVE-2024-0001", "CRITICAL", 9.8)])
        mock_response = MagicMock()
        mock_response.json.return_value = raw
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            findings = await server_source.scan("nginx:1.25")

        assert len(findings) == 1
        assert findings[0]["cve_id"] == "CVE-2024-0001"

    @pytest.mark.asyncio
    async def test_server_http_error_returns_empty(self, server_source: TrivyCVESource) -> None:
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        exc = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=exc)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            findings = await server_source.scan("nginx:1.25")

        assert findings == []

    @pytest.mark.asyncio
    async def test_server_connection_error_returns_empty(
        self, server_source: TrivyCVESource
    ) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=ConnectionError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            findings = await server_source.scan("nginx:1.25")

        assert findings == []


# ============================================================================
# Result parsing
# ============================================================================


class TestParseResults:
    def test_cvss_v3_score_extracted(self, cli_source: TrivyCVESource) -> None:
        raw = _make_trivy_result([_make_vuln("CVE-2024-0001", "HIGH", 8.1)])
        findings = cli_source._parse_results(raw, "nginx:1.25", "low")

        assert len(findings) == 1
        assert findings[0]["cvss_score"] == pytest.approx(8.1)

    def test_cvss_v2_fallback(self, cli_source: TrivyCVESource) -> None:
        vuln = _make_vuln("CVE-2024-0001", "HIGH", cvss_v3=None)
        vuln["CVSS"] = {"nvd": {"V2Score": 6.5}}
        raw = _make_trivy_result([vuln])
        findings = cli_source._parse_results(raw, "img:1", "low")

        assert findings[0]["cvss_score"] == pytest.approx(6.5)

    def test_severity_fallback_when_no_cvss(self, cli_source: TrivyCVESource) -> None:
        vuln = _make_vuln("CVE-2024-0001", "HIGH", cvss_v3=None)
        vuln.pop("CVSS", None)
        raw = _make_trivy_result([vuln])
        findings = cli_source._parse_results(raw, "img:1", "low")

        # High severity maps to 7.5 estimated CVSS
        assert findings[0]["cvss_score"] == pytest.approx(7.5)

    def test_findings_sorted_by_cvss_descending(self, cli_source: TrivyCVESource) -> None:
        raw = _make_trivy_result(
            [
                _make_vuln("CVE-LOW", "MEDIUM", 4.0),
                _make_vuln("CVE-HIGH", "CRITICAL", 9.8),
                _make_vuln("CVE-MED", "HIGH", 7.0),
            ]
        )
        findings = cli_source._parse_results(raw, "img:1", "low")
        scores = [f["cvss_score"] for f in findings]
        assert scores == [pytest.approx(9.8), pytest.approx(7.0), pytest.approx(4.0)]

    def test_empty_results(self, cli_source: TrivyCVESource) -> None:
        findings = cli_source._parse_results({"Results": []}, "img:1", "low")
        assert findings == []

    def test_finding_contains_standard_keys(self, cli_source: TrivyCVESource) -> None:
        raw = _make_trivy_result([_make_vuln()])
        findings = cli_source._parse_results(raw, "nginx:1.25", "low")

        expected_keys = {
            "cve_id",
            "severity",
            "cvss_score",
            "package_name",
            "installed_version",
            "fixed_version",
            "affected_resource",
            "description",
            "source",
            "target_type",
            "references",
        }
        assert expected_keys.issubset(findings[0].keys())
        assert findings[0]["source"] == "trivy"

    def test_cvss_score_clamped_to_10(self, cli_source: TrivyCVESource) -> None:
        vuln = _make_vuln("CVE-2024-0001", "CRITICAL", cvss_v3=None)
        vuln["CVSS"] = {"nvd": {"V3Score": 15.0}}
        raw = _make_trivy_result([vuln])
        findings = cli_source._parse_results(raw, "img:1", "low")

        assert findings[0]["cvss_score"] == pytest.approx(10.0)

    def test_unknown_severity_maps_to_low(self, cli_source: TrivyCVESource) -> None:
        raw = _make_trivy_result([_make_vuln("CVE-2024-0001", "UNKNOWN", cvss_v3=None)])
        findings = cli_source._parse_results(raw, "img:1", "low")
        assert findings[0]["severity"] == "low"


# ============================================================================
# Severity constants
# ============================================================================


class TestSeverityMaps:
    def test_severity_order_contains_all_levels(self) -> None:
        assert set(SEVERITY_ORDER.values()) == {"critical", "high", "medium", "low"}

    def test_threshold_map_ordering(self) -> None:
        assert SEVERITY_THRESHOLD_MAP["critical"] > SEVERITY_THRESHOLD_MAP["high"]
        assert SEVERITY_THRESHOLD_MAP["high"] > SEVERITY_THRESHOLD_MAP["medium"]
        assert SEVERITY_THRESHOLD_MAP["medium"] > SEVERITY_THRESHOLD_MAP["low"]

    def test_severity_to_cvss_estimates(self) -> None:
        assert TrivyCVESource._severity_to_cvss("critical") == pytest.approx(9.5)
        assert TrivyCVESource._severity_to_cvss("high") == pytest.approx(7.5)
        assert TrivyCVESource._severity_to_cvss("medium") == pytest.approx(5.0)
        assert TrivyCVESource._severity_to_cvss("low") == pytest.approx(2.5)
        assert TrivyCVESource._severity_to_cvss("bogus") == pytest.approx(0.0)
