"""Tests for OS vendor advisory feeds (F6)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.integrations.cve.os_advisories import (
    RedHatRHSASource,
    UbuntuUSNSource,
)


class TestUbuntuUSNSource:
    @pytest.fixture
    def source(self):
        return UbuntuUSNSource()

    def test_source_name(self, source):
        assert source.source_name == "ubuntu_usn"

    @pytest.mark.asyncio
    async def test_scan_with_cves(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "notices": [
                {
                    "id": "USN-6789-1",
                    "title": "OpenSSL vulnerability",
                    "description": "A flaw in OpenSSL",
                    "published": "2024-01-01",
                    "priority": "high",
                    "cves": ["CVE-2024-1111", "CVE-2024-2222"],
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("openssl", "medium")
        assert len(findings) == 2
        assert findings[0]["cve_id"] == "CVE-2024-1111"
        assert findings[0]["source"] == "ubuntu_usn"
        assert findings[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_scan_no_cves(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "notices": [
                {
                    "id": "USN-1234-1",
                    "title": "Bug fix",
                    "description": "",
                    "published": "2024-01-01",
                    "priority": "medium",
                    "cves": [],
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("pkg", "low")
        assert len(findings) == 1
        assert findings[0]["cve_id"] == "USN-1234-1"

    @pytest.mark.asyncio
    async def test_scan_empty(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"notices": []}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("nonexistent")
        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_error(self, source):
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Network error")
        source._client = mock_client
        findings = await source.scan("openssl")
        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_severity_filter(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "notices": [
                {
                    "id": "USN-1",
                    "title": "Low",
                    "priority": "low",
                    "cves": ["CVE-2024-0001"],
                    "published": "",
                    "description": "",
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("pkg", "high")
        assert len(findings) == 0

    def test_priority_to_severity(self):
        assert UbuntuUSNSource._priority_to_severity("critical") == "critical"
        assert UbuntuUSNSource._priority_to_severity("high") == "high"
        assert UbuntuUSNSource._priority_to_severity("medium") == "medium"
        assert UbuntuUSNSource._priority_to_severity("low") == "low"
        assert UbuntuUSNSource._priority_to_severity("negligible") == "low"
        assert UbuntuUSNSource._priority_to_severity("unknown") == "medium"

    def test_severity_to_score(self):
        assert UbuntuUSNSource._severity_to_score("critical") == 9.5
        assert UbuntuUSNSource._severity_to_score("high") == 7.5
        assert UbuntuUSNSource._severity_to_score("medium") == 5.0
        assert UbuntuUSNSource._severity_to_score("low") == 2.0

    @pytest.mark.asyncio
    async def test_close(self, source):
        mock_client = AsyncMock()
        source._client = mock_client
        await source.close()
        assert source._client is None

    @pytest.mark.asyncio
    async def test_scan_cve_dict_format(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "notices": [
                {
                    "id": "USN-5555-1",
                    "title": "Test",
                    "priority": "critical",
                    "cves": [{"id": "CVE-2024-5555"}],
                    "published": "2024-06-01",
                    "description": "",
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("test-pkg", "medium")
        assert len(findings) == 1
        assert findings[0]["cve_id"] == "CVE-2024-5555"


class TestRedHatRHSASource:
    @pytest.fixture
    def source(self):
        return RedHatRHSASource()

    def test_source_name(self, source):
        assert source.source_name == "redhat_rhsa"

    @pytest.mark.asyncio
    async def test_scan_success(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "CVE": "CVE-2024-3333",
                "severity": "important",
                "cvss3_score": 8.1,
                "RHSA": "RHSA-2024:001",
                "affected_package": "openssl",
                "bugzilla_description": "OpenSSL flaw",
                "public_date": "2024-01-15",
            }
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("openssl", "medium")
        assert len(findings) == 1
        assert findings[0]["cve_id"] == "CVE-2024-3333"
        assert findings[0]["severity"] == "high"
        assert findings[0]["cvss_score"] == 8.1
        assert findings[0]["source"] == "redhat_rhsa"

    @pytest.mark.asyncio
    async def test_scan_moderate_severity(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "CVE": "CVE-2024-4444",
                "severity": "moderate",
                "cvss3_score": 5.5,
                "public_date": "2024-02-01",
            }
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("pkg", "low")
        assert len(findings) == 1
        assert findings[0]["severity"] == "medium"

    @pytest.mark.asyncio
    async def test_scan_empty(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("nothing")
        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_error(self, source):
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("timeout")
        source._client = mock_client
        findings = await source.scan("pkg")
        assert findings == []

    @pytest.mark.asyncio
    async def test_scan_string_cvss_score(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"CVE": "CVE-2024-5555", "severity": "low", "cvss3_score": "3.5"}
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("pkg", "low")
        assert findings[0]["cvss_score"] == 3.5

    @pytest.mark.asyncio
    async def test_scan_no_cvss_score(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"CVE": "CVE-2024-6666", "severity": "critical"}]
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("pkg", "medium")
        assert findings[0]["cvss_score"] == 9.5

    @pytest.mark.asyncio
    async def test_scan_dict_response(self, source):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"CVE": "CVE-2024-7777", "severity": "high", "cvss3_score": 7.0}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        source._client = mock_client

        findings = await source.scan("pkg", "medium")
        assert len(findings) == 1

    def test_severity_to_score(self):
        assert RedHatRHSASource._severity_to_score("critical") == 9.5
        assert RedHatRHSASource._severity_to_score("high") == 7.5

    @pytest.mark.asyncio
    async def test_close(self, source):
        mock_client = AsyncMock()
        source._client = mock_client
        await source.close()
        assert source._client is None
