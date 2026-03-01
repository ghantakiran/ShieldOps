"""SLA Breach Impact Analyzer — track breaches, assessments, and trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BreachCategory(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    RESPONSE_TIME = "response_time"


class ImpactLevel(StrEnum):
    CATASTROPHIC = "catastrophic"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    NEGLIGIBLE = "negligible"


class BreachConsequence(StrEnum):
    FINANCIAL_PENALTY = "financial_penalty"
    CUSTOMER_CHURN = "customer_churn"
    REPUTATION_DAMAGE = "reputation_damage"
    CONTRACT_RISK = "contract_risk"
    ESCALATION = "escalation"


# --- Models ---


class BreachImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sla_id: str = ""
    breach_category: BreachCategory = BreachCategory.AVAILABILITY
    impact_level: ImpactLevel = ImpactLevel.NEGLIGIBLE
    breach_consequence: BreachConsequence = BreachConsequence.ESCALATION
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sla_id: str = ""
    breach_category: BreachCategory = BreachCategory.AVAILABILITY
    financial_impact: float = 0.0
    affected_customers: int = 0
    mitigation_plan: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SLABreachImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    high_impact_breaches: int = 0
    avg_impact_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_impact_level: dict[str, int] = Field(default_factory=dict)
    by_consequence: dict[str, int] = Field(default_factory=dict)
    top_breaches: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLABreachImpactAnalyzer:
    """Track SLA breaches, assess impact, and detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        max_breach_impact_score: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._max_breach_impact_score = max_breach_impact_score
        self._records: list[BreachImpactRecord] = []
        self._assessments: list[ImpactAssessment] = []
        logger.info(
            "breach_impact.initialized",
            max_records=max_records,
            max_breach_impact_score=max_breach_impact_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_breach(
        self,
        sla_id: str,
        breach_category: BreachCategory = BreachCategory.AVAILABILITY,
        impact_level: ImpactLevel = ImpactLevel.NEGLIGIBLE,
        breach_consequence: BreachConsequence = BreachConsequence.ESCALATION,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BreachImpactRecord:
        record = BreachImpactRecord(
            sla_id=sla_id,
            breach_category=breach_category,
            impact_level=impact_level,
            breach_consequence=breach_consequence,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "breach_impact.breach_recorded",
            record_id=record.id,
            sla_id=sla_id,
            breach_category=breach_category.value,
            impact_level=impact_level.value,
        )
        return record

    def get_breach(self, record_id: str) -> BreachImpactRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_breaches(
        self,
        category: BreachCategory | None = None,
        impact_level: ImpactLevel | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BreachImpactRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.breach_category == category]
        if impact_level is not None:
            results = [r for r in results if r.impact_level == impact_level]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        sla_id: str,
        breach_category: BreachCategory = BreachCategory.AVAILABILITY,
        financial_impact: float = 0.0,
        affected_customers: int = 0,
        mitigation_plan: str = "",
        description: str = "",
    ) -> ImpactAssessment:
        assessment = ImpactAssessment(
            sla_id=sla_id,
            breach_category=breach_category,
            financial_impact=financial_impact,
            affected_customers=affected_customers,
            mitigation_plan=mitigation_plan,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "breach_impact.assessment_added",
            sla_id=sla_id,
            breach_category=breach_category.value,
            financial_impact=financial_impact,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_breach_patterns(self) -> dict[str, Any]:
        """Group by category; return count and avg impact score per category."""
        category_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.breach_category.value
            category_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for category, scores in category_data.items():
            result[category] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_impact_breaches(self) -> list[dict[str, Any]]:
        """Return records where impact_level is CATASTROPHIC or MAJOR."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact_level in (ImpactLevel.CATASTROPHIC, ImpactLevel.MAJOR):
                results.append(
                    {
                        "record_id": r.id,
                        "sla_id": r.sla_id,
                        "breach_category": r.breach_category.value,
                        "impact_level": r.impact_level.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_impact_score(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg impact score."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_data.items():
            results.append(
                {
                    "service": service,
                    "breach_count": len(scores),
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_breach_trends(self) -> dict[str, Any]:
        """Split-half on financial_impact; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [a.financial_impact for a in self._assessments]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> SLABreachImpactReport:
        by_category: dict[str, int] = {}
        by_impact_level: dict[str, int] = {}
        by_consequence: dict[str, int] = {}
        for r in self._records:
            by_category[r.breach_category.value] = by_category.get(r.breach_category.value, 0) + 1
            by_impact_level[r.impact_level.value] = by_impact_level.get(r.impact_level.value, 0) + 1
            by_consequence[r.breach_consequence.value] = (
                by_consequence.get(r.breach_consequence.value, 0) + 1
            )
        high_impact_count = sum(
            1
            for r in self._records
            if r.impact_level in (ImpactLevel.CATASTROPHIC, ImpactLevel.MAJOR)
        )
        scores = [r.impact_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        rankings = self.rank_by_impact_score()
        top_breaches = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        above_threshold = sum(
            1 for r in self._records if r.impact_score > self._max_breach_impact_score
        )
        above_rate = round(above_threshold / len(self._records) * 100, 2) if self._records else 0.0
        if above_rate > 20.0:
            recs.append(
                f"High impact breach rate {above_rate}% exceeds "
                f"threshold ({self._max_breach_impact_score})"
            )
        if high_impact_count > 0:
            recs.append(
                f"{high_impact_count} high-impact breach(es) detected — review SLA compliance"
            )
        if not recs:
            recs.append("SLA breach impact levels are acceptable")
        return SLABreachImpactReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            high_impact_breaches=high_impact_count,
            avg_impact_score=avg_score,
            by_category=by_category,
            by_impact_level=by_impact_level,
            by_consequence=by_consequence,
            top_breaches=top_breaches,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("breach_impact.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.breach_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "max_breach_impact_score": self._max_breach_impact_score,
            "category_distribution": category_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_slas": len({r.sla_id for r in self._records}),
        }
