"""Tests for ConsumerLagIntelligence."""

from __future__ import annotations

from shieldops.observability.consumer_lag_intelligence import (
    ConsumerLagIntelligence,
    LagSeverity,
    LagTrend,
    StallReason,
)


def _engine(**kw) -> ConsumerLagIntelligence:
    return ConsumerLagIntelligence(**kw)


class TestEnums:
    def test_lag_trend_values(self):
        for v in LagTrend:
            assert isinstance(v.value, str)

    def test_stall_reason_values(self):
        for v in StallReason:
            assert isinstance(v.value, str)

    def test_lag_severity_values(self):
        for v in LagSeverity:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(consumer_group="cg1")
        assert r.consumer_group == "cg1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(consumer_group=f"cg-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().add_record()
        assert r.lag_trend == LagTrend.STABLE


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            consumer_group="cg1",
            current_lag=1000,
            lag_rate=10.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "consumer_group")
        assert a.consumer_group == "cg1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(consumer_group="cg1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_critical_groups(self):
        eng = _engine()
        eng.add_record(
            consumer_group="cg1",
            lag_severity=LagSeverity.CRITICAL,
        )
        rpt = eng.generate_report()
        assert len(rpt.critical_groups) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(consumer_group="cg1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(consumer_group="cg1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestForecastLagGrowth:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            consumer_group="cg1",
            current_lag=1000,
            lag_rate=10.0,
        )
        result = eng.forecast_lag_growth()
        assert len(result) == 1
        assert result[0]["forecast_1h"] == 1600

    def test_empty(self):
        assert _engine().forecast_lag_growth() == []


class TestDetectConsumerStalls:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            consumer_group="cg1",
            lag_trend=LagTrend.GROWING,
            current_lag=5000,
        )
        result = eng.detect_consumer_stalls()
        assert len(result) == 1

    def test_no_stalls(self):
        eng = _engine()
        eng.add_record(
            consumer_group="cg1",
            lag_trend=LagTrend.STABLE,
        )
        assert eng.detect_consumer_stalls() == []


class TestRankConsumerGroupsByLagSeverity:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            consumer_group="cg1",
            lag_severity=LagSeverity.CRITICAL,
            current_lag=5000,
        )
        eng.add_record(
            consumer_group="cg2",
            lag_severity=LagSeverity.LOW,
            current_lag=100,
        )
        result = eng.rank_consumer_groups_by_lag_severity()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_consumer_groups_by_lag_severity()
        assert r == []
