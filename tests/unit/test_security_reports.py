"""Tests for Security Report Generation (F11)."""

from unittest.mock import AsyncMock

import pytest

from shieldops.vulnerability.report_generator import (
    ReportMetadata,
    SecurityReport,
    SecurityReportGenerator,
)


class TestReportModels:
    def test_report_metadata_defaults(self):
        meta = ReportMetadata(
            report_id="test-1",
            report_type="executive",
            title="Test Report",
        )
        assert meta.report_id == "test-1"
        assert meta.report_type == "executive"
        assert meta.generated_by == "ShieldOps Security Platform"
        assert meta.format == "html"
        assert meta.generated_at != ""

    def test_report_metadata_full(self):
        meta = ReportMetadata(
            report_id="comp-1",
            report_type="compliance",
            title="SOC2 Report",
            period_start="2024-01-01",
            period_end="2024-06-30",
        )
        assert meta.period_start == "2024-01-01"
        assert meta.period_end == "2024-06-30"

    def test_security_report_defaults(self):
        meta = ReportMetadata(report_id="r1", report_type="exec", title="T")
        report = SecurityReport(metadata=meta)
        assert report.content == ""
        assert report.summary == {}
        assert report.sections == []

    def test_security_report_full(self):
        meta = ReportMetadata(report_id="r1", report_type="exec", title="T")
        report = SecurityReport(
            metadata=meta,
            content="<html>Report</html>",
            summary={"score": 85},
            sections=[{"title": "Overview", "type": "overview", "data": {}}],
        )
        assert "<html>" in report.content
        assert report.summary["score"] == 85
        assert len(report.sections) == 1


