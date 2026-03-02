"""Vendor Risk Intelligence — third-party vendor risk scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VendorTier(StrEnum):
    TIER_1_CRITICAL = "tier_1_critical"
    TIER_2_IMPORTANT = "tier_2_important"
    TIER_3_STANDARD = "tier_3_standard"
    TIER_4_LOW_RISK = "tier_4_low_risk"
    TIER_5_MINIMAL = "tier_5_minimal"


class RiskDomain(StrEnum):
    SECURITY = "security"
    COMPLIANCE = "compliance"
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    REPUTATIONAL = "reputational"


class AssessmentStatus(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    OVERDUE = "overdue"
    SCHEDULED = "scheduled"
    NOT_STARTED = "not_started"


# --- Models ---


class VendorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_name: str = ""
    vendor_tier: VendorTier = VendorTier.TIER_1_CRITICAL
    risk_domain: RiskDomain = RiskDomain.SECURITY
    assessment_status: AssessmentStatus = AssessmentStatus.COMPLETED
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class VendorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_name: str = ""
    vendor_tier: VendorTier = VendorTier.TIER_1_CRITICAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class VendorRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_risk_count: int = 0
    avg_risk_score: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_high_risk: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class VendorRiskIntelligence:
    """Third-party vendor risk scoring and assessment tracking."""

    def __init__(
        self,
        max_records: int = 200000,
        vendor_risk_threshold: float = 65.0,
    ) -> None:
        self._max_records = max_records
        self._vendor_risk_threshold = vendor_risk_threshold
        self._records: list[VendorRecord] = []
        self._analyses: list[VendorAnalysis] = []
        logger.info(
            "vendor_risk_intelligence.initialized",
            max_records=max_records,
            vendor_risk_threshold=vendor_risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_vendor(
        self,
        vendor_name: str,
        vendor_tier: VendorTier = VendorTier.TIER_1_CRITICAL,
        risk_domain: RiskDomain = RiskDomain.SECURITY,
        assessment_status: AssessmentStatus = AssessmentStatus.COMPLETED,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> VendorRecord:
        record = VendorRecord(
            vendor_name=vendor_name,
            vendor_tier=vendor_tier,
            risk_domain=risk_domain,
            assessment_status=assessment_status,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "vendor_risk_intelligence.vendor_recorded",
            record_id=record.id,
            vendor_name=vendor_name,
            vendor_tier=vendor_tier.value,
            risk_domain=risk_domain.value,
        )
        return record

    def get_vendor(self, record_id: str) -> VendorRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_vendors(
        self,
        vendor_tier: VendorTier | None = None,
        risk_domain: RiskDomain | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[VendorRecord]:
        results = list(self._records)
        if vendor_tier is not None:
            results = [r for r in results if r.vendor_tier == vendor_tier]
        if risk_domain is not None:
            results = [r for r in results if r.risk_domain == risk_domain]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        vendor_name: str,
        vendor_tier: VendorTier = VendorTier.TIER_1_CRITICAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> VendorAnalysis:
        analysis = VendorAnalysis(
            vendor_name=vendor_name,
            vendor_tier=vendor_tier,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "vendor_risk_intelligence.analysis_added",
            vendor_name=vendor_name,
            vendor_tier=vendor_tier.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_tier_distribution(self) -> dict[str, Any]:
        """Group by vendor_tier; return count and avg risk_score."""
        tier_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.vendor_tier.value
            tier_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for tier, scores in tier_data.items():
            result[tier] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_risk_vendors(self) -> list[dict[str, Any]]:
        """Return records where risk_score > vendor_risk_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score > self._vendor_risk_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "vendor_name": r.vendor_name,
                        "vendor_tier": r.vendor_tier.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"], reverse=True)

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_risk_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> VendorRiskReport:
        by_tier: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_tier[r.vendor_tier.value] = by_tier.get(r.vendor_tier.value, 0) + 1
            by_domain[r.risk_domain.value] = by_domain.get(r.risk_domain.value, 0) + 1
            by_status[r.assessment_status.value] = by_status.get(r.assessment_status.value, 0) + 1
        high_risk_count = sum(
            1 for r in self._records if r.risk_score > self._vendor_risk_threshold
        )
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_risk_vendors()
        top_high_risk = [o["vendor_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_risk_count > 0:
            recs.append(
                f"{high_risk_count} vendor(s) above risk threshold ({self._vendor_risk_threshold})"
            )
        if self._records and avg_risk_score > self._vendor_risk_threshold:
            recs.append(
                f"Avg risk score {avg_risk_score} above threshold ({self._vendor_risk_threshold})"
            )
        if not recs:
            recs.append("Vendor risk posture is healthy")
        return VendorRiskReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_risk_count=high_risk_count,
            avg_risk_score=avg_risk_score,
            by_tier=by_tier,
            by_domain=by_domain,
            by_status=by_status,
            top_high_risk=top_high_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("vendor_risk_intelligence.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.vendor_tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "vendor_risk_threshold": self._vendor_risk_threshold,
            "tier_distribution": tier_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
