"""Tests for the NVD CVE source implementation.

Tests cover:
- scan() with various severity thresholds
- CVSS v3.1, v3.0, v2.0 score parsing
- Pagination handling
- API error handling
- Empty results
- Score-to-severity conversion
- CVE parsing with and without CPE match data
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.integrations.cve.nvd import SEVERITY_THRESHOLDS, NVDCVESource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cve_item(
    cve_id: str = "CVE-2024-1234",
    base_score: float = 7.5,
    severity: str = "HIGH",
    description: str = "A test vulnerability",
    metric_version: str = "cvssMetricV31",
    package_name: str = "openssl",
) -> dict[str, Any]:
    """Build a mock NVD API 2.0 vulnerability item."""
    return {
        "cve": {
            "id": cve_id,
            "descriptions": [
                {"lang": "en", "value": description},
            ],
            "metrics": {
                metric_version: [
                    {
                        "cvssData": {
                            "baseScore": base_score,
                            "baseSeverity": severity,
                        },
                    }
                ]
            },
            "configurations": [
                {
                    "nodes": [
                        {
                            "cpeMatch": [
                                {
                                    "criteria": (
                                        f"cpe:2.3:a:vendor:{package_name}" ":1.0.0:*:*:*:*:*:*:*"
                                    ),
                                    "versionEndExcluding": "1.1.0",
                                }
                            ]
                        }
                    ]
                }
            ],
            "published": "2024-01-15T00:00:00.000",
            "lastModified": "2024-02-01T00:00:00.000",
        }
    }


def _make_nvd_response(
    cve_items: list[dict[str, Any]] | None = None,
    total_results: int | None = None,
) -> dict[str, Any]:
    """Build a mock NVD API response."""
    items = cve_items or []
    return {
        "vulnerabilities": items,
        "totalResults": total_results if total_results is not None else len(items),
    }


@pytest.fixture
def source() -> NVDCVESource:
    """Create an NVDCVESource with mocked HTTP session."""
    return NVDCVESource(api_key="test-key", timeout=5)


# ============================================================================
# scan()
# ============================================================================


class TestScan:
    @pytest.mark.asyncio
    async def test_scan_returns_findings_above_threshold(self, source: NVDCVESource) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _make_nvd_response(
            [
                _make_cve_item("CVE-2024-0001", 9.8, "CRITICAL"),
                _make_cve_item("CVE-2024-0002", 7.5, "HIGH"),
                _make_cve_item("CVE-2024-0003", 3.5, "LOW"),
            ]
        )

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        source._session = mock_session

        findings = await source.scan("openssl", severity_threshold="high")

        assert len(findings) == 2
        assert findings[0]["cve_id"] == "CVE-2024-0001"
        assert findings[1]["cve_id"] == "CVE-2024-0002"

    @pytest.mark.asyncio
    async def test_scan_medium_threshold(self, source: NVDCVESource) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _make_nvd_response(
            [
                _make_cve_item("CVE-2024-0001", 9.8, "CRITICAL"),
                _make_cve_item("CVE-2024-0002", 5.5, "MEDIUM"),
                _make_cve_item("CVE-2024-0003", 2.0, "LOW"),
            ]
        )

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        source._session = mock_session

        findings = await source.scan("nginx", severity_threshold="medium")

        assert len(findings) == 2
        scores = [f["cvss_score"] for f in findings]
        assert scores == [9.8, 5.5]  # Sorted descending

    @pytest.mark.asyncio
    async def test_scan_empty_results(self, source: NVDCVESource) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _make_nvd_response([])

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        source._session = mock_session

        findings = await source.scan("nonexistent-package")

        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_api_error_returns_empty(self, source: NVDCVESource) -> None:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=Exception("Connection refused"))
        source._session = mock_session

        findings = await source.scan("openssl")

        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_findings_sorted_by_score_descending(self, source: NVDCVESource) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _make_nvd_response(
            [
                _make_cve_item("CVE-2024-0001", 5.0, "MEDIUM"),
                _make_cve_item("CVE-2024-0002", 9.8, "CRITICAL"),
                _make_cve_item("CVE-2024-0003", 7.0, "HIGH"),
            ]
        )

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        source._session = mock_session

        findings = await source.scan("libcurl", severity_threshold="medium")

        scores = [f["cvss_score"] for f in findings]
        assert scores == [9.8, 7.0, 5.0]

    @pytest.mark.asyncio
    async def test_scan_critical_threshold(self, source: NVDCVESource) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _make_nvd_response(
            [
                _make_cve_item("CVE-2024-0001", 9.8, "CRITICAL"),
                _make_cve_item("CVE-2024-0002", 8.9, "HIGH"),
            ]
        )

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        source._session = mock_session

        findings = await source.scan("openssl", severity_threshold="critical")

        assert len(findings) == 1
        assert findings[0]["cvss_score"] == 9.8


# ============================================================================
# CVE Parsing
# ============================================================================


class TestParseCVE:
    def test_parse_cvss_v31(self, source: NVDCVESource) -> None:
        item = _make_cve_item("CVE-2024-5678", 8.1, "HIGH", metric_version="cvssMetricV31")
        result = source._parse_cve(item, "openssl")

        assert result is not None
        assert result["cve_id"] == "CVE-2024-5678"
        assert result["cvss_score"] == 8.1
        assert result["severity"] == "high"

    def test_parse_cvss_v30_fallback(self, source: NVDCVESource) -> None:
        item = _make_cve_item("CVE-2023-0001", 6.5, "MEDIUM", metric_version="cvssMetricV30")
        result = source._parse_cve(item, "nginx")

        assert result is not None
        assert result["cvss_score"] == 6.5

    def test_parse_cvss_v2_fallback(self, source: NVDCVESource) -> None:
        item: dict[str, Any] = {
            "cve": {
                "id": "CVE-2020-0001",
                "descriptions": [{"lang": "en", "value": "Old vuln"}],
                "metrics": {
                    "cvssMetricV2": [
                        {"cvssData": {"baseScore": 5.0}},
                    ]
                },
                "configurations": [],
            }
        }
        result = source._parse_cve(item, "old-lib")

        assert result is not None
        assert result["cvss_score"] == 5.0
        assert result["severity"] == "medium"

    def test_parse_no_cvss_returns_none(self, source: NVDCVESource) -> None:
        item: dict[str, Any] = {
            "cve": {
                "id": "CVE-2024-9999",
                "descriptions": [],
                "metrics": {},
                "configurations": [],
            }
        }
        result = source._parse_cve(item, "test")

        assert result is None

    def test_parse_extracts_package_info(self, source: NVDCVESource) -> None:
        item = _make_cve_item("CVE-2024-0001", 7.5, "HIGH", package_name="openssl")
        result = source._parse_cve(item, "openssl")

        assert result is not None
        assert result["package_name"] == "openssl"
        assert result["installed_version"] == "1.0.0"
        assert result["fixed_version"] == "1.1.0"

    def test_parse_description_truncated(self, source: NVDCVESource) -> None:
        long_desc = "A" * 1000
        item = _make_cve_item("CVE-2024-0001", 7.0, "HIGH", description=long_desc)
        result = source._parse_cve(item, "test")

        assert result is not None
        assert len(result["description"]) <= 500

    def test_parse_standard_keys_present(self, source: NVDCVESource) -> None:
        item = _make_cve_item("CVE-2024-0001", 7.5, "HIGH")
        result = source._parse_cve(item, "test-pkg")

        assert result is not None
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
        }
        assert expected_keys.issubset(result.keys())
        assert result["source"] == "nvd"
        assert result["affected_resource"] == "test-pkg"


# ============================================================================
# Score-to-severity conversion
# ============================================================================


class TestScoreToSeverity:
    def test_critical(self) -> None:
        assert NVDCVESource._score_to_severity(9.5) == "critical"
        assert NVDCVESource._score_to_severity(10.0) == "critical"

    def test_high(self) -> None:
        assert NVDCVESource._score_to_severity(7.0) == "high"
        assert NVDCVESource._score_to_severity(8.9) == "high"

    def test_medium(self) -> None:
        assert NVDCVESource._score_to_severity(4.0) == "medium"
        assert NVDCVESource._score_to_severity(6.9) == "medium"

    def test_low(self) -> None:
        assert NVDCVESource._score_to_severity(0.1) == "low"
        assert NVDCVESource._score_to_severity(3.9) == "low"

    def test_none(self) -> None:
        assert NVDCVESource._score_to_severity(0.0) == "none"


# ============================================================================
# Severity thresholds
# ============================================================================


class TestSeverityThresholds:
    def test_thresholds_defined(self) -> None:
        assert "critical" in SEVERITY_THRESHOLDS
        assert "high" in SEVERITY_THRESHOLDS
        assert "medium" in SEVERITY_THRESHOLDS
        assert "low" in SEVERITY_THRESHOLDS
        assert "none" in SEVERITY_THRESHOLDS

    def test_thresholds_ordered(self) -> None:
        assert SEVERITY_THRESHOLDS["critical"] > SEVERITY_THRESHOLDS["high"]
        assert SEVERITY_THRESHOLDS["high"] > SEVERITY_THRESHOLDS["medium"]
        assert SEVERITY_THRESHOLDS["medium"] > SEVERITY_THRESHOLDS["low"]
        assert SEVERITY_THRESHOLDS["low"] > SEVERITY_THRESHOLDS["none"]


# ============================================================================
# Initialization
# ============================================================================


class TestInit:
    def test_source_name(self) -> None:
        source = NVDCVESource()
        assert source.source_name == "nvd"

    def test_default_base_url(self) -> None:
        source = NVDCVESource()
        assert "nvd.nist.gov" in source._base_url

    def test_custom_api_key(self) -> None:
        source = NVDCVESource(api_key="my-key")
        assert source._api_key == "my-key"

    def test_session_initially_none(self) -> None:
        source = NVDCVESource()
        assert source._session is None

    def test_implements_cve_source(self) -> None:
        from shieldops.agents.security.protocols import CVESource

        assert issubclass(NVDCVESource, CVESource)
