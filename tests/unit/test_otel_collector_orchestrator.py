"""Tests for OtelCollectorOrchestrator."""

from __future__ import annotations

from shieldops.observability.otel_collector_orchestrator import (
    CollectorHealth,
    CollectorMode,
    OtelCollectorOrchestrator,
    ScalingPolicy,
)


def _engine(**kw) -> OtelCollectorOrchestrator:
    return OtelCollectorOrchestrator(**kw)


class TestEnums:
    def test_collector_mode_values(self):
        for v in CollectorMode:
            assert isinstance(v.value, str)

    def test_collector_health_values(self):
        for v in CollectorHealth:
            assert isinstance(v.value, str)

    def test_scaling_policy_values(self):
        for v in ScalingPolicy:
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


class TestAssessCollectorFleet:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            collector_health=CollectorHealth.RUNNING,
            score=90.0,
        )
        result = eng.assess_collector_fleet()
        assert "running" in result

    def test_empty(self):
        eng = _engine()
        assert eng.assess_collector_fleet() == {}


class TestDetectCollectorGaps:
    def test_with_data(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=30.0)
        result = eng.detect_collector_gaps()
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_collector_gaps() == []


class TestRecommendScalingAction:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(name="a", service="svc-a", score=30.0)
        result = eng.recommend_scaling_action()
        assert len(result) > 0

    def test_empty(self):
        eng = _engine()
        assert eng.recommend_scaling_action() == []
