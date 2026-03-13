"""Tests for RiskBasedPrioritizer."""

from __future__ import annotations

from shieldops.security.risk_based_prioritizer import (
    AnalystWorkload,
    PrioritizationMethod,
    QueuePosition,
    RiskBasedPrioritizer,
)


def _engine(**kw) -> RiskBasedPrioritizer:
    return RiskBasedPrioritizer(**kw)


class TestEnums:
    def test_prioritization_method_values(self):
        for v in PrioritizationMethod:
            assert isinstance(v.value, str)

    def test_queue_position_values(self):
        for v in QueuePosition:
            assert isinstance(v.value, str)

    def test_analyst_workload_values(self):
        for v in AnalystWorkload:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(alert_id="a1")
        assert r.alert_id == "a1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(alert_id=f"a-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(alert_id="a1", risk_score=80.0)
        a = eng.process(r.id)
        assert hasattr(a, "alert_id")
        assert a.alert_id == "a1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_id="a1")
        assert eng.generate_report().total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_id="a1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(alert_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestPrioritizeAlertQueue:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_id="a1",
            risk_score=90.0,
            asset_value=80.0,
        )
        result = eng.prioritize_alert_queue()
        assert len(result) == 1
        assert result[0]["composite_priority"] > 0

    def test_empty(self):
        assert _engine().prioritize_alert_queue() == []


class TestComputeQueueEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_id="a1",
            risk_score=90.0,
            position=QueuePosition.IMMEDIATE,
        )
        result = eng.compute_queue_efficiency()
        assert "efficiency_pct" in result

    def test_empty(self):
        result = _engine().compute_queue_efficiency()
        assert result["efficiency_pct"] == 0.0


class TestDetectPriorityInversions:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_id="a1",
            risk_score=90.0,
            asset_value=90.0,
            position=QueuePosition.DEFERRED,
        )
        result = eng.detect_priority_inversions()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_priority_inversions() == []
