"""Tests for shieldops.billing.ri_purchase_optimizer."""

from __future__ import annotations

from shieldops.billing.ri_purchase_optimizer import (
    CommitmentTerm,
    PaymentOption,
    PurchaseAnalysis,
    ReservationType,
    RIPurchaseOptimizer,
    RIPurchaseRecord,
    RIPurchaseReport,
)


def _engine(**kw) -> RIPurchaseOptimizer:
    return RIPurchaseOptimizer(**kw)


class TestEnums:
    def test_reservationtype_standard(self):
        assert ReservationType.STANDARD == "standard"

    def test_reservationtype_convertible(self):
        assert ReservationType.CONVERTIBLE == "convertible"

    def test_reservationtype_savings_plan(self):
        assert ReservationType.SAVINGS_PLAN == "savings_plan"

    def test_reservationtype_spot(self):
        assert ReservationType.SPOT == "spot"

    def test_reservationtype_on_demand(self):
        assert ReservationType.ON_DEMAND == "on_demand"

    def test_commitmentterm_one_year(self):
        assert CommitmentTerm.ONE_YEAR == "one_year"

    def test_commitmentterm_three_year(self):
        assert CommitmentTerm.THREE_YEAR == "three_year"

    def test_commitmentterm_monthly(self):
        assert CommitmentTerm.MONTHLY == "monthly"

    def test_commitmentterm_weekly(self):
        assert CommitmentTerm.WEEKLY == "weekly"

    def test_commitmentterm_none(self):
        assert CommitmentTerm.NONE == "none"

    def test_paymentoption_all_upfront(self):
        assert PaymentOption.ALL_UPFRONT == "all_upfront"

    def test_paymentoption_partial_upfront(self):
        assert PaymentOption.PARTIAL_UPFRONT == "partial_upfront"

    def test_paymentoption_no_upfront(self):
        assert PaymentOption.NO_UPFRONT == "no_upfront"

    def test_paymentoption_monthly(self):
        assert PaymentOption.MONTHLY == "monthly"

    def test_paymentoption_custom(self):
        assert PaymentOption.CUSTOM == "custom"


class TestModels:
    def test_ri_purchase_record_defaults(self):
        r = RIPurchaseRecord()
        assert r.id
        assert r.reservation_type == ReservationType.STANDARD
        assert r.commitment_term == CommitmentTerm.ONE_YEAR
        assert r.payment_option == PaymentOption.NO_UPFRONT
        assert r.on_demand_cost == 0.0
        assert r.reserved_cost == 0.0
        assert r.savings_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_purchase_analysis_defaults(self):
        a = PurchaseAnalysis()
        assert a.id
        assert a.reservation_type == ReservationType.STANDARD
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_ri_purchase_report_defaults(self):
        r = RIPurchaseReport()
        assert r.id
        assert r.total_records == 0
        assert r.high_savings_count == 0
        assert r.avg_savings_pct == 0.0
        assert r.by_reservation_type == {}
        assert r.top_opportunities == []
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordPurchase:
    def test_basic(self):
        eng = _engine()
        r = eng.record_purchase(
            reservation_type=ReservationType.CONVERTIBLE,
            commitment_term=CommitmentTerm.THREE_YEAR,
            payment_option=PaymentOption.ALL_UPFRONT,
            on_demand_cost=10000.0,
            reserved_cost=5000.0,
            savings_pct=50.0,
            service="ec2",
            team="platform",
        )
        assert r.reservation_type == ReservationType.CONVERTIBLE
        assert r.savings_pct == 50.0
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_purchase(reservation_type=ReservationType.STANDARD)
        assert len(eng._records) == 3


class TestGetPurchase:
    def test_found(self):
        eng = _engine()
        r = eng.record_purchase(savings_pct=40.0)
        result = eng.get_purchase(r.id)
        assert result is not None
        assert result.savings_pct == 40.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_purchase("nonexistent") is None


class TestListPurchases:
    def test_list_all(self):
        eng = _engine()
        eng.record_purchase(reservation_type=ReservationType.STANDARD)
        eng.record_purchase(reservation_type=ReservationType.CONVERTIBLE)
        assert len(eng.list_purchases()) == 2

    def test_filter_by_reservation_type(self):
        eng = _engine()
        eng.record_purchase(reservation_type=ReservationType.STANDARD)
        eng.record_purchase(reservation_type=ReservationType.SAVINGS_PLAN)
        results = eng.list_purchases(reservation_type=ReservationType.STANDARD)
        assert len(results) == 1

    def test_filter_by_commitment_term(self):
        eng = _engine()
        eng.record_purchase(commitment_term=CommitmentTerm.ONE_YEAR)
        eng.record_purchase(commitment_term=CommitmentTerm.THREE_YEAR)
        results = eng.list_purchases(commitment_term=CommitmentTerm.ONE_YEAR)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_purchase(team="platform")
        eng.record_purchase(team="security")
        results = eng.list_purchases(team="platform")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_purchase(reservation_type=ReservationType.STANDARD)
        assert len(eng.list_purchases(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            reservation_type=ReservationType.SAVINGS_PLAN,
            analysis_score=90.0,
            threshold=70.0,
            breached=True,
            description="high savings potential",
        )
        assert a.reservation_type == ReservationType.SAVINGS_PLAN
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(reservation_type=ReservationType.STANDARD)
        assert len(eng._analyses) == 2


class TestAnalyzeTypeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_purchase(reservation_type=ReservationType.STANDARD, savings_pct=30.0)
        eng.record_purchase(reservation_type=ReservationType.STANDARD, savings_pct=50.0)
        result = eng.analyze_type_distribution()
        assert "standard" in result
        assert result["standard"]["count"] == 2
        assert result["standard"]["avg_savings_pct"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


class TestIdentifyHighSavingsOpportunities:
    def test_detects_above_threshold(self):
        eng = _engine(savings_threshold=30.0)
        eng.record_purchase(savings_pct=50.0)
        eng.record_purchase(savings_pct=15.0)
        results = eng.identify_high_savings_opportunities()
        assert len(results) == 1

    def test_sorted_descending(self):
        eng = _engine(savings_threshold=20.0)
        eng.record_purchase(savings_pct=60.0)
        eng.record_purchase(savings_pct=40.0)
        results = eng.identify_high_savings_opportunities()
        assert results[0]["savings_pct"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_savings_opportunities() == []


class TestRankBySavings:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_purchase(service="ec2", savings_pct=50.0)
        eng.record_purchase(service="rds", savings_pct=20.0)
        results = eng.rank_by_savings()
        assert results[0]["service"] == "ec2"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_savings() == []


class TestDetectSavingsTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_savings_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=90.0)
        eng.add_analysis(analysis_score=90.0)
        result = eng.detect_savings_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_savings_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(savings_threshold=30.0)
        eng.record_purchase(
            reservation_type=ReservationType.STANDARD,
            commitment_term=CommitmentTerm.ONE_YEAR,
            payment_option=PaymentOption.NO_UPFRONT,
            savings_pct=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RIPurchaseReport)
        assert report.total_records == 1
        assert report.high_savings_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_purchase(reservation_type=ReservationType.STANDARD)
        eng.add_analysis(reservation_type=ReservationType.STANDARD)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["reservation_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_purchase(
            reservation_type=ReservationType.STANDARD,
            service="ec2",
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "standard" in stats["reservation_type_distribution"]