class TestSecurityReportGenerator:
    @pytest.fixture
    def generator(self):
        return SecurityReportGenerator()

    @pytest.fixture
    def mock_posture(self):
        posture = AsyncMock()
        posture.get_overview.return_value = {
            "overall_score": 78.5,
            "grade": "C",
            "total_vulnerabilities": 25,
            "by_severity": {"critical": 2, "high": 5, "medium": 10, "low": 8},
            "by_status": {"open": 15, "resolved": 10},
            "sla_breaches": 3,
            "mean_time_to_remediate_hours": 24.5,
            "open_critical": 2,
            "open_high": 5,
            "patch_coverage": 66.7,
            "last_scan": "2024-06-01T12:00:00Z",
            "timestamp": "2024-06-01T12:00:00Z",
        }
        posture.get_trends.return_value = {
            "period_days": 30,
            "data_points": [{"date": "2024-06-01", "total": 25}],
            "timestamp": "2024-06-01T12:00:00Z",
        }
        posture.get_risk_matrix.return_value = {
            "matrix": {
                "critical": {"exploitable": 1, "likely": 0, "possible": 0, "unlikely": 0},
                "high": {"exploitable": 0, "likely": 2, "possible": 1, "unlikely": 0},
                "medium": {"exploitable": 0, "likely": 0, "possible": 5, "unlikely": 3},
                "low": {"exploitable": 0, "likely": 0, "possible": 0, "unlikely": 5},
            },
            "timestamp": "2024-06-01T12:00:00Z",
        }
        return posture

    @pytest.fixture
    def mock_repository(self):
        repo = AsyncMock()
        repo.list_vulnerabilities.return_value = [
            {
                "cve_id": "CVE-2024-1111",
                "severity": "critical",
                "cvss_score": 9.8,
                "package_name": "openssl",
                "status": "open",
                "fixed_version": "3.1.5",
            },
            {
                "cve_id": "CVE-2024-2222",
                "severity": "high",
                "cvss_score": 7.5,
                "package_name": "nginx",
                "status": "open",
                "fixed_version": "",
            },
            {
                "cve_id": "CVE-2024-3333",
                "severity": "medium",
                "cvss_score": 5.0,
                "package_name": "curl",
                "status": "resolved",
                "fixed_version": "8.5.0",
            },
        ]
        return repo

    @pytest.fixture
    def generator_with_posture(self, mock_posture, mock_repository):
        return SecurityReportGenerator(
            posture_aggregator=mock_posture,
            repository=mock_repository,
        )

    @pytest.mark.asyncio
    async def test_executive_report_no_posture(self, generator):
        report = await generator.generate_executive_report()
        assert report.metadata.report_type == "executive"
        assert report.metadata.title == "Executive Security Summary"
        assert "exec-" in report.metadata.report_id
        assert report.summary["overall_score"] == 0
        assert "<html>" in report.content

    @pytest.mark.asyncio
    async def test_executive_report_with_posture(self, generator_with_posture):
        report = await generator_with_posture.generate_executive_report()
        assert report.summary["overall_score"] == 78.5
        assert report.summary["grade"] == "C"
        assert report.summary["critical_count"] == 2
        assert report.summary["high_count"] == 5
        assert report.summary["mttr_hours"] == 24.5
        assert len(report.sections) == 3
        assert report.sections[0]["title"] == "Security Posture Overview"

    @pytest.mark.asyncio
    async def test_executive_report_html_content(self, generator_with_posture):
        report = await generator_with_posture.generate_executive_report()
        assert "Executive Security Summary" in report.content
        assert "78.5" in report.content or "Score" in report.content

    @pytest.mark.asyncio
    async def test_compliance_report_no_posture(self, generator):
        report = await generator.generate_compliance_report("soc2")
        assert report.metadata.report_type == "compliance"
        assert "SOC2" in report.metadata.title
        assert "comp-" in report.metadata.report_id
        assert report.summary["framework"] == "soc2"

    @pytest.mark.asyncio
    async def test_compliance_report_with_posture(self, generator_with_posture):
        report = await generator_with_posture.generate_compliance_report("pci-dss")
        assert "PCI-DSS" in report.metadata.title
        assert report.summary["overall_score"] == 78.5
        assert len(report.sections) == 2

    @pytest.mark.asyncio
    async def test_compliance_report_html_content(self, generator_with_posture):
        report = await generator_with_posture.generate_compliance_report("hipaa")
        assert "HIPAA" in report.content

    @pytest.mark.asyncio
    async def test_vulnerability_report_no_data(self, generator):
        report = await generator.generate_vulnerability_report()
        assert report.metadata.report_type == "vulnerability"
        assert "vuln-" in report.metadata.report_id
        assert report.summary["total_vulnerabilities"] == 0

    @pytest.mark.asyncio
    async def test_vulnerability_report_with_data(self, generator_with_posture):
        report = await generator_with_posture.generate_vulnerability_report()
        assert report.summary["total_vulnerabilities"] == 3
        assert report.summary["critical"] == 1
        assert report.summary["high"] == 1
        assert report.summary["medium"] == 1
        assert report.summary["with_patches"] == 2
        assert len(report.sections) == 3

    @pytest.mark.asyncio
    async def test_vulnerability_report_html_content(self, generator_with_posture):
        report = await generator_with_posture.generate_vulnerability_report()
        assert "Vulnerability Assessment Report" in report.content
        assert "CVE-2024-1111" in report.content

    @pytest.mark.asyncio
    async def test_vulnerability_report_repo_error(self, mock_posture):
        repo = AsyncMock()
        repo.list_vulnerabilities.side_effect = Exception("DB error")
        gen = SecurityReportGenerator(posture_aggregator=mock_posture, repository=repo)
        report = await gen.generate_vulnerability_report()
        assert report.summary["total_vulnerabilities"] == 0

    @pytest.mark.asyncio
    async def test_get_history_empty(self, generator):
        assert generator.get_history() == []

    @pytest.mark.asyncio
    async def test_get_history_after_reports(self, generator_with_posture):
        await generator_with_posture.generate_executive_report()
        await generator_with_posture.generate_compliance_report("soc2")
        await generator_with_posture.generate_vulnerability_report()

        history = generator_with_posture.get_history()
        assert len(history) == 3
        types = [h["report_type"] for h in history]
        assert "executive" in types
        assert "compliance" in types
        assert "vulnerability" in types

    @pytest.mark.asyncio
    async def test_history_contains_report_ids(self, generator_with_posture):
        await generator_with_posture.generate_executive_report()
        history = generator_with_posture.get_history()
        assert history[0]["report_id"].startswith("exec-")

    @pytest.mark.asyncio
    async def test_report_unique_ids(self, generator_with_posture):
        r1 = await generator_with_posture.generate_executive_report()
        r2 = await generator_with_posture.generate_executive_report()
        assert r1.metadata.report_id != r2.metadata.report_id

    def test_render_executive_html(self, generator):
        summary = {
            "overall_score": 85,
            "grade": "B",
            "total_vulnerabilities": 10,
            "critical_count": 1,
            "high_count": 3,
            "mttr_hours": 12,
            "sla_breaches": 0,
            "patch_coverage": 90,
        }
        html = generator._render_executive_html(summary, [])
        assert "<!DOCTYPE html>" in html
        assert "85" in html
        assert "grade-B" in html

    def test_render_compliance_html(self, generator):
        data = {"overall_score": 78, "framework": "soc2"}
        html = generator._render_compliance_html("soc2", data, [])
        assert "SOC2" in html
        assert "78" in html

    def test_render_vulnerability_html(self, generator):
        summary = {
            "total_vulnerabilities": 2,
            "critical": 1,
            "high": 1,
            "medium": 0,
            "low": 0,
        }
        vulns = [
            {
                "cve_id": "CVE-2024-1111",
                "severity": "critical",
                "cvss_score": 9.8,
                "package_name": "openssl",
                "status": "open",
                "fixed_version": "3.1.5",
            }
        ]
        html = generator._render_vulnerability_html(summary, [], vulns)
        assert "CVE-2024-1111" in html
        assert "openssl" in html
        assert "9.8" in html

    def test_render_vulnerability_html_empty(self, generator):
        summary = {"total_vulnerabilities": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}
        html = generator._render_vulnerability_html(summary, [], [])
        assert "Vulnerability Assessment Report" in html
