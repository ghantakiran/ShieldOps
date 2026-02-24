"""Reserved Instance Optimizer — RI/savings plan coverage, expiry, recommendations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CommitmentType(StrEnum):
    RESERVED_INSTANCE = "reserved_instance"
    SAVINGS_PLAN = "savings_plan"
    COMMITTED_USE = "committed_use"
    SPOT_FLEET = "spot_fleet"
    ON_DEMAND = "on_demand"


class CoverageStatus(StrEnum):
    FULLY_COVERED = "fully_covered"
    PARTIALLY_COVERED = "partially_covered"
    UNCOVERED = "uncovered"
    OVER_COMMITTED = "over_committed"
    EXPIRING_SOON = "expiring_soon"


class PurchaseRecommendation(StrEnum):
    BUY_ONE_YEAR = "buy_one_year"
    BUY_THREE_YEAR = "buy_three_year"
    CONVERT_TO_SAVINGS_PLAN = "convert_to_savings_plan"
    MAINTAIN_ON_DEMAND = "maintain_on_demand"
    DOWNGRADE_COMMITMENT = "downgrade_commitment"


# --- Models ---


class ReservationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    commitment_type: CommitmentType = CommitmentType.RESERVED_INSTANCE
    instance_type: str = ""
    region: str = ""
    monthly_cost: float = 0.0
    utilization_pct: float = 0.0
    expiry_timestamp: float = 0.0
    coverage_status: CoverageStatus = CoverageStatus.UNCOVERED
    created_at: float = Field(default_factory=time.time)


class CoverageGap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    instance_type: str = ""
    region: str = ""
    on_demand_cost: float = 0.0
    potential_savings: float = 0.0
    recommendation: PurchaseRecommendation = PurchaseRecommendation.MAINTAIN_ON_DEMAND
    created_at: float = Field(default_factory=time.time)


class RIOptimizationReport(BaseModel):
    total_reservations: int = 0
    total_monthly_spend: float = 0.0
    avg_utilization_pct: float = 0.0
    expiring_count: int = 0
    coverage_gap_count: int = 0
    potential_annual_savings: float = 0.0
    commitment_breakdown: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReservedInstanceOptimizer:
    """RI/savings plan coverage analysis, expiry tracking, and purchase recommendations."""

    # Discount rates for savings estimation
    _ONE_YEAR_DISCOUNT = 0.30  # 30% savings over on-demand
    _THREE_YEAR_DISCOUNT = 0.50  # 50% savings over on-demand
    _SAVINGS_PLAN_DISCOUNT = 0.35  # 35% savings via savings plans

    def __init__(
        self,
        max_reservations: int = 100000,
        expiry_warning_days: int = 30,
    ) -> None:
        self._max_reservations = max_reservations
        self._expiry_warning_days = expiry_warning_days
        self._reservations: list[ReservationRecord] = []
        self._gaps: list[CoverageGap] = []
        logger.info(
            "ri_optimizer.initialized",
            max_reservations=max_reservations,
            expiry_warning_days=expiry_warning_days,
        )

    def register_reservation(
        self,
        resource_id: str,
        commitment_type: CommitmentType = CommitmentType.RESERVED_INSTANCE,
        instance_type: str = "",
        region: str = "",
        monthly_cost: float = 0.0,
        utilization_pct: float = 0.0,
        expiry_timestamp: float = 0.0,
        coverage_status: CoverageStatus = CoverageStatus.UNCOVERED,
    ) -> ReservationRecord:
        record = ReservationRecord(
            resource_id=resource_id,
            commitment_type=commitment_type,
            instance_type=instance_type,
            region=region,
            monthly_cost=monthly_cost,
            utilization_pct=utilization_pct,
            expiry_timestamp=expiry_timestamp,
            coverage_status=coverage_status,
        )
        self._reservations.append(record)
        if len(self._reservations) > self._max_reservations:
            self._reservations = self._reservations[-self._max_reservations :]
        logger.info(
            "ri_optimizer.reservation_registered",
            reservation_id=record.id,
            resource_id=resource_id,
            commitment_type=commitment_type,
            instance_type=instance_type,
            region=region,
        )
        return record

    def get_reservation(self, reservation_id: str) -> ReservationRecord | None:
        for r in self._reservations:
            if r.id == reservation_id:
                return r
        return None

    def list_reservations(
        self,
        commitment_type: CommitmentType | None = None,
        coverage_status: CoverageStatus | None = None,
        limit: int = 100,
    ) -> list[ReservationRecord]:
        results = list(self._reservations)
        if commitment_type is not None:
            results = [r for r in results if r.commitment_type == commitment_type]
        if coverage_status is not None:
            results = [r for r in results if r.coverage_status == coverage_status]
        return results[-limit:]

    def analyze_coverage_gaps(self) -> list[CoverageGap]:
        """Find UNCOVERED/PARTIALLY_COVERED reservations and estimate savings from commitments."""
        new_gaps: list[CoverageGap] = []

        for r in self._reservations:
            if r.coverage_status not in (
                CoverageStatus.UNCOVERED,
                CoverageStatus.PARTIALLY_COVERED,
            ):
                continue

            on_demand_cost = r.monthly_cost
            # Estimate savings from a 1-year RI commitment
            potential_savings = round(on_demand_cost * self._ONE_YEAR_DISCOUNT, 2)

            # Determine recommendation based on cost magnitude
            if on_demand_cost >= 500:
                recommendation = PurchaseRecommendation.BUY_THREE_YEAR
            elif on_demand_cost >= 100:
                recommendation = PurchaseRecommendation.BUY_ONE_YEAR
            else:
                recommendation = PurchaseRecommendation.MAINTAIN_ON_DEMAND

            gap = CoverageGap(
                resource_id=r.resource_id,
                instance_type=r.instance_type,
                region=r.region,
                on_demand_cost=on_demand_cost,
                potential_savings=potential_savings,
                recommendation=recommendation,
            )
            new_gaps.append(gap)

        self._gaps.extend(new_gaps)
        if len(self._gaps) > self._max_reservations:
            self._gaps = self._gaps[-self._max_reservations :]

        logger.info(
            "ri_optimizer.coverage_gaps_analyzed",
            gap_count=len(new_gaps),
        )
        return new_gaps

    def detect_expiring_commitments(self) -> list[ReservationRecord]:
        """Find reservations expiring within the warning window from now."""
        now = time.time()
        warning_threshold = now + (self._expiry_warning_days * 86400)

        expiring: list[ReservationRecord] = []
        for r in self._reservations:
            if r.expiry_timestamp <= 0:
                continue
            if r.commitment_type == CommitmentType.ON_DEMAND:
                continue
            if now <= r.expiry_timestamp <= warning_threshold:
                expiring.append(r)

        expiring.sort(key=lambda r: r.expiry_timestamp)
        logger.info(
            "ri_optimizer.expiring_commitments_detected",
            expiring_count=len(expiring),
            warning_days=self._expiry_warning_days,
        )
        return expiring

    def calculate_utilization_efficiency(self) -> dict[str, Any]:
        """Calculate average utilization and identify underutilized reservations."""
        committed = [r for r in self._reservations if r.commitment_type != CommitmentType.ON_DEMAND]
        if not committed:
            return {
                "avg_utilization_pct": 0.0,
                "total_committed": 0,
                "underutilized_count": 0,
                "underutilized_resources": [],
                "well_utilized_count": 0,
            }

        total_util = sum(r.utilization_pct for r in committed)
        avg_util = round(total_util / len(committed), 2)

        underutilized = [r for r in committed if r.utilization_pct < 50.0]
        well_utilized = [r for r in committed if r.utilization_pct >= 80.0]

        underutilized_resources = [
            {
                "reservation_id": r.id,
                "resource_id": r.resource_id,
                "instance_type": r.instance_type,
                "utilization_pct": r.utilization_pct,
                "monthly_cost": r.monthly_cost,
                "wasted_spend": round(r.monthly_cost * (1 - r.utilization_pct / 100), 2),
            }
            for r in underutilized
        ]

        return {
            "avg_utilization_pct": avg_util,
            "total_committed": len(committed),
            "underutilized_count": len(underutilized),
            "underutilized_resources": underutilized_resources,
            "well_utilized_count": len(well_utilized),
        }

    def recommend_purchases(self) -> list[dict[str, Any]]:
        """Generate purchase recommendations based on coverage gaps."""
        gaps = self.analyze_coverage_gaps()
        recommendations: list[dict[str, Any]] = []

        for gap in gaps:
            if gap.recommendation == PurchaseRecommendation.MAINTAIN_ON_DEMAND:
                continue

            if gap.recommendation == PurchaseRecommendation.BUY_THREE_YEAR:
                estimated_savings = round(gap.on_demand_cost * self._THREE_YEAR_DISCOUNT * 12, 2)
            else:
                estimated_savings = round(gap.on_demand_cost * self._ONE_YEAR_DISCOUNT * 12, 2)

            recommendations.append(
                {
                    "resource_id": gap.resource_id,
                    "instance_type": gap.instance_type,
                    "region": gap.region,
                    "current_monthly_cost": gap.on_demand_cost,
                    "recommendation": gap.recommendation.value,
                    "estimated_annual_savings": estimated_savings,
                    "reason": (
                        f"Resource '{gap.resource_id}' ({gap.instance_type}) in {gap.region} "
                        f"is {CoverageStatus.UNCOVERED.value} — "
                        f"estimated ${estimated_savings:.2f}/yr savings"
                    ),
                }
            )

        recommendations.sort(key=lambda x: x["estimated_annual_savings"], reverse=True)
        logger.info(
            "ri_optimizer.purchases_recommended",
            recommendation_count=len(recommendations),
        )
        return recommendations

    def estimate_savings_from_conversion(self) -> dict[str, Any]:
        """Estimate savings from converting existing RIs to savings plans."""
        ri_records = [
            r for r in self._reservations if r.commitment_type == CommitmentType.RESERVED_INSTANCE
        ]
        if not ri_records:
            return {
                "ri_count": 0,
                "total_ri_monthly_cost": 0.0,
                "estimated_monthly_savings": 0.0,
                "estimated_annual_savings": 0.0,
                "conversion_candidates": [],
            }

        total_ri_cost = sum(r.monthly_cost for r in ri_records)
        # Savings plans typically offer additional 5% over RI pricing via flexibility
        additional_savings_rate = 0.05
        monthly_savings = round(total_ri_cost * additional_savings_rate, 2)
        annual_savings = round(monthly_savings * 12, 2)

        # Identify best conversion candidates (underutilized RIs benefit most from flexibility)
        candidates: list[dict[str, Any]] = []
        for r in ri_records:
            if r.utilization_pct < 80.0:
                candidate_savings = round(r.monthly_cost * additional_savings_rate, 2)
                candidates.append(
                    {
                        "reservation_id": r.id,
                        "resource_id": r.resource_id,
                        "instance_type": r.instance_type,
                        "region": r.region,
                        "current_utilization": r.utilization_pct,
                        "monthly_savings": candidate_savings,
                        "reason": (
                            f"RI for '{r.resource_id}' at {r.utilization_pct:.0f}% utilization "
                            f"would benefit from savings plan flexibility"
                        ),
                    }
                )

        candidates.sort(key=lambda x: x["monthly_savings"], reverse=True)

        return {
            "ri_count": len(ri_records),
            "total_ri_monthly_cost": round(total_ri_cost, 2),
            "estimated_monthly_savings": monthly_savings,
            "estimated_annual_savings": annual_savings,
            "conversion_candidates": candidates,
        }

    def generate_optimization_report(self) -> RIOptimizationReport:
        total = len(self._reservations)
        if total == 0:
            return RIOptimizationReport()

        # Total monthly spend
        total_monthly = sum(r.monthly_cost for r in self._reservations)

        # Average utilization (committed only)
        util_analysis = self.calculate_utilization_efficiency()
        avg_util = util_analysis["avg_utilization_pct"]

        # Expiring commitments
        expiring = self.detect_expiring_commitments()

        # Coverage gaps
        gaps = self.analyze_coverage_gaps()

        # Potential annual savings from gaps
        potential_annual = round(sum(g.potential_savings for g in gaps) * 12, 2)

        # Commitment type breakdown
        commitment_counts: dict[str, int] = {}
        for r in self._reservations:
            key = r.commitment_type.value
            commitment_counts[key] = commitment_counts.get(key, 0) + 1

        # Build recommendations
        recommendations: list[str] = []
        if gaps:
            high_value_gaps = [g for g in gaps if g.on_demand_cost >= 500]
            if high_value_gaps:
                recommendations.append(
                    f"{len(high_value_gaps)} high-value resource(s) uncovered — "
                    f"purchase 3-year commitments for maximum savings"
                )
            medium_gaps = [g for g in gaps if 100 <= g.on_demand_cost < 500]
            if medium_gaps:
                recommendations.append(
                    f"{len(medium_gaps)} medium-cost resource(s) uncovered — "
                    f"consider 1-year reserved instances"
                )

        if expiring:
            recommendations.append(
                f"{len(expiring)} commitment(s) expiring within "
                f"{self._expiry_warning_days} days — review and renew"
            )

        underutilized_count = util_analysis["underutilized_count"]
        if underutilized_count > 0:
            recommendations.append(
                f"{underutilized_count} reservation(s) below 50% utilization — "
                f"consider downsizing or converting to savings plans"
            )

        conversion = self.estimate_savings_from_conversion()
        if conversion["estimated_annual_savings"] > 0:
            recommendations.append(
                f"Converting RIs to savings plans could save "
                f"${conversion['estimated_annual_savings']:.2f}/year"
            )

        report = RIOptimizationReport(
            total_reservations=total,
            total_monthly_spend=round(total_monthly, 2),
            avg_utilization_pct=avg_util,
            expiring_count=len(expiring),
            coverage_gap_count=len(gaps),
            potential_annual_savings=potential_annual,
            commitment_breakdown=commitment_counts,
            recommendations=recommendations,
        )
        logger.info(
            "ri_optimizer.report_generated",
            total_reservations=total,
            total_monthly_spend=round(total_monthly, 2),
            coverage_gaps=len(gaps),
            potential_annual_savings=potential_annual,
        )
        return report

    def clear_data(self) -> None:
        self._reservations.clear()
        self._gaps.clear()
        logger.info("ri_optimizer.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        resource_ids = {r.resource_id for r in self._reservations}
        commitment_types = {r.commitment_type.value for r in self._reservations}
        regions = {r.region for r in self._reservations if r.region}
        return {
            "total_reservations": len(self._reservations),
            "total_gaps": len(self._gaps),
            "unique_resources": len(resource_ids),
            "commitment_types": sorted(commitment_types),
            "regions": sorted(regions),
        }
