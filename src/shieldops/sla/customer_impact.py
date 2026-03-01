"""Customer Impact Scorer — track customer impacts, details, and patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactCategory(StrEnum):
    AVAILABILITY = "availability"
    PERFORMANCE = "performance"
    FUNCTIONALITY = "functionality"
    DATA_ACCESS = "data_access"
    BILLING = "billing"


class CustomerTier(StrEnum):
    ENTERPRISE = "enterprise"
    BUSINESS = "business"
    PROFESSIONAL = "professional"
    STARTER = "starter"
    FREE = "free"


class ImpactSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    COSMETIC = "cosmetic"


# --- Models ---


class CustomerImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    impact_category: ImpactCategory = ImpactCategory.AVAILABILITY
    customer_tier: CustomerTier = CustomerTier.FREE
    impact_severity: ImpactSeverity = ImpactSeverity.MINOR
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    impact_category: ImpactCategory = ImpactCategory.AVAILABILITY
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CustomerImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_details: int = 0
    high_impact_incidents: int = 0
    avg_impact_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_impacted: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CustomerImpactScorer:
    """Track customer impacts, identify high-impact incidents, and detect patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        max_impact_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._max_impact_score = max_impact_score
        self._records: list[CustomerImpactRecord] = []
        self._details: list[ImpactDetail] = []
        logger.info(
            "customer_impact.initialized",
            max_records=max_records,
            max_impact_score=max_impact_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_impact(
        self,
        incident_id: str,
        impact_category: ImpactCategory = ImpactCategory.AVAILABILITY,
        customer_tier: CustomerTier = CustomerTier.FREE,
        impact_severity: ImpactSeverity = ImpactSeverity.MINOR,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CustomerImpactRecord:
        record = CustomerImpactRecord(
            incident_id=incident_id,
            impact_category=impact_category,
            customer_tier=customer_tier,
            impact_severity=impact_severity,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "customer_impact.impact_recorded",
            record_id=record.id,
            incident_id=incident_id,
            impact_category=impact_category.value,
            customer_tier=customer_tier.value,
        )
        return record

    def get_impact(self, record_id: str) -> CustomerImpactRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_impacts(
        self,
        category: ImpactCategory | None = None,
        tier: CustomerTier | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CustomerImpactRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.impact_category == category]
        if tier is not None:
            results = [r for r in results if r.customer_tier == tier]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_detail(
        self,
        incident_id: str,
        impact_category: ImpactCategory = ImpactCategory.AVAILABILITY,
        value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ImpactDetail:
        detail = ImpactDetail(
            incident_id=incident_id,
            impact_category=impact_category,
            value=value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._details.append(detail)
        if len(self._details) > self._max_records:
            self._details = self._details[-self._max_records :]
        logger.info(
            "customer_impact.detail_added",
            incident_id=incident_id,
            impact_category=impact_category.value,
            value=value,
        )
        return detail

    # -- domain operations --------------------------------------------------

    def analyze_customer_impact(self) -> dict[str, Any]:
        """Group by category; return count and avg impact score per category."""
        category_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.impact_category.value
            category_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for category, scores in category_data.items():
            result[category] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_impact_incidents(self) -> list[dict[str, Any]]:
        """Return records where severity == CRITICAL or MAJOR."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact_severity in (
                ImpactSeverity.CRITICAL,
                ImpactSeverity.MAJOR,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "impact_category": r.impact_category.value,
                        "impact_severity": r.impact_severity.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_impact_score(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg score."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(scores),
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_impact_patterns(self) -> dict[str, Any]:
        """Split-half on value; delta threshold 5.0."""
        if len(self._details) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [d.value for d in self._details]
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

    def generate_report(self) -> CustomerImpactReport:
        by_category: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_category[r.impact_category.value] = by_category.get(r.impact_category.value, 0) + 1
            by_tier[r.customer_tier.value] = by_tier.get(r.customer_tier.value, 0) + 1
            by_severity[r.impact_severity.value] = by_severity.get(r.impact_severity.value, 0) + 1
        high_impact_count = sum(
            1
            for r in self._records
            if r.impact_severity in (ImpactSeverity.CRITICAL, ImpactSeverity.MAJOR)
        )
        scores = [r.impact_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        rankings = self.rank_by_impact_score()
        top_impacted = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        above_threshold = sum(1 for r in self._records if r.impact_score > self._max_impact_score)
        above_rate = round(above_threshold / len(self._records) * 100, 2) if self._records else 0.0
        if above_rate > 20.0:
            recs.append(
                f"High impact rate {above_rate}% exceeds threshold ({self._max_impact_score})"
            )
        if high_impact_count > 0:
            recs.append(f"{high_impact_count} high-impact incident(s) detected — review impact")
        if not recs:
            recs.append("Customer impact is acceptable")
        return CustomerImpactReport(
            total_records=len(self._records),
            total_details=len(self._details),
            high_impact_incidents=high_impact_count,
            avg_impact_score=avg_score,
            by_category=by_category,
            by_tier=by_tier,
            by_severity=by_severity,
            top_impacted=top_impacted,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._details.clear()
        logger.info("customer_impact.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.impact_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_details": len(self._details),
            "max_impact_score": self._max_impact_score,
            "category_distribution": category_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
