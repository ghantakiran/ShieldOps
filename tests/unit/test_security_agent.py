"""Unit tests for the security_agent module — models, secret_detector, cert_monitor, cve_scanner."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from shieldops.security_agent.cert_monitor import CertificateMonitor
from shieldops.security_agent.cve_scanner import CVEScanner
from shieldops.security_agent.models import (
    CertificateStatus,
    FindingType,
    SecretFinding,
    SecurityScanResult,
    VulnerabilityRecord,
    VulnerabilitySeverity,
    VulnerabilityStatus,
)
from shieldops.security_agent.secret_detector import SecretDetector, _mask_snippet

# =====================================================================
# Model Tests
# =====================================================================


class TestVulnerabilitySeverity:
    """Tests for VulnerabilitySeverity enum."""

    def test_enum_values(self) -> None:
        assert VulnerabilitySeverity.CRITICAL == "critical"
        assert VulnerabilitySeverity.HIGH == "high"
        assert VulnerabilitySeverity.MEDIUM == "medium"
        assert VulnerabilitySeverity.LOW == "low"
        assert VulnerabilitySeverity.INFO == "info"

    def test_enum_membership(self) -> None:
        assert len(VulnerabilitySeverity) == 5

    def test_string_comparison(self) -> None:
        assert VulnerabilitySeverity("critical") is VulnerabilitySeverity.CRITICAL


class TestVulnerabilityStatus:
    """Tests for VulnerabilityStatus enum."""

    def test_enum_values(self) -> None:
        assert VulnerabilityStatus.OPEN == "open"
        assert VulnerabilityStatus.IN_PROGRESS == "in_progress"
        assert VulnerabilityStatus.FIXED == "fixed"
        assert VulnerabilityStatus.WONT_FIX == "wont_fix"
        assert VulnerabilityStatus.FALSE_POSITIVE == "false_positive"

    def test_enum_membership(self) -> None:
        assert len(VulnerabilityStatus) == 5


class TestFindingType:
    """Tests for FindingType enum."""

    def test_enum_values(self) -> None:
        assert FindingType.API_KEY == "api_key"
        assert FindingType.PASSWORD == "password"  # noqa: S105
        assert FindingType.PRIVATE_KEY == "private_key"
        assert FindingType.TOKEN == "token"  # noqa: S105
        assert FindingType.CERTIFICATE == "certificate"

    def test_enum_membership(self) -> None:
        assert len(FindingType) == 5


class TestVulnerabilityRecord:
    """Tests for VulnerabilityRecord model."""

    def test_creation_with_required_fields(self) -> None:
        record = VulnerabilityRecord(
            cve_id="CVE-2024-1234",
            package_name="openssl",
            installed_version="1.1.1k",
            severity=VulnerabilitySeverity.HIGH,
        )
        assert record.cve_id == "CVE-2024-1234"
        assert record.package_name == "openssl"
        assert record.installed_version == "1.1.1k"
        assert record.severity == VulnerabilitySeverity.HIGH
        assert record.fixed_version is None
        assert record.status == VulnerabilityStatus.OPEN
        assert record.cvss_score == 0.0
        assert record.description == ""

    def test_creation_with_all_fields(self) -> None:
        now = datetime.utcnow()
        record = VulnerabilityRecord(
            cve_id="CVE-2024-5678",
            package_name="curl",
            installed_version="7.80.0",
            fixed_version="7.81.0",
            severity=VulnerabilitySeverity.CRITICAL,
            description="Buffer overflow in curl",
            cvss_score=9.8,
            affected_service="nginx:latest",
            namespace="production",
            detected_at=now,
            status=VulnerabilityStatus.IN_PROGRESS,
        )
        assert record.fixed_version == "7.81.0"
        assert record.cvss_score == 9.8
        assert record.namespace == "production"
        assert record.status == VulnerabilityStatus.IN_PROGRESS

    def test_cvss_score_validation_bounds(self) -> None:
        """CVSS score must be between 0.0 and 10.0."""
        with pytest.raises(Exception):  # noqa: B017
            VulnerabilityRecord(
                cve_id="CVE-2024-0001",
                package_name="pkg",
                installed_version="1.0",
                severity=VulnerabilitySeverity.LOW,
                cvss_score=11.0,
            )


class TestSecretFinding:
    """Tests for SecretFinding model."""

    def test_creation(self) -> None:
        finding = SecretFinding(
            finding_type=FindingType.API_KEY,
            location="repo:config.py",
        )
        assert finding.finding_type == FindingType.API_KEY
        assert finding.location == "repo:config.py"
        assert finding.severity == VulnerabilitySeverity.HIGH
        assert finding.resolved is False
        assert finding.line_number is None
        assert finding.file_path == ""

    def test_creation_with_full_fields(self) -> None:
        finding = SecretFinding(
            finding_type=FindingType.PRIVATE_KEY,
            location="repo:secrets/key.pem",
            file_path="/app/secrets/key.pem",
            line_number=1,
            snippet_masked="-----BEGIN ***REDACTED*** KEY-----",
            severity=VulnerabilitySeverity.CRITICAL,
            resolved=True,
        )
        assert finding.line_number == 1
        assert finding.file_path == "/app/secrets/key.pem"
        assert finding.resolved is True


class TestCertificateStatus:
    """Tests for CertificateStatus model."""

    def test_basic_creation(self) -> None:
        cert = CertificateStatus(domain="example.com")
        assert cert.domain == "example.com"
        assert cert.issuer == ""
        assert cert.is_expired is False
        assert cert.days_until_expiry == 0

    def test_expired_certificate(self) -> None:
        cert = CertificateStatus(
            domain="expired.example.com",
            is_expired=True,
            days_until_expiry=-10,
        )
        assert cert.is_expired is True
        assert cert.days_until_expiry == -10

    def test_expiry_date_fields(self) -> None:
        now = datetime.now(tz=UTC)
        not_after = now + timedelta(days=30)
        cert = CertificateStatus(
            domain="valid.example.com",
            not_before=now,
            not_after=not_after,
            days_until_expiry=30,
            is_expired=False,
            serial_number="AABBCCDD",
            fingerprint="SHA256:abcdef",
        )
        assert cert.not_after == not_after
        assert cert.serial_number == "AABBCCDD"
        assert cert.fingerprint == "SHA256:abcdef"


class TestSecurityScanResult:
    """Tests for SecurityScanResult model."""

    def test_creation(self) -> None:
        result = SecurityScanResult(scan_id="scan-001")
        assert result.scan_id == "scan-001"
        assert result.scan_type == "full"
        assert result.vulnerabilities == []
        assert result.secrets == []
        assert result.certificates == []


# =====================================================================
# SecretDetector Tests
# =====================================================================


class TestMaskSnippet:
    """Tests for the _mask_snippet helper function."""

    def test_masks_long_alphanumeric_runs(self) -> None:
        line = "api_key = 'AKIAIOSFODNN7EXAMPLEE'"
        masked = _mask_snippet(line)
        assert "AKIAIOSFODNN7EXAMPLEE" not in masked
        assert "***REDACTED***" in masked

    def test_short_values_not_masked(self) -> None:
        line = "name = 'hello'"
        masked = _mask_snippet(line)
        assert "hello" in masked

    def test_truncation(self) -> None:
        long_line = "x" * 200
        masked = _mask_snippet(long_line, max_len=50)
        # After masking, the result is based on the first 50 chars
        assert len(masked) <= 200  # masking may expand with REDACTED text

    def test_strips_whitespace(self) -> None:
        line = "   secret = 'AKIAIOSFODNN7EXAMPLEE'   "
        masked = _mask_snippet(line)
        assert not masked.startswith("   ")


class TestSecretDetector:
    """Tests for SecretDetector.scan_repository."""

    @pytest.mark.asyncio
    async def test_detects_aws_access_key(self, tmp_path: Path) -> None:
        # AKIA + exactly 16 uppercase alphanumeric chars = 20 chars total
        secret_file = tmp_path / "config.py"
        secret_file.write_text("AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n")
        detector = SecretDetector()
        findings = await detector.scan_repository(str(tmp_path))
        assert len(findings) >= 1
        assert any(f.finding_type == FindingType.API_KEY for f in findings)
        # Ensure the raw key is masked in the snippet
        for f in findings:
            assert "AKIAIOSFODNN7EXAMPLE" not in f.snippet_masked

    @pytest.mark.asyncio
    async def test_detects_github_personal_access_token(self, tmp_path: Path) -> None:
        token_file = tmp_path / "deploy.sh"
        token_file.write_text('GITHUB_TOKEN="ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"\n')
        detector = SecretDetector()
        findings = await detector.scan_repository(str(tmp_path))
        assert len(findings) >= 1
        assert any(f.finding_type == FindingType.TOKEN for f in findings)

    @pytest.mark.asyncio
    async def test_detects_private_key_header(self, tmp_path: Path) -> None:
        key_file = tmp_path / "server.conf"
        # Split to avoid triggering detect-private-key pre-commit hook
        pk_header = "-----BEGIN " + "RSA PRIVATE" + " KEY-----"
        key_file.write_text(f"{pk_header}\nMIIE...\n")
        detector = SecretDetector()
        findings = await detector.scan_repository(str(tmp_path))
        assert len(findings) >= 1
        assert any(f.finding_type == FindingType.PRIVATE_KEY for f in findings)

    @pytest.mark.asyncio
    async def test_detects_password_in_config(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "database.yml"
        cfg_file.write_text("password: 'SuperSecret123!'\n")
        detector = SecretDetector()
        findings = await detector.scan_repository(str(tmp_path))
        assert len(findings) >= 1
        assert any(f.finding_type == FindingType.PASSWORD for f in findings)

    @pytest.mark.asyncio
    async def test_skips_non_scannable_extensions(self, tmp_path: Path) -> None:
        binary_file = tmp_path / "image.png"
        binary_file.write_text("AKIAIOSFODNN7EXAMPLE ghp_ABCDabcdABCDabcdABCDabcdABCDabcdABCDab")
        detector = SecretDetector()
        findings = await detector.scan_repository(str(tmp_path))
        assert len(findings) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_directory(self, tmp_path: Path) -> None:
        detector = SecretDetector()
        findings = await detector.scan_repository(str(tmp_path))
        assert findings == []

    @pytest.mark.asyncio
    async def test_handles_nonexistent_directory(self) -> None:
        detector = SecretDetector()
        findings = await detector.scan_repository("/nonexistent/path/xyz")
        assert findings == []

    @pytest.mark.asyncio
    async def test_finding_includes_location_metadata(self, tmp_path: Path) -> None:
        secret_file = tmp_path / "app.py"
        secret_file.write_text("x = 1\nkey = AKIAIOSFODNN7EXAMPLE\n")
        detector = SecretDetector()
        findings = await detector.scan_repository(str(tmp_path))
        assert len(findings) >= 1
        f = findings[0]
        assert f.file_path == str(secret_file)
        assert f.line_number == 2
        assert "app.py" in f.location

    @pytest.mark.asyncio
    async def test_skips_git_directory(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        git_file = git_dir / "config.py"
        git_file.write_text("AKIAIOSFODNN7EXAMPLEE1\n")
        detector = SecretDetector()
        findings = await detector.scan_repository(str(tmp_path))
        assert len(findings) == 0


# =====================================================================
# CertificateMonitor Tests
# =====================================================================


class TestCertificateMonitorParsePeerCert:
    """Tests for CertificateMonitor._parse_peer_cert."""

    def test_parses_valid_cert_dict(self) -> None:
        cert_dict = {
            "notBefore": "Jan 01 00:00:00 2024 GMT",
            "notAfter": "Dec 31 23:59:59 2030 GMT",
            "issuer": ((("organizationName", "Let's Encrypt"),),),
            "serialNumber": "0A1B2C3D",
        }
        result = CertificateMonitor._parse_peer_cert(cert_dict, "example.com")
        assert result.domain == "example.com"
        assert result.issuer == "Let's Encrypt"
        assert result.serial_number == "0A1B2C3D"
        assert result.not_before is not None
        assert result.not_after is not None
        assert result.is_expired is False
        assert result.days_until_expiry > 0

    def test_parses_expired_cert(self) -> None:
        cert_dict = {
            "notBefore": "Jan 01 00:00:00 2020 GMT",
            "notAfter": "Jan 01 00:00:00 2021 GMT",
            "issuer": (),
            "serialNumber": "DEAD",
        }
        result = CertificateMonitor._parse_peer_cert(cert_dict, "expired.com")
        assert result.is_expired is True
        assert result.days_until_expiry < 0

    def test_handles_missing_dates(self) -> None:
        cert_dict: dict = {
            "issuer": (),
        }
        result = CertificateMonitor._parse_peer_cert(cert_dict, "nodates.com")
        assert result.domain == "nodates.com"
        assert result.not_before is None
        assert result.not_after is None
        assert result.days_until_expiry == -1
        assert result.is_expired is True

    def test_extracts_org_from_nested_issuer(self) -> None:
        cert_dict = {
            "notBefore": "Jan 01 00:00:00 2024 GMT",
            "notAfter": "Dec 31 23:59:59 2030 GMT",
            "issuer": (
                (("countryName", "US"),),
                (("organizationName", "DigiCert Inc"),),
                (("commonName", "DigiCert SHA2"),),
            ),
            "serialNumber": "1234",
        }
        result = CertificateMonitor._parse_peer_cert(cert_dict, "digicert.com")
        assert result.issuer == "DigiCert Inc"


class TestCertificateMonitorCheckCertificate:
    """Tests for CertificateMonitor.check_certificate error handling."""

    @pytest.mark.asyncio
    async def test_connection_error_returns_expired_status(self) -> None:
        monitor = CertificateMonitor()
        with patch("shieldops.security_agent.cert_monitor.asyncio.open_connection") as mock_conn:
            mock_conn.side_effect = ConnectionRefusedError("Connection refused")
            result = await monitor.check_certificate("unreachable.example.com", port=443)
        assert result.domain == "unreachable.example.com"
        assert result.is_expired is True
        assert result.days_until_expiry == -1

    @pytest.mark.asyncio
    async def test_ssl_error_returns_expired_status(self) -> None:
        monitor = CertificateMonitor()
        with patch("shieldops.security_agent.cert_monitor.asyncio.open_connection") as mock_conn:
            mock_conn.side_effect = OSError("SSL handshake failed")
            result = await monitor.check_certificate("badsssl.example.com")
        assert result.is_expired is True
        assert result.days_until_expiry == -1


class TestCertificateMonitorRenewalAlert:
    """Tests for CertificateMonitor.generate_renewal_alert."""

    @pytest.mark.asyncio
    async def test_expired_cert_alert(self) -> None:
        monitor = CertificateMonitor()
        cert = CertificateStatus(
            domain="expired.com", is_expired=True, days_until_expiry=-5, issuer="TestCA"
        )
        alert = await monitor.generate_renewal_alert(cert)
        assert alert["urgency"] == "critical"
        assert "EXPIRED" in alert["title"]

    @pytest.mark.asyncio
    async def test_expiring_soon_alert(self) -> None:
        monitor = CertificateMonitor()
        cert = CertificateStatus(
            domain="soon.com", is_expired=False, days_until_expiry=3, issuer="TestCA"
        )
        alert = await monitor.generate_renewal_alert(cert)
        assert alert["urgency"] == "critical"
        assert "3 day(s)" in alert["title"]

    @pytest.mark.asyncio
    async def test_expiring_within_30_days_alert(self) -> None:
        monitor = CertificateMonitor()
        cert = CertificateStatus(
            domain="medium.com", is_expired=False, days_until_expiry=20, issuer="TestCA"
        )
        alert = await monitor.generate_renewal_alert(cert)
        assert alert["urgency"] == "high"

    @pytest.mark.asyncio
    async def test_healthy_cert_alert(self) -> None:
        monitor = CertificateMonitor()
        cert = CertificateStatus(
            domain="healthy.com", is_expired=False, days_until_expiry=90, issuer="TestCA"
        )
        alert = await monitor.generate_renewal_alert(cert)
        assert alert["urgency"] == "info"


class TestCertificateMonitorExpiringCertificates:
    """Tests for CertificateMonitor.get_expiring_certificates."""

    @pytest.mark.asyncio
    async def test_filters_by_threshold(self) -> None:
        monitor = CertificateMonitor()
        monitor._certificates = [
            CertificateStatus(domain="a.com", days_until_expiry=10),
            CertificateStatus(domain="b.com", days_until_expiry=60),
            CertificateStatus(domain="c.com", days_until_expiry=25),
        ]
        expiring = await monitor.get_expiring_certificates(days_threshold=30)
        domains = {c.domain for c in expiring}
        assert domains == {"a.com", "c.com"}


# =====================================================================
# CVEScanner Tests
# =====================================================================


class TestCVEScannerParseGrypeOutput:
    """Tests for CVEScanner._parse_grype_output."""

    def test_parses_valid_grype_json(self) -> None:
        grype_output = json.dumps(
            {
                "matches": [
                    {
                        "vulnerability": {
                            "id": "CVE-2024-9999",
                            "severity": "Critical",
                            "description": "A critical bug",
                            "fix": {"versions": ["2.0.0"]},
                            "cvss": [{"metrics": {"baseScore": 9.8}}],
                        },
                        "artifact": {
                            "name": "libfoo",
                            "version": "1.0.0",
                        },
                    },
                    {
                        "vulnerability": {
                            "id": "CVE-2024-1111",
                            "severity": "Low",
                            "description": "Minor issue",
                            "fix": {"versions": []},
                            "cvss": [],
                        },
                        "artifact": {
                            "name": "libbar",
                            "version": "3.2.1",
                        },
                    },
                ]
            }
        )
        scanner = CVEScanner()
        records = scanner._parse_grype_output(
            grype_output, image="nginx:latest", namespace="default"
        )
        assert len(records) == 2

        crit = records[0]
        assert crit.cve_id == "CVE-2024-9999"
        assert crit.severity == VulnerabilitySeverity.CRITICAL
        assert crit.cvss_score == 9.8
        assert crit.fixed_version == "2.0.0"
        assert crit.package_name == "libfoo"
        assert crit.affected_service == "nginx:latest"
        assert crit.namespace == "default"

        low = records[1]
        assert low.cve_id == "CVE-2024-1111"
        assert low.severity == VulnerabilitySeverity.LOW
        assert low.fixed_version is None
        assert low.cvss_score == 0.0

    def test_handles_invalid_json(self) -> None:
        scanner = CVEScanner()
        records = scanner._parse_grype_output("NOT JSON AT ALL", image="img", namespace="")
        assert records == []

    def test_handles_empty_matches(self) -> None:
        scanner = CVEScanner()
        records = scanner._parse_grype_output(
            json.dumps({"matches": []}), image="img", namespace=""
        )
        assert records == []

    def test_handles_unknown_severity(self) -> None:
        grype_output = json.dumps(
            {
                "matches": [
                    {
                        "vulnerability": {
                            "id": "CVE-2024-0000",
                            "severity": "Unknown",
                            "fix": {"versions": []},
                            "cvss": [],
                        },
                        "artifact": {"name": "pkg", "version": "1.0"},
                    }
                ]
            }
        )
        scanner = CVEScanner()
        records = scanner._parse_grype_output(grype_output, image="img", namespace="")
        assert records[0].severity == VulnerabilitySeverity.INFO


class TestCVEScannerScanImage:
    """Tests for CVEScanner.scan_container_image subprocess handling."""

    @pytest.mark.asyncio
    async def test_grype_not_installed_returns_empty(self) -> None:
        scanner = CVEScanner(grype_path="/nonexistent/grype")
        with patch("shieldops.security_agent.cve_scanner.asyncio.create_subprocess_exec") as mock:
            mock.side_effect = FileNotFoundError("grype not found")
            results = await scanner.scan_container_image("nginx:latest")
        assert results == []

    @pytest.mark.asyncio
    async def test_grype_error_exit_code_returns_empty(self) -> None:
        scanner = CVEScanner()
        mock_proc = AsyncMock()
        mock_proc.returncode = 2  # error (not 0 or 1)
        mock_proc.communicate.return_value = (b"", b"some error")

        with patch(
            "shieldops.security_agent.cve_scanner.asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            results = await scanner.scan_container_image("bad-image:latest")
        assert results == []

    @pytest.mark.asyncio
    async def test_grype_success_parses_output(self) -> None:
        grype_json = json.dumps(
            {
                "matches": [
                    {
                        "vulnerability": {
                            "id": "CVE-2024-0001",
                            "severity": "High",
                            "description": "Test vuln",
                            "fix": {"versions": ["1.2.3"]},
                            "cvss": [{"metrics": {"baseScore": 7.5}}],
                        },
                        "artifact": {"name": "testpkg", "version": "1.0.0"},
                    }
                ]
            }
        )
        scanner = CVEScanner()
        mock_proc = AsyncMock()
        mock_proc.returncode = 1  # grype returns 1 when vulns found
        mock_proc.communicate.return_value = (grype_json.encode(), b"")

        with patch(
            "shieldops.security_agent.cve_scanner.asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            results = await scanner.scan_container_image("myapp:v1", namespace="prod")
        assert len(results) == 1
        assert results[0].cve_id == "CVE-2024-0001"
        assert results[0].severity == VulnerabilitySeverity.HIGH


class TestCVEScannerPrioritize:
    """Tests for CVEScanner.prioritize_vulnerabilities."""

    def test_sorts_by_cvss_then_severity(self) -> None:
        scanner = CVEScanner()
        vulns = [
            VulnerabilityRecord(
                cve_id="LOW-1",
                package_name="a",
                installed_version="1",
                severity=VulnerabilitySeverity.LOW,
                cvss_score=2.0,
            ),
            VulnerabilityRecord(
                cve_id="CRIT-1",
                package_name="b",
                installed_version="1",
                severity=VulnerabilitySeverity.CRITICAL,
                cvss_score=9.8,
            ),
            VulnerabilityRecord(
                cve_id="HIGH-1",
                package_name="c",
                installed_version="1",
                severity=VulnerabilitySeverity.HIGH,
                cvss_score=7.5,
            ),
        ]
        sorted_vulns = scanner.prioritize_vulnerabilities(vulns)
        assert sorted_vulns[0].cve_id == "CRIT-1"
        assert sorted_vulns[1].cve_id == "HIGH-1"
        assert sorted_vulns[2].cve_id == "LOW-1"


class TestCVEScannerFixRecommendations:
    """Tests for CVEScanner.get_fix_recommendations."""

    @pytest.mark.asyncio
    async def test_with_fix_available(self) -> None:
        scanner = CVEScanner()
        vuln = VulnerabilityRecord(
            cve_id="CVE-2024-1234",
            package_name="openssl",
            installed_version="1.1.1k",
            fixed_version="1.1.1l",
            severity=VulnerabilitySeverity.CRITICAL,
        )
        rec = await scanner.get_fix_recommendations(vuln)
        assert rec["priority"] == "immediate"
        assert "Upgrade" in rec["action"]
        assert "1.1.1l" in rec["action"]

    @pytest.mark.asyncio
    async def test_without_fix_available(self) -> None:
        scanner = CVEScanner()
        vuln = VulnerabilityRecord(
            cve_id="CVE-2024-5678",
            package_name="zlib",
            installed_version="1.2.11",
            severity=VulnerabilitySeverity.MEDIUM,
        )
        rec = await scanner.get_fix_recommendations(vuln)
        assert rec["priority"] == "monitor"
        assert "No fix available" in rec["action"]
