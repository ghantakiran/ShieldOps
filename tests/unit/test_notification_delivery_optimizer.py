"""Tests for NotificationDeliveryOptimizer."""

from __future__ import annotations

from shieldops.operations.notification_delivery_optimizer import (
    BatchStrategy,
    DeliveryPriority,
    NotificationDeliveryOptimizer,
    ReliabilityLevel,
)


def _engine(**kw) -> NotificationDeliveryOptimizer:
    return NotificationDeliveryOptimizer(**kw)


class TestEnums:
    def test_delivery_priority_values(self):
        for v in DeliveryPriority:
            assert isinstance(v.value, str)

    def test_batch_strategy_values(self):
        for v in BatchStrategy:
            assert isinstance(v.value, str)

    def test_reliability_level_values(self):
        for v in ReliabilityLevel:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(notification_id="n1")
        assert r.notification_id == "n1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(notification_id=f"n-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.record_item(
            notification_id="n1",
            delivery_time_ms=150.0,
            success=True,
            channel="slack",
        )
        assert r.delivery_time_ms == 150.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            notification_id="n1",
            channel="slack",
        )
        a = eng.process(r.id)
        assert hasattr(a, "notification_id")
        assert a.notification_id == "n1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(notification_id="n1")
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
        eng.record_item(notification_id="n1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(notification_id="n1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestOptimizeDeliveryTiming:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            notification_id="n1",
            channel="slack",
            delivery_time_ms=100.0,
        )
        result = eng.optimize_delivery_timing()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().optimize_delivery_timing()
        assert r == []


class TestPlanNotificationBatching:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            notification_id="n1",
            batch_strategy=BatchStrategy.DIGEST,
            batch_size=5,
        )
        result = eng.plan_notification_batching()
        assert len(result) >= 1

    def test_empty(self):
        r = _engine().plan_notification_batching()
        assert r == []


class TestEvaluateDeliveryReliability:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            notification_id="n1",
            channel="slack",
            success=True,
        )
        eng.record_item(
            notification_id="n2",
            channel="slack",
            success=False,
        )
        result = eng.evaluate_delivery_reliability()
        assert len(result) == 1
        assert "reliability_rate" in result[0]

    def test_empty(self):
        r = _engine().evaluate_delivery_reliability()
        assert r == []
