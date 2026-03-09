"""Tests for shieldops.security.threat_exposure_management — ThreatExposureManagement."""

from __future__ import annotations

from shieldops.security.threat_exposure_management import (
    ExposureSeverity,
    ExposureType,
    RemediationPriority,
    ThreatExposureManagement,
)


def _engine(**kw) -> ThreatExposureManagement:
    return ThreatExposureManagement(**kw)


class TestEnums:
    def test_exposure_type(self):
        assert ExposureType.PUBLIC_ENDPOINT == "public_endpoint"

    def test_severity_critical(self):
        assert ExposureSeverity.CRITICAL == "critical"

    def test_remediation(self):
        assert RemediationPriority.IMMEDIATE == "immediate"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(asset_name="api-gw", exposure_type=ExposureType.PUBLIC_ENDPOINT)
        assert rec.asset_name == "api-gw"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(asset_name=f"asset-{i}")
        assert len(eng._records) == 3


class TestPrioritize:
    def test_basic(self):
        eng = _engine()
        eng.add_record(asset_name="a1", severity=ExposureSeverity.CRITICAL)
        result = eng.prioritize_remediation()
        assert isinstance(result, list)


class TestCorrelateVulns:
    def test_basic(self):
        eng = _engine()
        eng.add_record(asset_name="a1", cve_ids=["CVE-2024-001"])
        result = eng.correlate_vulnerabilities()
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(asset_name="a1", service="api")
        result = eng.process("a1")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(asset_name="a1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(asset_name="a1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(asset_name="a1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
