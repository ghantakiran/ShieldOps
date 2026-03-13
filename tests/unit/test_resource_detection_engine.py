"""Tests for ResourceDetectionEngine."""

from __future__ import annotations

from shieldops.observability.resource_detection_engine import (
    DetectionMethod,
    ResourceConfidence,
    ResourceDetectionEngine,
    ResourceProvider,
)


def _engine(**kw) -> ResourceDetectionEngine:
    return ResourceDetectionEngine(**kw)


class TestEnums:
    def test_resource_provider_values(self):
        for v in ResourceProvider:
            assert isinstance(v.value, str)

    def test_detection_method_values(self):
        for v in DetectionMethod:
            assert isinstance(v.value, str)

    def test_resource_confidence_values(self):
        for v in ResourceConfidence:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(name="test-001", score=80.0)
        assert r.name == "test-001"
        assert r.score == 80.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(name=f"item-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(name="test", score=40.0)
        result = eng.process(r.id)
        assert result["status"] == "processed"

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=50.0)
        report = eng.generate_report()
        assert report.total_records > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated_count(self):
        eng = _engine()
        eng.add_record(name="a")
        eng.add_record(name="b")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(name="a")
        eng.clear_data()
        assert len(eng._records) == 0


class TestDetectResourceAttributes:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            resource_provider=ResourceProvider.AWS,
            score=90.0,
        )
        result = eng.detect_resource_attributes()
        assert "aws" in result

    def test_empty(self):
        eng = _engine()
        assert eng.detect_resource_attributes() == {}


class TestComputeDetectionCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(name="a", service="svc-a", score=30.0)
        result = eng.compute_detection_coverage()
        assert len(result) > 0

    def test_empty(self):
        eng = _engine()
        assert eng.compute_detection_coverage() == []


class TestReconcileConflictingAttributes:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            resource_confidence=(ResourceConfidence.UNKNOWN),
        )
        result = eng.reconcile_conflicting_attributes()
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        result = eng.reconcile_conflicting_attributes()
        assert result == []
