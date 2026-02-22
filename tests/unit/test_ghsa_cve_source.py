"""Tests for GitHub Advisory Database CVE source (F5)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.integrations.cve.ghsa import (
    ECOSYSTEM_MAP,
    SEVERITY_MAP,
    GHSACVESource,
)


class TestGHSACVESource:
    @pytest.fixture
    def source(self):
        return GHSACVESource(token="test-token")

    @pytest.fixture
    def mock_response(self):
        return {
            "data": {
                "securityVulnerabilities": {
                    "nodes": [
                        {
                            "advisory": {
                                "ghsaId": "GHSA-1234-5678",
                                "summary": "SQL injection in django",
                                "description": "Vuln description",
                                "severity": "HIGH",
                                "cvss": {"score": 8.5, "vectorString": "CVSS:3.1/AV:N"},
                                "identifiers": [
                                    {"type": "CVE", "value": "CVE-2024-1234"},
                                    {"type": "GHSA", "value": "GHSA-1234-5678"},
                                ],
                                "publishedAt": "2024-01-01T00:00:00Z",
                                "updatedAt": "2024-01-15T00:00:00Z",
                                "references": [{"url": "https://example.com"}],
                            },
                            "package": {"name": "django", "ecosystem": "PIP"},
                            "vulnerableVersionRange": "< 4.2.8",
                            "firstPatchedVersion": {"identifier": "4.2.8"},
                        }
                    ]
                }
            }
        }

    def test_source_name(self, source):
        assert source.source_name == "ghsa"

    def test_parse_resource_id_with_ecosystem(self, source):
        pkg, eco = source._parse_resource_id("pip:django")
        assert pkg == "django"
        assert eco == "PIP"

    def test_parse_resource_id_without_ecosystem(self, source):
        pkg, eco = source._parse_resource_id("django")
        assert pkg == "django"
        assert eco is None

    def test_parse_resource_id_npm(self, source):
        pkg, eco = source._parse_resource_id("npm:express")
        assert pkg == "express"
        assert eco == "NPM"

    def test_parse_resource_id_go(self, source):
        pkg, eco = source._parse_resource_id("go:github.com/gin-gonic/gin")
        assert eco == "GO"

    def test_ecosystem_map_coverage(self):
        assert "pip" in ECOSYSTEM_MAP
        assert "npm" in ECOSYSTEM_MAP
        assert "go" in ECOSYSTEM_MAP
        assert "maven" in ECOSYSTEM_MAP
        assert "rust" in ECOSYSTEM_MAP

    def test_severity_map(self):
        assert SEVERITY_MAP["CRITICAL"] == "critical"
        assert SEVERITY_MAP["HIGH"] == "high"
        assert SEVERITY_MAP["MODERATE"] == "medium"
        assert SEVERITY_MAP["LOW"] == "low"

    @pytest.mark.asyncio
    async def test_scan_success(self, source, mock_response):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("pip:django", "medium")
        assert len(findings) == 1
        assert findings[0]["cve_id"] == "CVE-2024-1234"
        assert findings[0]["severity"] == "high"
        assert findings[0]["cvss_score"] == 8.5
        assert findings[0]["fixed_version"] == "4.2.8"
        assert findings[0]["source"] == "ghsa"

    @pytest.mark.asyncio
    async def test_scan_empty(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"securityVulnerabilities": {"nodes": []}}}
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("nonexistent-pkg")
        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_error(self, source):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Network error")
        source._client = mock_client

        findings = await source.scan("django")
        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_severity_filter(self, source, mock_response):
        # Set score below critical threshold
        mock_response["data"]["securityVulnerabilities"]["nodes"][0]["advisory"]["cvss"][
            "score"
        ] = 8.5
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("django", "critical")
        assert len(findings) == 0  # 8.5 < 9.0

    def test_parse_advisory_no_cve(self, source):
        node = {
            "advisory": {
                "ghsaId": "GHSA-abcd",
                "summary": "Test",
                "severity": "MODERATE",
                "cvss": {"score": 5.0},
                "identifiers": [{"type": "GHSA", "value": "GHSA-abcd"}],
                "publishedAt": "",
                "updatedAt": "",
            },
            "package": {"name": "pkg", "ecosystem": "NPM"},
            "vulnerableVersionRange": "< 1.0",
            "firstPatchedVersion": None,
        }
        result = source._parse_advisory(node, "pkg")
        assert result["cve_id"] == "GHSA-abcd"
        assert result["fixed_version"] == ""

    def test_parse_advisory_no_cvss(self, source):
        node = {
            "advisory": {
                "ghsaId": "GHSA-xyz",
                "summary": "Low severity",
                "severity": "LOW",
                "cvss": None,
                "identifiers": [],
                "publishedAt": "",
                "updatedAt": "",
            },
            "package": {"name": "pkg", "ecosystem": "PIP"},
            "vulnerableVersionRange": "",
            "firstPatchedVersion": None,
        }
        result = source._parse_advisory(node, "pkg")
        assert result["cvss_score"] == 2.0  # Inferred from LOW

    @pytest.mark.asyncio
    async def test_scan_graphql_errors(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "errors": [{"message": "rate limited"}],
            "data": {"securityVulnerabilities": {"nodes": []}},
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("django")
        assert findings == []

    @pytest.mark.asyncio
    async def test_close(self, source):
        mock_client = AsyncMock()
        source._client = mock_client
        await source.close()
        assert source._client is None
        mock_client.aclose.assert_called_once()

    def test_parse_advisory_ghsa_id(self, source):
        node = {
            "advisory": {
                "ghsaId": "GHSA-test",
                "summary": "Test vuln",
                "severity": "HIGH",
                "cvss": {"score": 7.5},
                "identifiers": [{"type": "CVE", "value": "CVE-2024-9999"}],
                "publishedAt": "2024-06-01",
                "updatedAt": "2024-06-15",
            },
            "package": {"name": "express", "ecosystem": "NPM"},
            "vulnerableVersionRange": "< 5.0",
            "firstPatchedVersion": {"identifier": "5.0.0"},
        }
        result = source._parse_advisory(node, "npm:express")
        assert result["ghsa_id"] == "GHSA-test"
        assert result["ecosystem"] == "NPM"
