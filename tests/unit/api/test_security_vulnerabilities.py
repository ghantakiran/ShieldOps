"""Tests for the GET /security/scans/{scan_id}/vulnerabilities endpoint."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from shieldops.api.app import app
from shieldops.api.routes import security


@pytest.fixture(autouse=True)
def _reset_runner():
    """Reset the security runner between tests."""
    original = security._runner
    security._runner = None
    yield
    security._runner = original


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def _make_cve(cve_id="CVE-2024-1234", severity="critical"):
    cve = MagicMock()
    cve.severity = severity
    cve.model_dump.return_value = {
        "cve_id": cve_id,
        "severity": severity,
        "cvss_score": 9.8,
        "package_name": "openssl",
        "installed_version": "1.1.1",
        "fixed_version": "1.1.2",
    }
    return cve


def _make_mock_runner(scan=None):
    runner = MagicMock()
    runner.get_scan.return_value = scan
    return runner


class TestSecurityVulnerabilities:
    """Tests for GET /api/v1/security/scans/{scan_id}/vulnerabilities."""

    def test_returns_404_when_scan_not_found(self, client: TestClient):
        security.set_runner(_make_mock_runner(scan=None))
        resp = client.get("/api/v1/security/scans/nonexistent/vulnerabilities")
        assert resp.status_code == 404

    def test_returns_empty_list_when_no_cves(self, client: TestClient):
        scan = MagicMock()
        scan.cve_findings = []
        security.set_runner(_make_mock_runner(scan=scan))
        resp = client.get("/api/v1/security/scans/scan-1/vulnerabilities")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_all_cves(self, client: TestClient):
        scan = MagicMock()
        scan.cve_findings = [
            _make_cve("CVE-2024-0001", "critical"),
            _make_cve("CVE-2024-0002", "high"),
        ]
        security.set_runner(_make_mock_runner(scan=scan))
        resp = client.get("/api/v1/security/scans/scan-1/vulnerabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["cve_id"] == "CVE-2024-0001"

    def test_filters_by_severity(self, client: TestClient):
        scan = MagicMock()
        scan.cve_findings = [
            _make_cve("CVE-2024-0001", "critical"),
            _make_cve("CVE-2024-0002", "high"),
        ]
        security.set_runner(_make_mock_runner(scan=scan))
        resp = client.get("/api/v1/security/scans/scan-1/vulnerabilities?severity=critical")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["severity"] == "critical"

    def test_existing_scan_detail_endpoint_still_works(self, client: TestClient):
        scan = MagicMock()
        scan.model_dump.return_value = {"id": "scan-1", "status": "complete"}
        security.set_runner(_make_mock_runner(scan=scan))
        resp = client.get("/api/v1/security/scans/scan-1")
        assert resp.status_code == 200

    def test_severity_filter_returns_empty_on_no_match(self, client: TestClient):
        scan = MagicMock()
        scan.cve_findings = [_make_cve("CVE-2024-0001", "low")]
        security.set_runner(_make_mock_runner(scan=scan))
        resp = client.get("/api/v1/security/scans/scan-1/vulnerabilities?severity=critical")
        assert resp.status_code == 200
        assert resp.json() == []
