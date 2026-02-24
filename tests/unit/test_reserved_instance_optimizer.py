"""Tests for shieldops.billing.reserved_instance_optimizer — ReservedInstanceOptimizer."""

from __future__ import annotations

import time

from shieldops.billing.reserved_instance_optimizer import (
    CommitmentType,
    CoverageGap,
    CoverageStatus,
    PurchaseRecommendation,
    ReservationRecord,
    ReservedInstanceOptimizer,
    RIOptimizationReport,
)


def _engine(**kw) -> ReservedInstanceOptimizer:
    return ReservedInstanceOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # CommitmentType (5)
    def test_commitment_reserved_instance(self):
        assert CommitmentType.RESERVED_INSTANCE == "reserved_instance"

    def test_commitment_savings_plan(self):
        assert CommitmentType.SAVINGS_PLAN == "savings_plan"

    def test_commitment_committed_use(self):
        assert CommitmentType.COMMITTED_USE == "committed_use"

    def test_commitment_spot_fleet(self):
        assert CommitmentType.SPOT_FLEET == "spot_fleet"

    def test_commitment_on_demand(self):
        assert CommitmentType.ON_DEMAND == "on_demand"

    # CoverageStatus (5)
    def test_status_fully_covered(self):
        assert CoverageStatus.FULLY_COVERED == "fully_covered"

    def test_status_partially_covered(self):
        assert CoverageStatus.PARTIALLY_COVERED == "partially_covered"

    def test_status_uncovered(self):
        assert CoverageStatus.UNCOVERED == "uncovered"

    def test_status_over_committed(self):
        assert CoverageStatus.OVER_COMMITTED == "over_committed"

    def test_status_expiring_soon(self):
        assert CoverageStatus.EXPIRING_SOON == "expiring_soon"

    # PurchaseRecommendation (5)
    def test_rec_buy_one_year(self):
        assert PurchaseRecommendation.BUY_ONE_YEAR == "buy_one_year"

    def test_rec_buy_three_year(self):
        assert PurchaseRecommendation.BUY_THREE_YEAR == "buy_three_year"

    def test_rec_convert_to_savings_plan(self):
        assert PurchaseRecommendation.CONVERT_TO_SAVINGS_PLAN == "convert_to_savings_plan"

    def test_rec_maintain_on_demand(self):
        assert PurchaseRecommendation.MAINTAIN_ON_DEMAND == "maintain_on_demand"

    def test_rec_downgrade_commitment(self):
        assert PurchaseRecommendation.DOWNGRADE_COMMITMENT == "downgrade_commitment"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_reservation_defaults(self):
        r = ReservationRecord()
        assert r.id
        assert r.resource_id == ""
        assert r.commitment_type == CommitmentType.RESERVED_INSTANCE
        assert r.instance_type == ""
        assert r.region == ""
        assert r.monthly_cost == 0.0
        assert r.utilization_pct == 0.0
        assert r.expiry_timestamp == 0.0
        assert r.coverage_status == CoverageStatus.UNCOVERED

    def test_gap_defaults(self):
        g = CoverageGap()
        assert g.id
        assert g.resource_id == ""
        assert g.instance_type == ""
        assert g.region == ""
        assert g.on_demand_cost == 0.0
        assert g.potential_savings == 0.0
        assert g.recommendation == PurchaseRecommendation.MAINTAIN_ON_DEMAND

    def test_report_defaults(self):
        r = RIOptimizationReport()
        assert r.total_reservations == 0
        assert r.total_monthly_spend == 0.0
        assert r.avg_utilization_pct == 0.0
        assert r.expiring_count == 0
        assert r.coverage_gap_count == 0
        assert r.potential_annual_savings == 0.0
        assert r.commitment_breakdown == {}
        assert r.recommendations == []


# ---------------------------------------------------------------------------
# register_reservation
# ---------------------------------------------------------------------------


class TestRegisterReservation:
    def test_basic_register(self):
        eng = _engine()
        r = eng.register_reservation(
            resource_id="i-abc123",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            instance_type="m5.xlarge",
            region="us-east-1",
            monthly_cost=250.0,
            utilization_pct=85.0,
            expiry_timestamp=time.time() + 86400 * 365,
            coverage_status=CoverageStatus.FULLY_COVERED,
        )
        assert r.resource_id == "i-abc123"
        assert r.commitment_type == CommitmentType.RESERVED_INSTANCE
        assert r.instance_type == "m5.xlarge"
        assert r.region == "us-east-1"
        assert r.monthly_cost == 250.0
        assert r.utilization_pct == 85.0
        assert r.coverage_status == CoverageStatus.FULLY_COVERED

    def test_eviction_at_max(self):
        eng = _engine(max_reservations=3)
        for i in range(5):
            eng.register_reservation(resource_id=f"r-{i}")
        assert len(eng._reservations) == 3


# ---------------------------------------------------------------------------
# get_reservation
# ---------------------------------------------------------------------------


