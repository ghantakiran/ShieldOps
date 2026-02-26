"""Spot Instance Advisor — advise on spot/preemptible instance usage and savings."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SpotMarket(StrEnum):
    AWS_SPOT = "aws_spot"
    GCP_PREEMPTIBLE = "gcp_preemptible"
    AZURE_SPOT = "azure_spot"
    ON_DEMAND = "on_demand"
    RESERVED = "reserved"


class InterruptionRisk(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


class SavingsGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    MARGINAL = "marginal"
    NOT_RECOMMENDED = "not_recommended"


# --- Models ---


class SpotUsageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    instance_type: str = ""
    market: SpotMarket = SpotMarket.ON_DEMAND
    interruption_risk: InterruptionRisk = InterruptionRisk.MODERATE
    savings_pct: float = 0.0
    monthly_cost: float = 0.0
    on_demand_cost: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class SpotRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    instance_type: str = ""
    recommended_market: SpotMarket = SpotMarket.AWS_SPOT
    savings_grade: SavingsGrade = SavingsGrade.MODERATE
    estimated_savings_pct: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class SpotAdvisorReport(BaseModel):
    total_records: int = 0
    total_recommendations: int = 0
    avg_savings_pct: float = 0.0
    by_market: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    high_savings_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SpotInstanceAdvisor:
    """Advise on spot/preemptible instance usage and savings."""

    def __init__(
        self,
        max_records: int = 200000,
        min_savings_pct: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._min_savings_pct = min_savings_pct
        self._records: list[SpotUsageRecord] = []
        self._recommendations: list[SpotRecommendation] = []
        logger.info(
            "spot_advisor.initialized",
            max_records=max_records,
            min_savings_pct=min_savings_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _savings_to_grade(self, savings: float) -> SavingsGrade:
        if savings >= 70:
            return SavingsGrade.EXCELLENT
        if savings >= 50:
            return SavingsGrade.GOOD
        if savings >= 30:
            return SavingsGrade.MODERATE
        if savings >= 15:
            return SavingsGrade.MARGINAL
        return SavingsGrade.NOT_RECOMMENDED

    # -- record / get / list ---------------------------------------------

    def record_usage(
        self,
        instance_type: str,
        market: SpotMarket = SpotMarket.ON_DEMAND,
        interruption_risk: InterruptionRisk = InterruptionRisk.MODERATE,
        savings_pct: float = 0.0,
        monthly_cost: float = 0.0,
        on_demand_cost: float = 0.0,
        details: str = "",
    ) -> SpotUsageRecord:
        record = SpotUsageRecord(
            instance_type=instance_type,
            market=market,
            interruption_risk=interruption_risk,
            savings_pct=savings_pct,
            monthly_cost=monthly_cost,
            on_demand_cost=on_demand_cost,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "spot_advisor.usage_recorded",
            record_id=record.id,
            instance_type=instance_type,
            market=market.value,
        )
        return record

    def get_usage(self, record_id: str) -> SpotUsageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_usage(
        self,
        instance_type: str | None = None,
        market: SpotMarket | None = None,
        limit: int = 50,
    ) -> list[SpotUsageRecord]:
        results = list(self._records)
        if instance_type is not None:
            results = [r for r in results if r.instance_type == instance_type]
        if market is not None:
            results = [r for r in results if r.market == market]
        return results[-limit:]

    def add_recommendation(
        self,
        instance_type: str,
        recommended_market: SpotMarket = SpotMarket.AWS_SPOT,
        savings_grade: SavingsGrade | None = None,
        estimated_savings_pct: float = 0.0,
        reason: str = "",
    ) -> SpotRecommendation:
        if savings_grade is None:
            savings_grade = self._savings_to_grade(estimated_savings_pct)
        rec = SpotRecommendation(
            instance_type=instance_type,
            recommended_market=recommended_market,
            savings_grade=savings_grade,
            estimated_savings_pct=estimated_savings_pct,
            reason=reason,
        )
        self._recommendations.append(rec)
        if len(self._recommendations) > self._max_records:
            self._recommendations = self._recommendations[-self._max_records :]
        logger.info(
            "spot_advisor.recommendation_added",
            instance_type=instance_type,
            savings_grade=savings_grade.value,
        )
        return rec

    # -- domain operations -----------------------------------------------

    def analyze_spot_suitability(self, instance_type: str) -> dict[str, Any]:
        """Analyze spot suitability for a specific instance type."""
        records = [r for r in self._records if r.instance_type == instance_type]
        if not records:
            return {
                "instance_type": instance_type,
                "status": "no_data",
            }
        latest = records[-1]
        return {
            "instance_type": instance_type,
            "market": latest.market.value,
            "interruption_risk": latest.interruption_risk.value,
            "savings_pct": latest.savings_pct,
            "monthly_cost": latest.monthly_cost,
        }

    def identify_high_savings_opportunities(
        self,
    ) -> list[dict[str, Any]]:
        """Find instances with savings above threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.savings_pct >= self._min_savings_pct:
                results.append(
                    {
                        "instance_type": r.instance_type,
                        "market": r.market.value,
                        "savings_pct": r.savings_pct,
                        "interruption_risk": r.interruption_risk.value,
                    }
                )
        results.sort(key=lambda x: x["savings_pct"], reverse=True)
        return results

    def rank_by_interruption_risk(self) -> list[dict[str, Any]]:
        """Rank instances by interruption risk."""
        risk_order = {
            InterruptionRisk.VERY_HIGH: 5,
            InterruptionRisk.HIGH: 4,
            InterruptionRisk.MODERATE: 3,
            InterruptionRisk.LOW: 2,
            InterruptionRisk.MINIMAL: 1,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "instance_type": r.instance_type,
                    "interruption_risk": r.interruption_risk.value,
                    "risk_score": risk_order.get(r.interruption_risk, 0),
                    "savings_pct": r.savings_pct,
                }
            )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def estimate_total_savings(self) -> dict[str, Any]:
        """Estimate total savings from spot adoption."""
        total_on_demand = sum(r.on_demand_cost for r in self._records)
        total_actual = sum(r.monthly_cost for r in self._records)
        savings = total_on_demand - total_actual
        pct = round(savings / total_on_demand * 100, 2) if total_on_demand > 0 else 0.0
        return {
            "total_on_demand_cost": round(total_on_demand, 2),
            "total_actual_cost": round(total_actual, 2),
            "total_savings": round(savings, 2),
            "savings_pct": pct,
            "record_count": len(self._records),
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> SpotAdvisorReport:
        by_market: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_market[r.market.value] = by_market.get(r.market.value, 0) + 1
            by_risk[r.interruption_risk.value] = by_risk.get(r.interruption_risk.value, 0) + 1
        avg_savings = (
            round(
                sum(r.savings_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_savings = sum(1 for r in self._records if r.savings_pct >= self._min_savings_pct)
        recs: list[str] = []
        if high_savings > 0:
            recs.append(f"{high_savings} instance(s) with savings >= {self._min_savings_pct}%")
        high_risk = sum(
            1
            for r in self._records
            if r.interruption_risk in (InterruptionRisk.VERY_HIGH, InterruptionRisk.HIGH)
        )
        if high_risk > 0:
            recs.append(f"{high_risk} instance(s) with high interruption risk")
        if not recs:
            recs.append("Spot usage optimization meets targets")
        return SpotAdvisorReport(
            total_records=len(self._records),
            total_recommendations=len(self._recommendations),
            avg_savings_pct=avg_savings,
            by_market=by_market,
            by_risk=by_risk,
            high_savings_count=high_savings,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._recommendations.clear()
        logger.info("spot_advisor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        market_dist: dict[str, int] = {}
        for r in self._records:
            key = r.market.value
            market_dist[key] = market_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_recommendations": len(self._recommendations),
            "min_savings_pct": self._min_savings_pct,
            "market_distribution": market_dist,
            "unique_instance_types": len({r.instance_type for r in self._records}),
        }
