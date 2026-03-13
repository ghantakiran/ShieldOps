"""Tests for ApiRateLimitIntelligence."""

from __future__ import annotations

from shieldops.topology.api_rate_limit_intelligence import (
    AdjustmentDirection,
    ApiRateLimitIntelligence,
    QuotaStatus,
    ThrottleRisk,
)


def _engine(**kw) -> ApiRateLimitIntelligence:
    return ApiRateLimitIntelligence(**kw)


class TestEnums:
    def test_quota_status_values(self):
        for v in QuotaStatus:
            assert isinstance(v.value, str)

    def test_throttle_risk_values(self):
        for v in ThrottleRisk:
            assert isinstance(v.value, str)

    def test_adjustment_direction_values(self):
        for v in AdjustmentDirection:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(consumer_id="c-1")
        assert r.consumer_id == "c-1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(consumer_id=f"c-{i}")
        assert len(eng._records) == 5

    def test_all_fields(self):
        eng = _engine()
        r = eng.record_item(
            api_name="users-api",
            consumer_id="c-1",
            quota_status=QuotaStatus.EXCEEDED,
            utilization_pct=105.0,
        )
        assert r.utilization_pct == 105.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            consumer_id="c-1",
            utilization_pct=75.0,
        )
        a = eng.process(r.id)
        assert a.utilization_pct == 75.0

    def test_at_risk(self):
        eng = _engine()
        r = eng.record_item(
            throttle_risk=ThrottleRisk.IMMINENT,
        )
        a = eng.process(r.id)
        assert a.at_risk is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(consumer_id="c-1")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_at_risk_consumers(self):
        eng = _engine()
        eng.record_item(
            consumer_id="c-1",
            throttle_risk=ThrottleRisk.IMMINENT,
        )
        rpt = eng.generate_report()
        assert len(rpt.at_risk_consumers) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(consumer_id="c-1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(consumer_id="c-1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestPredictThrottlingEvents:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            consumer_id="c-1",
            throttle_risk=ThrottleRisk.IMMINENT,
            utilization_pct=95.0,
        )
        result = eng.predict_throttling_events()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().predict_throttling_events() == []


class TestAnalyzeQuotaUtilization:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            consumer_id="c-1",
            utilization_pct=80.0,
        )
        result = eng.analyze_quota_utilization()
        assert len(result) == 1
        assert result[0]["avg_utilization"] == 80.0

    def test_empty(self):
        assert _engine().analyze_quota_utilization() == []


class TestRecommendQuotaAdjustments:
    def test_high_util(self):
        eng = _engine()
        eng.record_item(
            consumer_id="c-1",
            utilization_pct=95.0,
        )
        result = eng.recommend_quota_adjustments()
        assert len(result) == 1
        assert "Increase" in result[0]["recommendation"]

    def test_low_util(self):
        eng = _engine()
        eng.record_item(
            consumer_id="c-1",
            utilization_pct=10.0,
        )
        result = eng.recommend_quota_adjustments()
        assert "Decrease" in result[0]["recommendation"]

    def test_empty(self):
        assert _engine().recommend_quota_adjustments() == []
