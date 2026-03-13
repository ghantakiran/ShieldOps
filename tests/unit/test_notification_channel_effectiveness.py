"""Tests for NotificationChannelEffectiveness."""

from __future__ import annotations

from shieldops.incidents.notification_channel_effectiveness import (
    ChannelType,
    DeliveryStatus,
    EffectivenessRating,
    NotificationChannelEffectiveness,
)


def _engine(**kw) -> NotificationChannelEffectiveness:
    return NotificationChannelEffectiveness(**kw)


class TestEnums:
    def test_channel_type_values(self):
        for v in ChannelType:
            assert isinstance(v.value, str)

    def test_effectiveness_rating_values(self):
        for v in EffectivenessRating:
            assert isinstance(v.value, str)

    def test_delivery_status_values(self):
        for v in DeliveryStatus:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(channel_type=ChannelType.SLACK)
        assert r.channel_type == ChannelType.SLACK

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(recipient_id=f"r-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.add_record(
            channel_type=ChannelType.PAGERDUTY,
            acknowledged=True,
            response_time_ms=200.0,
        )
        assert r.acknowledged is True


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            channel_type=ChannelType.SLACK,
            acknowledged=True,
        )
        a = eng.process(r.id)
        assert hasattr(a, "channel_type")

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(channel_type=ChannelType.SLACK)
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
        eng.add_record()
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record()
        eng.clear_data()
        assert len(eng._records) == 0


class TestRankChannelsByResponseRate:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            channel_type=ChannelType.SLACK,
            acknowledged=True,
        )
        eng.add_record(
            channel_type=ChannelType.EMAIL,
            acknowledged=False,
        )
        result = eng.rank_channels_by_response_rate()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_channels_by_response_rate()
        assert r == []


class TestDetectChannelDegradation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            channel_type=ChannelType.SLACK,
            delivery_status=DeliveryStatus.FAILED,
        )
        result = eng.detect_channel_degradation()
        assert len(result) >= 1

    def test_empty(self):
        r = _engine().detect_channel_degradation()
        assert r == []


class TestRecommendChannelOptimization:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            channel_type=ChannelType.SLACK,
            acknowledged=True,
        )
        result = eng.recommend_channel_optimization()
        assert len(result) >= 1

    def test_empty(self):
        r = _engine().recommend_channel_optimization()
        assert r == []
