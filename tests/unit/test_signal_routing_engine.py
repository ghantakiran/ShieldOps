"""Tests for SignalRoutingEngine."""

from __future__ import annotations

from shieldops.observability.signal_routing_engine import (
    RoutingPriority,
    RoutingRule,
    SignalRoutingEngine,
    SignalType,
)


def _engine(**kw) -> SignalRoutingEngine:
    return SignalRoutingEngine(**kw)


class TestEnums:
    def test_signal_type_values(self):
        for v in SignalType:
            assert isinstance(v.value, str)

    def test_routing_rule_values(self):
        for v in RoutingRule:
            assert isinstance(v.value, str)

    def test_routing_priority_values(self):
        for v in RoutingPriority:
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


class TestEvaluateRoutingRules:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            routing_rule=RoutingRule.FORWARD,
            score=90.0,
        )
        result = eng.evaluate_routing_rules()
        assert "forward" in result

    def test_empty(self):
        eng = _engine()
        assert eng.evaluate_routing_rules() == {}


class TestComputeRoutingEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(name="a", service="svc-a", score=30.0)
        result = eng.compute_routing_efficiency()
        assert len(result) > 0

    def test_empty(self):
        eng = _engine()
        assert eng.compute_routing_efficiency() == []


class TestDetectRoutingConflicts:
    def test_with_data(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=30.0)
        result = eng.detect_routing_conflicts()
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_routing_conflicts() == []
