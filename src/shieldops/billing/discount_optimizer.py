"""Cloud Discount Optimizer — optimize discount portfolio mix across RIs, savings plans, spot."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DiscountType(StrEnum):
    RESERVED_INSTANCE = "reserved_instance"
    SAVINGS_PLAN = "savings_plan"
    SPOT_INSTANCE = "spot_instance"
    SUSTAINED_USE = "sustained_use"
    ENTERPRISE_DISCOUNT = "enterprise_discount"


class CoverageStatus(StrEnum):
    FULLY_COVERED = "fully_covered"
    PARTIALLY_COVERED = "partially_covered"
    UNCOVERED = "uncovered"
    OVER_COMMITTED = "over_committed"
    EXPIRING_SOON = "expiring_soon"


class CloudProvider(StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    MULTI_CLOUD = "multi_cloud"
    ON_PREM = "on_prem"


# --- Models ---


class DiscountRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    discount_type: DiscountType = DiscountType.RESERVED_INSTANCE
    provider: CloudProvider = CloudProvider.AWS
    coverage_status: CoverageStatus = CoverageStatus.UNCOVERED
    monthly_spend: float = 0.0
    monthly_savings: float = 0.0
    coverage_pct: float = 0.0
    expiry_days: int = 365
    created_at: float = Field(default_factory=time.time)


class DiscountStrategy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    provider: CloudProvider = CloudProvider.AWS
    recommended_mix: dict[str, float] = Field(default_factory=dict)
    total_monthly_spend: float = 0.0
    potential_savings: float = 0.0
    coverage_target_pct: float = 70.0
    current_coverage_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class DiscountOptimizerReport(BaseModel):
    total_discounts: int = 0
    total_monthly_spend: float = 0.0
    total_monthly_savings: float = 0.0
    avg_coverage_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_provider: dict[str, int] = Field(default_factory=dict)
    expiring_soon_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CloudDiscountOptimizer:
    """Optimize discount portfolio mix across RIs, savings plans, spot, and enterprise discounts."""

    def __init__(
        self,
        max_records: int = 200000,
        min_coverage_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_coverage_pct = min_coverage_pct
        self._records: list[DiscountRecord] = []
        self._strategies: list[DiscountStrategy] = []
        logger.info(
            "discount_optimizer.initialized",
            max_records=max_records,
            min_coverage_pct=min_coverage_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _coverage_to_status(self, coverage_pct: float, expiry_days: int) -> CoverageStatus:
        if expiry_days < 30:
            return CoverageStatus.EXPIRING_SOON
        if coverage_pct > 100:
            return CoverageStatus.OVER_COMMITTED
        if coverage_pct >= 90:
            return CoverageStatus.FULLY_COVERED
        if coverage_pct >= 50:
            return CoverageStatus.PARTIALLY_COVERED
        return CoverageStatus.UNCOVERED

    # -- record / get / list ---------------------------------------------

    def record_discount(
        self,
        name: str,
        discount_type: DiscountType,
        provider: CloudProvider = CloudProvider.AWS,
        monthly_spend: float = 0.0,
        monthly_savings: float = 0.0,
        coverage_pct: float = 0.0,
        expiry_days: int = 365,
    ) -> DiscountRecord:
        coverage_status = self._coverage_to_status(coverage_pct, expiry_days)
        record = DiscountRecord(
            name=name,
            discount_type=discount_type,
            provider=provider,
            coverage_status=coverage_status,
            monthly_spend=monthly_spend,
            monthly_savings=monthly_savings,
            coverage_pct=coverage_pct,
            expiry_days=expiry_days,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "discount_optimizer.discount_recorded",
            record_id=record.id,
            name=name,
            discount_type=discount_type.value,
            coverage_pct=coverage_pct,
        )
        return record

    def get_discount(self, record_id: str) -> DiscountRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_discounts(
        self,
        provider: CloudProvider | None = None,
        discount_type: DiscountType | None = None,
        limit: int = 50,
    ) -> list[DiscountRecord]:
        results = list(self._records)
        if provider is not None:
            results = [r for r in results if r.provider == provider]
        if discount_type is not None:
            results = [r for r in results if r.discount_type == discount_type]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def generate_strategy(self, provider: CloudProvider = CloudProvider.AWS) -> DiscountStrategy:
        """Generate an optimal discount portfolio strategy for a provider."""
        provider_records = [r for r in self._records if r.provider == provider]
        if not provider_records:
            strategy = DiscountStrategy(
                provider=provider,
                coverage_target_pct=self._min_coverage_pct,
            )
            self._strategies.append(strategy)
            return strategy

        total_spend = sum(r.monthly_spend for r in provider_records)
        total_savings = sum(r.monthly_savings for r in provider_records)
        avg_coverage = round(
            sum(r.coverage_pct for r in provider_records) / len(provider_records), 2
        )

        # Recommend mix based on current distribution
        type_spend: dict[str, float] = {}
        for r in provider_records:
            type_spend[r.discount_type.value] = (
                type_spend.get(r.discount_type.value, 0) + r.monthly_spend
            )
        recommended_mix = {
            k: round(v / total_spend * 100, 2) if total_spend > 0 else 0.0
            for k, v in type_spend.items()
        }

        potential = round(total_spend * 0.3 - total_savings, 2) if total_spend > 0 else 0.0
        potential = max(0, potential)

        strategy = DiscountStrategy(
            provider=provider,
            recommended_mix=recommended_mix,
            total_monthly_spend=total_spend,
            potential_savings=potential,
            coverage_target_pct=self._min_coverage_pct,
            current_coverage_pct=avg_coverage,
        )
        self._strategies.append(strategy)
        if len(self._strategies) > self._max_records:
            self._strategies = self._strategies[-self._max_records :]
        logger.info(
            "discount_optimizer.strategy_generated",
            strategy_id=strategy.id,
            provider=provider.value,
            current_coverage=avg_coverage,
        )
        return strategy

    def calculate_coverage_gaps(self) -> list[dict[str, Any]]:
        """Find resources with coverage below minimum threshold."""
        gaps: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_pct < self._min_coverage_pct:
                gaps.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "provider": r.provider.value,
                        "coverage_pct": r.coverage_pct,
                        "gap_pct": round(self._min_coverage_pct - r.coverage_pct, 2),
                        "monthly_spend": r.monthly_spend,
                    }
                )
        gaps.sort(key=lambda x: x["gap_pct"], reverse=True)
        return gaps

    def identify_expiring_discounts(self, within_days: int = 60) -> list[dict[str, Any]]:
        """Find discounts expiring within N days."""
        expiring = [r for r in self._records if r.expiry_days <= within_days]
        return [
            {
                "record_id": r.id,
                "name": r.name,
                "discount_type": r.discount_type.value,
                "provider": r.provider.value,
                "expiry_days": r.expiry_days,
                "monthly_savings": r.monthly_savings,
            }
            for r in sorted(expiring, key=lambda x: x.expiry_days)
        ]

    def optimize_portfolio_mix(self) -> dict[str, Any]:
        """Suggest optimal portfolio mix across all providers."""
        by_type: dict[str, float] = {}
        total_spend = 0.0
        for r in self._records:
            by_type[r.discount_type.value] = by_type.get(r.discount_type.value, 0) + r.monthly_spend
            total_spend += r.monthly_spend
        current_mix = {
            k: round(v / total_spend * 100, 2) if total_spend > 0 else 0.0
            for k, v in by_type.items()
        }
        # Recommended target mix
        target_mix = {
            DiscountType.RESERVED_INSTANCE.value: 40.0,
            DiscountType.SAVINGS_PLAN.value: 30.0,
            DiscountType.SPOT_INSTANCE.value: 15.0,
            DiscountType.SUSTAINED_USE.value: 10.0,
            DiscountType.ENTERPRISE_DISCOUNT.value: 5.0,
        }
        return {
            "total_monthly_spend": total_spend,
            "current_mix": current_mix,
            "target_mix": target_mix,
            "total_discounts": len(self._records),
        }

    def estimate_savings_potential(self) -> dict[str, Any]:
        """Estimate potential savings from optimization."""
        total_spend = sum(r.monthly_spend for r in self._records)
        current_savings = sum(r.monthly_savings for r in self._records)
        avg_coverage = (
            round(sum(r.coverage_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        potential = round(total_spend * 0.3 - current_savings, 2) if total_spend > 0 else 0.0
        potential = max(0, potential)
        return {
            "total_monthly_spend": total_spend,
            "current_monthly_savings": current_savings,
            "potential_additional_savings": potential,
            "current_savings_rate_pct": (
                round(current_savings / total_spend * 100, 2) if total_spend > 0 else 0.0
            ),
            "avg_coverage_pct": avg_coverage,
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DiscountOptimizerReport:
        by_type: dict[str, int] = {}
        by_provider: dict[str, int] = {}
        for r in self._records:
            by_type[r.discount_type.value] = by_type.get(r.discount_type.value, 0) + 1
            by_provider[r.provider.value] = by_provider.get(r.provider.value, 0) + 1
        total_spend = sum(r.monthly_spend for r in self._records)
        total_savings = sum(r.monthly_savings for r in self._records)
        avg_coverage = (
            round(sum(r.coverage_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        expiring = sum(1 for r in self._records if r.expiry_days < 60)
        recs: list[str] = []
        if avg_coverage < self._min_coverage_pct:
            recs.append(f"Average coverage {avg_coverage}% below target {self._min_coverage_pct}%")
        if expiring > 0:
            recs.append(f"{expiring} discount(s) expiring within 60 days")
        uncovered = sum(1 for r in self._records if r.coverage_status == CoverageStatus.UNCOVERED)
        if uncovered > 0:
            recs.append(f"{uncovered} resource(s) have no discount coverage")
        if not recs:
            recs.append("Discount portfolio well-optimized")
        return DiscountOptimizerReport(
            total_discounts=len(self._records),
            total_monthly_spend=total_spend,
            total_monthly_savings=total_savings,
            avg_coverage_pct=avg_coverage,
            by_type=by_type,
            by_provider=by_provider,
            expiring_soon_count=expiring,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._strategies.clear()
        logger.info("discount_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.discount_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_discounts": len(self._records),
            "total_strategies": len(self._strategies),
            "min_coverage_pct": self._min_coverage_pct,
            "type_distribution": type_dist,
            "unique_providers": len({r.provider for r in self._records}),
        }
