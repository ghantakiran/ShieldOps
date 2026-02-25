"""Tests for shieldops.billing.discount_optimizer — CloudDiscountOptimizer."""

from __future__ import annotations

from shieldops.billing.discount_optimizer import (
    CloudDiscountOptimizer,
    CloudProvider,
    CoverageStatus,
    DiscountOptimizerReport,
    DiscountRecord,
    DiscountStrategy,
    DiscountType,
)


def _engine(**kw) -> CloudDiscountOptimizer:
    return CloudDiscountOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # DiscountType (5)
    def test_type_reserved_instance(self):
        assert DiscountType.RESERVED_INSTANCE == "reserved_instance"

    def test_type_savings_plan(self):
        assert DiscountType.SAVINGS_PLAN == "savings_plan"

    def test_type_spot_instance(self):
        assert DiscountType.SPOT_INSTANCE == "spot_instance"

    def test_type_sustained_use(self):
        assert DiscountType.SUSTAINED_USE == "sustained_use"

    def test_type_enterprise_discount(self):
        assert DiscountType.ENTERPRISE_DISCOUNT == "enterprise_discount"

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

    # CloudProvider (5)
    def test_provider_aws(self):
        assert CloudProvider.AWS == "aws"

    def test_provider_gcp(self):
        assert CloudProvider.GCP == "gcp"

    def test_provider_azure(self):
        assert CloudProvider.AZURE == "azure"

    def test_provider_multi_cloud(self):
        assert CloudProvider.MULTI_CLOUD == "multi_cloud"

    def test_provider_on_prem(self):
        assert CloudProvider.ON_PREM == "on_prem"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_discount_record_defaults(self):
        r = DiscountRecord()
        assert r.id
        assert r.name == ""
        assert r.discount_type == DiscountType.RESERVED_INSTANCE
        assert r.provider == CloudProvider.AWS
        assert r.coverage_status == CoverageStatus.UNCOVERED
        assert r.monthly_spend == 0.0
        assert r.monthly_savings == 0.0
        assert r.coverage_pct == 0.0
        assert r.expiry_days == 365
        assert r.created_at > 0

    def test_discount_strategy_defaults(self):
        s = DiscountStrategy()
        assert s.id
        assert s.provider == CloudProvider.AWS
        assert s.recommended_mix == {}
        assert s.total_monthly_spend == 0.0
        assert s.potential_savings == 0.0
        assert s.coverage_target_pct == 70.0
        assert s.current_coverage_pct == 0.0
        assert s.created_at > 0

    def test_discount_optimizer_report_defaults(self):
        r = DiscountOptimizerReport()
        assert r.total_discounts == 0
        assert r.total_monthly_spend == 0.0
        assert r.total_monthly_savings == 0.0
        assert r.avg_coverage_pct == 0.0
        assert r.by_type == {}
        assert r.by_provider == {}
        assert r.expiring_soon_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_discount
# ---------------------------------------------------------------------------


class TestRecordDiscount:
    def test_basic(self):
        eng = _engine()
        r = eng.record_discount(
            name="prod-ri-01",
            discount_type=DiscountType.RESERVED_INSTANCE,
        )
        assert r.name == "prod-ri-01"
        assert r.discount_type == DiscountType.RESERVED_INSTANCE
        assert r.coverage_status == CoverageStatus.UNCOVERED

    def test_with_params(self):
        eng = _engine()
        r = eng.record_discount(
            name="prod-sp-01",
            discount_type=DiscountType.SAVINGS_PLAN,
            provider=CloudProvider.GCP,
            monthly_spend=5000.0,
            monthly_savings=1500.0,
            coverage_pct=95.0,
            expiry_days=180,
        )
        assert r.provider == CloudProvider.GCP
        assert r.monthly_spend == 5000.0
        assert r.monthly_savings == 1500.0
        assert r.coverage_pct == 95.0
        assert r.coverage_status == CoverageStatus.FULLY_COVERED

    def test_expiring_soon_status(self):
        eng = _engine()
        r = eng.record_discount(
            name="expiring-ri",
            discount_type=DiscountType.RESERVED_INSTANCE,
            coverage_pct=95.0,
            expiry_days=15,
        )
        assert r.coverage_status == CoverageStatus.EXPIRING_SOON

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_discount(
                name=f"disc-{i}",
                discount_type=DiscountType.RESERVED_INSTANCE,
            )
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_discount
# ---------------------------------------------------------------------------


