"""Tests for IacTestCoverageAnalyzer."""

from __future__ import annotations

from shieldops.analytics.iac_test_coverage_analyzer import (
    CoverageStatus,
    IacTestCoverageAnalyzer,
    TestFramework,
    TestType,
)


def _engine(**kw) -> IacTestCoverageAnalyzer:
    return IacTestCoverageAnalyzer(**kw)


class TestEnums:
    def test_test_type_values(self):
        for v in TestType:
            assert isinstance(v.value, str)

    def test_coverage_status_values(self):
        for v in CoverageStatus:
            assert isinstance(v.value, str)

    def test_test_framework_values(self):
        for v in TestFramework:
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
            coverage_pct=75.0,
            total_resources=10,
            tested_resources=7,
        )
        a = eng.process(r.id)
        assert hasattr(a, "module_id")
        assert a.untested_count == 3

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


class TestComputeTestCoverageRatio:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(module_id="m1", coverage_pct=80.0)
        result = eng.compute_test_coverage_ratio()
        assert len(result) == 1
        assert result[0]["avg_coverage"] == 80.0

    def test_empty(self):
        r = _engine().compute_test_coverage_ratio()
        assert r == []


class TestDetectUntestedResources:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            module_id="m1",
            total_resources=10,
            tested_resources=5,
        )
        result = eng.detect_untested_resources()
        assert len(result) == 1
        assert result[0]["untested_count"] == 5

    def test_empty(self):
        r = _engine().detect_untested_resources()
        assert r == []


class TestRankModulesByTestingGaps:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(module_id="m1", coverage_pct=60.0)
        eng.add_record(module_id="m2", coverage_pct=30.0)
        result = eng.rank_modules_by_testing_gaps()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_modules_by_testing_gaps()
        assert r == []
