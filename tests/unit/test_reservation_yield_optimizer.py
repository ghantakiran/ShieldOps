"""Tests for ReservationYieldOptimizer."""

from __future__ import annotations

from shieldops.billing.reservation_yield_optimizer import (
    CoverageStatus,
    ReservationType,
    ReservationYieldOptimizer,
    YieldLevel,
)


def _engine(**kw) -> ReservationYieldOptimizer:
    return ReservationYieldOptimizer(**kw)


class TestEnums:
    def test_reservation_type_values(self):
        for v in ReservationType:
            assert isinstance(v.value, str)

    def test_coverage_status_values(self):
        for v in CoverageStatus:
            assert isinstance(v.value, str)

    def test_yield_level_values(self):
        for v in YieldLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(reservation_id="r1")
        assert r.reservation_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(reservation_id=f"r-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            reservation_id="r1",
            monthly_cost=1000,
            utilization_pct=60,
        )
        a = eng.process(r.id)
        assert a.waste_amount == 400.0

    def test_exchange_recommended(self):
        eng = _engine()
        r = eng.add_record(yield_level=YieldLevel.WASTEFUL)
        a = eng.process(r.id)
        assert a.exchange_recommended is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(reservation_id="r1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_wasteful_recommendation(self):
        eng = _engine()
        eng.add_record(yield_level=YieldLevel.WASTEFUL)
        rpt = eng.generate_report()
        assert any("wasteful" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(reservation_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAnalyzeReservationCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(utilization_pct=80)
        result = eng.analyze_reservation_coverage()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().analyze_reservation_coverage() == []


class TestRecommendReservationExchanges:
    def test_with_suboptimal(self):
        eng = _engine()
        eng.add_record(
            reservation_id="r1",
            yield_level=YieldLevel.SUBOPTIMAL,
            monthly_cost=1000,
            utilization_pct=50,
        )
        result = eng.recommend_reservation_exchanges()
        assert len(result) == 1
        assert result[0]["waste_amount"] == 500.0

    def test_empty(self):
        assert _engine().recommend_reservation_exchanges() == []


class TestForecastReservationExpiryImpact:
    def test_with_expiring(self):
        eng = _engine()
        eng.add_record(
            reservation_id="r1",
            expiry_days=30,
            monthly_cost=1000,
        )
        result = eng.forecast_reservation_expiry_impact()
        assert len(result) == 1

    def test_no_expiring(self):
        eng = _engine()
        eng.add_record(expiry_days=365)
        assert eng.forecast_reservation_expiry_impact() == []