class TestGetReservation:
    def test_found(self):
        eng = _engine()
        r = eng.register_reservation(resource_id="i-found")
        assert eng.get_reservation(r.id) is not None
        assert eng.get_reservation(r.id).resource_id == "i-found"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_reservation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_reservations
# ---------------------------------------------------------------------------


class TestListReservations:
    def test_list_all(self):
        eng = _engine()
        eng.register_reservation(resource_id="a")
        eng.register_reservation(resource_id="b")
        assert len(eng.list_reservations()) == 2

    def test_filter_by_commitment_type(self):
        eng = _engine()
        eng.register_reservation(resource_id="a", commitment_type=CommitmentType.SAVINGS_PLAN)
        eng.register_reservation(resource_id="b", commitment_type=CommitmentType.RESERVED_INSTANCE)
        results = eng.list_reservations(commitment_type=CommitmentType.SAVINGS_PLAN)
        assert len(results) == 1
        assert results[0].resource_id == "a"

    def test_filter_by_coverage_status(self):
        eng = _engine()
        eng.register_reservation(resource_id="a", coverage_status=CoverageStatus.FULLY_COVERED)
        eng.register_reservation(resource_id="b", coverage_status=CoverageStatus.UNCOVERED)
        results = eng.list_reservations(coverage_status=CoverageStatus.FULLY_COVERED)
        assert len(results) == 1
        assert results[0].resource_id == "a"


# ---------------------------------------------------------------------------
# analyze_coverage_gaps
# ---------------------------------------------------------------------------


class TestAnalyzeCoverageGaps:
    def test_with_uncovered_resources(self):
        eng = _engine()
        eng.register_reservation(
            resource_id="covered",
            monthly_cost=300.0,
            coverage_status=CoverageStatus.FULLY_COVERED,
        )
        eng.register_reservation(
            resource_id="uncovered-high",
            monthly_cost=600.0,
            instance_type="c5.4xlarge",
            region="us-west-2",
            coverage_status=CoverageStatus.UNCOVERED,
        )
        eng.register_reservation(
            resource_id="uncovered-mid",
            monthly_cost=200.0,
            instance_type="m5.large",
            region="eu-west-1",
            coverage_status=CoverageStatus.PARTIALLY_COVERED,
        )
        gaps = eng.analyze_coverage_gaps()
        assert len(gaps) == 2
        # High-cost gap should recommend 3-year
        high_gap = [g for g in gaps if g.resource_id == "uncovered-high"][0]
        assert high_gap.recommendation == PurchaseRecommendation.BUY_THREE_YEAR
        assert high_gap.potential_savings == 600.0 * 0.30
        # Mid-cost gap should recommend 1-year
        mid_gap = [g for g in gaps if g.resource_id == "uncovered-mid"][0]
        assert mid_gap.recommendation == PurchaseRecommendation.BUY_ONE_YEAR


# ---------------------------------------------------------------------------
# detect_expiring_commitments
# ---------------------------------------------------------------------------


class TestDetectExpiringCommitments:
    def test_with_expiring_reservations(self):
        eng = _engine(expiry_warning_days=30)
        now = time.time()
        # Expiring in 10 days — within window
        eng.register_reservation(
            resource_id="expiring-soon",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            expiry_timestamp=now + 86400 * 10,
        )
        # Expiring in 60 days — outside window
        eng.register_reservation(
            resource_id="not-expiring",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            expiry_timestamp=now + 86400 * 60,
        )
        # On-demand — should be ignored even if timestamp set
        eng.register_reservation(
            resource_id="on-demand",
            commitment_type=CommitmentType.ON_DEMAND,
            expiry_timestamp=now + 86400 * 5,
        )
        expiring = eng.detect_expiring_commitments()
        assert len(expiring) == 1
        assert expiring[0].resource_id == "expiring-soon"


# ---------------------------------------------------------------------------
# calculate_utilization_efficiency
# ---------------------------------------------------------------------------


class TestCalculateUtilizationEfficiency:
    def test_with_various_utilization_levels(self):
        eng = _engine()
        # Committed reservation — well utilized
        eng.register_reservation(
            resource_id="well-used",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            utilization_pct=90.0,
            monthly_cost=200.0,
        )
        # Committed reservation — underutilized
        eng.register_reservation(
            resource_id="under-used",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            utilization_pct=30.0,
            monthly_cost=150.0,
        )
        # On-demand — should be excluded from committed calculations
        eng.register_reservation(
            resource_id="on-demand",
            commitment_type=CommitmentType.ON_DEMAND,
            utilization_pct=50.0,
            monthly_cost=100.0,
        )
        result = eng.calculate_utilization_efficiency()
        assert result["total_committed"] == 2
        assert result["avg_utilization_pct"] == 60.0  # (90 + 30) / 2
        assert result["underutilized_count"] == 1
        assert result["well_utilized_count"] == 1
        assert len(result["underutilized_resources"]) == 1
        assert result["underutilized_resources"][0]["resource_id"] == "under-used"