class TestGetDiscount:
    def test_found(self):
        eng = _engine()
        r = eng.record_discount(
            name="prod-ri-01",
            discount_type=DiscountType.RESERVED_INSTANCE,
        )
        result = eng.get_discount(r.id)
        assert result is not None
        assert result.name == "prod-ri-01"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_discount("nonexistent") is None


# ---------------------------------------------------------------------------
# list_discounts
# ---------------------------------------------------------------------------


class TestListDiscounts:
    def test_list_all(self):
        eng = _engine()
        eng.record_discount(name="d1", discount_type=DiscountType.RESERVED_INSTANCE)
        eng.record_discount(name="d2", discount_type=DiscountType.SAVINGS_PLAN)
        assert len(eng.list_discounts()) == 2

    def test_filter_by_provider(self):
        eng = _engine()
        eng.record_discount(
            name="d1",
            discount_type=DiscountType.RESERVED_INSTANCE,
            provider=CloudProvider.AWS,
        )
        eng.record_discount(
            name="d2",
            discount_type=DiscountType.SAVINGS_PLAN,
            provider=CloudProvider.GCP,
        )
        results = eng.list_discounts(provider=CloudProvider.AWS)
        assert len(results) == 1
        assert results[0].provider == CloudProvider.AWS

    def test_filter_by_discount_type(self):
        eng = _engine()
        eng.record_discount(name="d1", discount_type=DiscountType.RESERVED_INSTANCE)
        eng.record_discount(name="d2", discount_type=DiscountType.SAVINGS_PLAN)
        results = eng.list_discounts(discount_type=DiscountType.SAVINGS_PLAN)
        assert len(results) == 1
        assert results[0].discount_type == DiscountType.SAVINGS_PLAN


# ---------------------------------------------------------------------------
# generate_strategy
# ---------------------------------------------------------------------------


class TestGenerateStrategy:
    def test_with_records(self):
        eng = _engine()
        eng.record_discount(
            name="d1",
            discount_type=DiscountType.RESERVED_INSTANCE,
            provider=CloudProvider.AWS,
            monthly_spend=10000.0,
            coverage_pct=80.0,
        )
        strategy = eng.generate_strategy(provider=CloudProvider.AWS)
        assert strategy.provider == CloudProvider.AWS
        assert strategy.total_monthly_spend == 10000.0
        assert strategy.current_coverage_pct == 80.0
        assert len(strategy.recommended_mix) > 0

    def test_no_records(self):
        eng = _engine()
        strategy = eng.generate_strategy(provider=CloudProvider.GCP)
        assert strategy.provider == CloudProvider.GCP
        assert strategy.total_monthly_spend == 0.0
        assert strategy.recommended_mix == {}


# ---------------------------------------------------------------------------
# calculate_coverage_gaps
# ---------------------------------------------------------------------------


class TestCalculateCoverageGaps:
    def test_has_gaps(self):
        eng = _engine(min_coverage_pct=70.0)
        eng.record_discount(
            name="d1",
            discount_type=DiscountType.RESERVED_INSTANCE,
            coverage_pct=40.0,
            monthly_spend=5000.0,
        )
        eng.record_discount(
            name="d2",
            discount_type=DiscountType.SAVINGS_PLAN,
            coverage_pct=90.0,
            monthly_spend=8000.0,
        )
        gaps = eng.calculate_coverage_gaps()
        assert len(gaps) == 1
        assert gaps[0]["name"] == "d1"
        assert gaps[0]["gap_pct"] == 30.0

    def test_no_gaps(self):
        eng = _engine(min_coverage_pct=70.0)
        eng.record_discount(
            name="d1",
            discount_type=DiscountType.RESERVED_INSTANCE,
            coverage_pct=90.0,
        )
        gaps = eng.calculate_coverage_gaps()
        assert gaps == []


# ---------------------------------------------------------------------------
# identify_expiring_discounts
# ---------------------------------------------------------------------------


