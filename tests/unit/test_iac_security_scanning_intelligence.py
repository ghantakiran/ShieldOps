"""Tests for IacSecurityScanningIntelligence."""

from __future__ import annotations

from shieldops.security.iac_security_scanning_intelligence import (
    FindingCategory,
    FindingSeverity,
    IacSecurityScanningIntelligence,
    ScanTool,
)


def _engine(**kw) -> IacSecurityScanningIntelligence:
    return IacSecurityScanningIntelligence(**kw)


class TestEnums:
    def test_finding_severity_values(self):
        for v in FindingSeverity:
            assert isinstance(v.value, str)

    def test_scan_tool_values(self):
        for v in ScanTool:
            assert isinstance(v.value, str)

    def test_finding_category_values(self):
        for v in FindingCategory:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(module_id="m1")
        assert r.module_id == "m1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(module_id=f"m-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            module_id="m1",
            risk_score=75.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "module_id")
        assert a.module_id == "m1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(module_id="m1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(module_id="m1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(module_id="m1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestClassifySecurityFindings:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            module_id="m1",
            finding_severity=(FindingSeverity.CRITICAL),
        )
        result = eng.classify_security_findings()
        assert len(result) == 1
        assert result[0]["by_severity"]["critical"] == 1

    def test_empty(self):
        r = _engine().classify_security_findings()
        assert r == []


class TestComputeScanCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(module_id="m1", resolved=True)
        eng.add_record(module_id="m1", resolved=False)
        result = eng.compute_scan_coverage()
        assert len(result) == 1
        assert result[0]["coverage_pct"] == 50.0

    def test_empty(self):
        r = _engine().compute_scan_coverage()
        assert r == []


class TestRankModulesBySecurityRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(module_id="m1", risk_score=50.0)
        eng.add_record(module_id="m2", risk_score=80.0)
        result = eng.rank_modules_by_security_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_modules_by_security_risk()
        assert r == []
