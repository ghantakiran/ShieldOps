"""Tests for NotificationFatigueDetector."""

from __future__ import annotations

from shieldops.observability.notification_fatigue_detector import (
    DetectionMethod,
    FatigueLevel,
    NotificationFatigueDetector,
    NotificationType,
)


def _engine(**kw) -> NotificationFatigueDetector:
    return NotificationFatigueDetector(**kw)


class TestEnums:
    def test_fatigue_level_values(self):
        for v in FatigueLevel:
            assert isinstance(v.value, str)

    def test_notification_type_values(self):
        for v in NotificationType:
            assert isinstance(v.value, str)

    def test_detection_method_values(self):
        for v in DetectionMethod:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(recipient_id="r1")
        assert r.recipient_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(recipient_id=f"r-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.add_record(
            recipient_id="r1",
            fatigue_level=FatigueLevel.HIGH,
            volume=50,
        )
        assert r.fatigue_level == FatigueLevel.HIGH
        assert r.volume == 50


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            recipient_id="r1",
            response_time_ms=500.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "recipient_id")
        assert a.recipient_id == "r1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(recipient_id="r1")
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
        eng.add_record(recipient_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(recipient_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestDetectFatiguePatterns:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            recipient_id="r1",
            acknowledged=False,
        )
        result = eng.detect_fatigue_patterns()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_fatigue_patterns() == []


class TestCalculateFatigueRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(recipient_id="r1", volume=100)
        result = eng.calculate_fatigue_risk_score()
        assert len(result) == 1
        assert "fatigue_risk_score" in result[0]

    def test_empty(self):
        r = _engine().calculate_fatigue_risk_score()
        assert r == []


class TestRecommendLoadRedistribution:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(recipient_id="r1", volume=100)
        eng.add_record(recipient_id="r2", volume=10)
        result = eng.recommend_load_redistribution()
        assert len(result) == 2

    def test_empty(self):
        r = _engine().recommend_load_redistribution()
        assert r == []