# ---------------------------------------------------------------------------
# recommend_purchases
# ---------------------------------------------------------------------------


class TestRecommendPurchases:
    def test_with_gaps(self):
        eng = _engine()
        eng.register_reservation(
            resource_id="uncovered-big",
            monthly_cost=600.0,
            instance_type="r5.2xlarge",
            region="us-east-1",
            coverage_status=CoverageStatus.UNCOVERED,
        )
        eng.register_reservation(
            resource_id="uncovered-mid",
            monthly_cost=200.0,
            instance_type="m5.large",
            region="eu-west-1",
            coverage_status=CoverageStatus.UNCOVERED,
        )
        recs = eng.recommend_purchases()
        assert len(recs) == 2
        # Sorted by annual savings descending — big first
        assert recs[0]["resource_id"] == "uncovered-big"
        assert recs[0]["recommendation"] == PurchaseRecommendation.BUY_THREE_YEAR.value
        # 3-year: 600 * 0.50 * 12 = 3600
        assert recs[0]["estimated_annual_savings"] == 3600.0
        assert recs[1]["resource_id"] == "uncovered-mid"
        assert recs[1]["recommendation"] == PurchaseRecommendation.BUY_ONE_YEAR.value
        # 1-year: 200 * 0.30 * 12 = 720
        assert recs[1]["estimated_annual_savings"] == 720.0


# ---------------------------------------------------------------------------
# estimate_savings_from_conversion
# ---------------------------------------------------------------------------


class TestEstimateSavingsFromConversion:
    def test_with_ri_data(self):
        eng = _engine()
        eng.register_reservation(
            resource_id="ri-1",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            monthly_cost=400.0,
            utilization_pct=60.0,
            instance_type="m5.xlarge",
            region="us-east-1",
        )
        eng.register_reservation(
            resource_id="ri-2",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            monthly_cost=200.0,
            utilization_pct=90.0,
            instance_type="c5.large",
            region="us-west-2",
        )
        # Non-RI should be excluded
        eng.register_reservation(
            resource_id="sp-1",
            commitment_type=CommitmentType.SAVINGS_PLAN,
            monthly_cost=300.0,
        )
        result = eng.estimate_savings_from_conversion()
        assert result["ri_count"] == 2
        assert result["total_ri_monthly_cost"] == 600.0
        # 600 * 0.05 = 30.0 monthly savings
        assert result["estimated_monthly_savings"] == 30.0
        assert result["estimated_annual_savings"] == 360.0
        # Only ri-1 has utilization < 80%
        assert len(result["conversion_candidates"]) == 1
        assert result["conversion_candidates"][0]["resource_id"] == "ri-1"


# ---------------------------------------------------------------------------
# generate_optimization_report
# ---------------------------------------------------------------------------


class TestGenerateOptimizationReport:
    def test_basic_report(self):
        eng = _engine(expiry_warning_days=30)
        now = time.time()
        eng.register_reservation(
            resource_id="ri-prod",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            monthly_cost=500.0,
            utilization_pct=85.0,
            coverage_status=CoverageStatus.FULLY_COVERED,
            expiry_timestamp=now + 86400 * 365,
            region="us-east-1",
        )
        eng.register_reservation(
            resource_id="od-dev",
            commitment_type=CommitmentType.ON_DEMAND,
            monthly_cost=200.0,
            utilization_pct=50.0,
            coverage_status=CoverageStatus.UNCOVERED,
            region="us-west-2",
        )
        report = eng.generate_optimization_report()
        assert report.total_reservations == 2
        assert report.total_monthly_spend == 700.0
        assert isinstance(report.commitment_breakdown, dict)
        assert CommitmentType.RESERVED_INSTANCE.value in report.commitment_breakdown
        assert CommitmentType.ON_DEMAND.value in report.commitment_breakdown


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.register_reservation(resource_id="a", coverage_status=CoverageStatus.UNCOVERED)
        eng.analyze_coverage_gaps()
        assert len(eng._reservations) > 0
        assert len(eng._gaps) > 0
        eng.clear_data()
        assert len(eng._reservations) == 0
        assert len(eng._gaps) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_reservations"] == 0
        assert stats["total_gaps"] == 0
        assert stats["unique_resources"] == 0
        assert stats["commitment_types"] == []
        assert stats["regions"] == []

    def test_populated(self):
        eng = _engine()
        eng.register_reservation(
            resource_id="i-abc",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            region="us-east-1",
        )
        eng.register_reservation(
            resource_id="i-def",
            commitment_type=CommitmentType.SAVINGS_PLAN,
            region="eu-west-1",
        )
        stats = eng.get_stats()
        assert stats["total_reservations"] == 2
        assert stats["unique_resources"] == 2
        assert "reserved_instance" in stats["commitment_types"]
        assert "savings_plan" in stats["commitment_types"]
        assert "us-east-1" in stats["regions"]
        assert "eu-west-1" in stats["regions"]
