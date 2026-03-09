"""Tests for shieldops.security.cloud_workload_protection — CloudWorkloadProtection."""

from __future__ import annotations

from shieldops.security.cloud_workload_protection import (
    CloudWorkloadProtection,
    ProtectionStatus,
    ThreatCategory,
    WorkloadType,
)


def _engine(**kw) -> CloudWorkloadProtection:
    return CloudWorkloadProtection(**kw)


class TestEnums:
    def test_workload_type(self):
        assert WorkloadType.CONTAINER == "container"

    def test_threat_category(self):
        assert ThreatCategory.FILE_INTEGRITY == "file_integrity"

    def test_protection_status(self):
        assert ProtectionStatus.PROTECTED == "protected"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(workload_name="api-pod", workload_type=WorkloadType.CONTAINER)
        assert rec.workload_name == "api-pod"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(workload_name=f"w-{i}")
        assert len(eng._records) == 3


class TestProtectionCoverage:
    def test_basic(self):
        eng = _engine()
        eng.add_record(workload_name="w1", protection_status=ProtectionStatus.PROTECTED)
        result = eng.assess_protection_coverage()
        assert isinstance(result, dict)


class TestThreatDistribution:
    def test_basic(self):
        eng = _engine()
        eng.add_record(workload_name="w1", threat_category=ThreatCategory.FILE_INTEGRITY)
        result = eng.analyze_threat_distribution()
        assert isinstance(result, dict)


class TestUnprotected:
    def test_basic(self):
        eng = _engine()
        eng.add_record(workload_name="w1", protection_status=ProtectionStatus.UNPROTECTED)
        result = eng.identify_unprotected()
        assert isinstance(result, list)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(workload_name="w1", service="k8s")
        result = eng.process("w1")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(workload_name="w1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(workload_name="w1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(workload_name="w1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
