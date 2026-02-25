"""Incident Impact Quantifier.

Quantify business impact in monetary terms, customer count, SLA credits.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactDimension(StrEnum):
    REVENUE_LOSS = "revenue_loss"
    CUSTOMER_IMPACT = "customer_impact"
    SLA_CREDIT = "sla_credit"
    ENGINEERING_COST = "engineering_cost"
    REPUTATION_DAMAGE = "reputation_damage"


class QuantificationMethod(StrEnum):
    DIRECT_MEASUREMENT = "direct_measurement"
    ESTIMATION = "estimation"
    EXTRAPOLATION = "extrapolation"
    BENCHMARK_BASED = "benchmark_based"
    MANUAL_INPUT = "manual_input"


class CostCategory(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    PERSONNEL = "personnel"
    OPPORTUNITY = "opportunity"
    CONTRACTUAL_PENALTY = "contractual_penalty"
    CUSTOMER_CHURN = "customer_churn"


# --- Models ---


class CostBreakdown(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_id: str = ""
    category: CostCategory = CostCategory.INFRASTRUCTURE
    amount_usd: float = 0.0
    description: str = ""
    method: QuantificationMethod = QuantificationMethod.ESTIMATION
    created_at: float = Field(default_factory=time.time)


class ImpactAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    service_name: str = ""
    duration_minutes: float = 0.0
    affected_customers: int = 0
    total_cost_usd: float = 0.0
    sla_credit_usd: float = 0.0
    primary_dimension: ImpactDimension = ImpactDimension.REVENUE_LOSS
    method: QuantificationMethod = QuantificationMethod.ESTIMATION
    severity: str = "medium"
    created_at: float = Field(default_factory=time.time)


class ImpactReport(BaseModel):
    total_assessments: int = 0
    total_cost_usd: float = 0.0
    total_sla_credits_usd: float = 0.0
    total_affected_customers: int = 0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, float] = Field(default_factory=dict)
    avg_duration_minutes: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentImpactQuantifier:
    """Quantify business impact in monetary terms, customer count, SLA credits."""

    def __init__(
        self,
        max_assessments: int = 100000,
        default_hourly_rate_usd: float = 150.0,
    ) -> None:
        self._max_assessments = max_assessments
        self._default_hourly_rate = default_hourly_rate_usd
        self._items: list[ImpactAssessment] = []
        self._breakdowns: list[CostBreakdown] = []
        logger.info(
            "impact_quantifier.initialized",
            max_assessments=max_assessments,
            default_hourly_rate_usd=default_hourly_rate_usd,
        )

    # -- create / get / list -----------------------------------------

    def create_assessment(
        self,
        incident_id: str,
        service_name: str = "",
        duration_minutes: float = 0.0,
        affected_customers: int = 0,
        total_cost_usd: float = 0.0,
        sla_credit_usd: float = 0.0,
        primary_dimension: ImpactDimension = ImpactDimension.REVENUE_LOSS,
        method: QuantificationMethod = QuantificationMethod.ESTIMATION,
        severity: str = "medium",
        **kw: Any,
    ) -> ImpactAssessment:
        assessment = ImpactAssessment(
            incident_id=incident_id,
            service_name=service_name,
            duration_minutes=duration_minutes,
            affected_customers=affected_customers,
            total_cost_usd=total_cost_usd,
            sla_credit_usd=sla_credit_usd,
            primary_dimension=primary_dimension,
            method=method,
            severity=severity,
            **kw,
        )
        self._items.append(assessment)
        if len(self._items) > self._max_assessments:
            self._items = self._items[-self._max_assessments :]
        logger.info(
            "impact_quantifier.assessment_created",
            assessment_id=assessment.id,
            incident_id=incident_id,
        )
        return assessment

    def get_assessment(self, assessment_id: str) -> ImpactAssessment | None:
        for item in self._items:
            if item.id == assessment_id:
                return item
        return None

    def list_assessments(
        self,
        service_name: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[ImpactAssessment]:
        results = list(self._items)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        return results[-limit:]

    # -- cost breakdowns ---------------------------------------------

    def add_cost_breakdown(
        self,
        assessment_id: str,
        category: CostCategory = CostCategory.INFRASTRUCTURE,
        amount_usd: float = 0.0,
        description: str = "",
        method: QuantificationMethod = QuantificationMethod.ESTIMATION,
        **kw: Any,
    ) -> CostBreakdown | None:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return None
        breakdown = CostBreakdown(
            assessment_id=assessment_id,
            category=category,
            amount_usd=amount_usd,
            description=description,
            method=method,
            **kw,
        )
        self._breakdowns.append(breakdown)
        logger.info(
            "impact_quantifier.breakdown_added",
            breakdown_id=breakdown.id,
            assessment_id=assessment_id,
        )
        return breakdown

    # -- domain operations -------------------------------------------

    def calculate_total_impact(
        self,
        assessment_id: str,
    ) -> dict[str, Any]:
        """Calculate total impact for an assessment including breakdowns."""
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return {"found": False, "total_usd": 0.0}
        breakdowns = [b for b in self._breakdowns if b.assessment_id == assessment_id]
        breakdown_total = sum(b.amount_usd for b in breakdowns)
        engineering_cost = round(
            (assessment.duration_minutes / 60.0) * self._default_hourly_rate, 2
        )
        total = round(assessment.total_cost_usd + breakdown_total + engineering_cost, 2)
        return {
            "found": True,
            "assessment_id": assessment_id,
            "base_cost_usd": assessment.total_cost_usd,
            "breakdown_cost_usd": breakdown_total,
            "engineering_cost_usd": engineering_cost,
            "total_usd": total,
            "breakdown_count": len(breakdowns),
        }

    def estimate_sla_credit(
        self,
        assessment_id: str,
        sla_target_pct: float = 99.9,
        monthly_contract_usd: float = 10000.0,
    ) -> dict[str, Any]:
        """Estimate SLA credit based on downtime and contract value."""
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return {"found": False, "credit_usd": 0.0}
        downtime_pct = round((assessment.duration_minutes / (30 * 24 * 60)) * 100, 4)
        achieved_pct = round(100.0 - downtime_pct, 4)
        if achieved_pct >= sla_target_pct:
            credit = 0.0
        else:
            gap = round(sla_target_pct - achieved_pct, 4)
            credit_pct = min(gap * 10, 30.0)
            credit = round(monthly_contract_usd * credit_pct / 100.0, 2)
        return {
            "found": True,
            "assessment_id": assessment_id,
            "downtime_pct": downtime_pct,
            "achieved_pct": achieved_pct,
            "sla_target_pct": sla_target_pct,
            "credit_usd": credit,
        }

    def estimate_customer_impact(
        self,
        assessment_id: str,
        total_customers: int = 10000,
    ) -> dict[str, Any]:
        """Estimate customer impact for an assessment."""
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return {"found": False, "affected_pct": 0.0}
        affected_pct = round((assessment.affected_customers / max(total_customers, 1)) * 100, 2)
        return {
            "found": True,
            "assessment_id": assessment_id,
            "affected_customers": assessment.affected_customers,
            "total_customers": total_customers,
            "affected_pct": affected_pct,
            "severity": assessment.severity,
        }

    def compare_incidents(
        self,
        assessment_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Compare impact across multiple incidents."""
        results: list[dict[str, Any]] = []
        for aid in assessment_ids:
            a = self.get_assessment(aid)
            if a is not None:
                results.append(
                    {
                        "assessment_id": a.id,
                        "incident_id": a.incident_id,
                        "total_cost_usd": a.total_cost_usd,
                        "affected_customers": a.affected_customers,
                        "duration_minutes": a.duration_minutes,
                        "severity": a.severity,
                    }
                )
        results.sort(key=lambda x: x["total_cost_usd"], reverse=True)
        return results

    # -- report / stats ----------------------------------------------

    def generate_impact_report(self) -> ImpactReport:
        by_dimension: dict[str, int] = {}
        for a in self._items:
            key = a.primary_dimension.value
            by_dimension[key] = by_dimension.get(key, 0) + 1
        by_category: dict[str, float] = {}
        for b in self._breakdowns:
            key = b.category.value
            by_category[key] = round(by_category.get(key, 0.0) + b.amount_usd, 2)
        total_cost = round(sum(a.total_cost_usd for a in self._items), 2)
        total_sla = round(sum(a.sla_credit_usd for a in self._items), 2)
        total_customers = sum(a.affected_customers for a in self._items)
        durations = [a.duration_minutes for a in self._items if a.duration_minutes > 0]
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
        recs: list[str] = []
        if total_cost > 100000:
            recs.append("High cumulative incident cost — review prevention strategies")
        if not recs:
            recs.append("Incident impact within acceptable range")
        return ImpactReport(
            total_assessments=len(self._items),
            total_cost_usd=total_cost,
            total_sla_credits_usd=total_sla,
            total_affected_customers=total_customers,
            by_dimension=by_dimension,
            by_category=by_category,
            avg_duration_minutes=avg_duration,
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._items)
        self._items.clear()
        self._breakdowns.clear()
        logger.info("impact_quantifier.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        dim_dist: dict[str, int] = {}
        for a in self._items:
            key = a.primary_dimension.value
            dim_dist[key] = dim_dist.get(key, 0) + 1
        return {
            "total_assessments": len(self._items),
            "total_breakdowns": len(self._breakdowns),
            "default_hourly_rate": self._default_hourly_rate,
            "dimension_distribution": dim_dist,
        }