class TestIdentifyExpiringDiscounts:
    def test_has_expiring(self):
        eng = _engine()
        eng.record_discount(
            name="expiring",
            discount_type=DiscountType.RESERVED_INSTANCE,
            expiry_days=30,
        )
        eng.record_discount(
            name="safe",
            discount_type=DiscountType.SAVINGS_PLAN,
            expiry_days=200,
        )
        results = eng.identify_expiring_discounts(within_days=60)
        assert len(results) == 1
        assert results[0]["name"] == "expiring"
        assert results[0]["expiry_days"] == 30

    def test_no_expiring(self):
        eng = _engine()
        eng.record_discount(
            name="safe",
            discount_type=DiscountType.RESERVED_INSTANCE,
            expiry_days=200,
        )
        results = eng.identify_expiring_discounts(within_days=60)
        assert results == []


# ---------------------------------------------------------------------------
# optimize_portfolio_mix
# ---------------------------------------------------------------------------


class TestOptimizePortfolioMix:
    def test_with_records(self):
        eng = _engine()
        eng.record_discount(
            name="d1",
            discount_type=DiscountType.RESERVED_INSTANCE,
            monthly_spend=6000.0,
        )
        eng.record_discount(
            name="d2",
            discount_type=DiscountType.SAVINGS_PLAN,
            monthly_spend=4000.0,
        )
        result = eng.optimize_portfolio_mix()
        assert result["total_monthly_spend"] == 10000.0
        assert result["total_discounts"] == 2
        assert "reserved_instance" in result["current_mix"]
        assert "savings_plan" in result["current_mix"]
        assert len(result["target_mix"]) == 5

    def test_empty(self):
        eng = _engine()
        result = eng.optimize_portfolio_mix()
        assert result["total_monthly_spend"] == 0.0
        assert result["current_mix"] == {}
        assert result["total_discounts"] == 0


# ---------------------------------------------------------------------------
# estimate_savings_potential
# ---------------------------------------------------------------------------


class TestEstimateSavingsPotential:
    def test_with_records(self):
        eng = _engine()
        eng.record_discount(
            name="d1",
            discount_type=DiscountType.RESERVED_INSTANCE,
            monthly_spend=10000.0,
            monthly_savings=1000.0,
            coverage_pct=80.0,
        )
        result = eng.estimate_savings_potential()
        assert result["total_monthly_spend"] == 10000.0
        assert result["current_monthly_savings"] == 1000.0
        assert result["potential_additional_savings"] == 2000.0
        assert result["current_savings_rate_pct"] == 10.0
        assert result["avg_coverage_pct"] == 80.0

    def test_empty(self):
        eng = _engine()
        result = eng.estimate_savings_potential()
        assert result["total_monthly_spend"] == 0.0
        assert result["current_monthly_savings"] == 0.0
        assert result["potential_additional_savings"] == 0.0
        assert result["avg_coverage_pct"] == 0.0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_discount(
            name="d1",
            discount_type=DiscountType.RESERVED_INSTANCE,
            provider=CloudProvider.AWS,
            monthly_spend=5000.0,
            monthly_savings=1000.0,
            coverage_pct=40.0,
        )
        eng.record_discount(
            name="d2",
            discount_type=DiscountType.SAVINGS_PLAN,
            provider=CloudProvider.GCP,
            monthly_spend=3000.0,
            monthly_savings=500.0,
            coverage_pct=90.0,
            expiry_days=20,
        )
        report = eng.generate_report()
        assert isinstance(report, DiscountOptimizerReport)
        assert report.total_discounts == 2
        assert report.total_monthly_spend == 8000.0
        assert report.total_monthly_savings == 1500.0
        assert len(report.by_type) == 2
        assert len(report.by_provider) == 2
        assert report.expiring_soon_count >= 1
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_discounts == 0
        assert report.total_monthly_spend == 0.0
        assert len(report.recommendations) > 0
        assert "Average coverage 0.0% below target 70.0%" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_discount(
            name="d1",
            discount_type=DiscountType.RESERVED_INSTANCE,
        )
        eng.generate_strategy()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._strategies) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_discounts"] == 0
        assert stats["total_strategies"] == 0
        assert stats["type_distribution"] == {}
        assert stats["unique_providers"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_discount(
            name="d1",
            discount_type=DiscountType.RESERVED_INSTANCE,
            provider=CloudProvider.AWS,
        )
        eng.generate_strategy()
        stats = eng.get_stats()
        assert stats["total_discounts"] == 1
        assert stats["total_strategies"] == 1
        assert stats["min_coverage_pct"] == 70.0
        assert "reserved_instance" in stats["type_distribution"]
        assert stats["unique_providers"] == 1
