"""Third Party Security Scorer — assess and score third-party vendor security."""

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
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class AssessmentType(StrEnum):
    QUESTIONNAIRE = "questionnaire"
    AUDIT = "audit"
    CONTINUOUS_MONITORING = "continuous_monitoring"
    PENETRATION_TEST = "penetration_test"
    CERTIFICATION = "certification"


class SecurityRating(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    CRITICAL = "critical"


# --- Models ---


class VendorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_name: str = ""
    vendor_tier: VendorTier = VendorTier.CRITICAL
    assessment_type: AssessmentType = AssessmentType.QUESTIONNAIRE
    security_rating: SecurityRating = SecurityRating.EXCELLENT
    vendor_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class VendorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_name: str = ""
    vendor_tier: VendorTier = VendorTier.CRITICAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class VendorSecurityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_vendor_score: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_assessment: dict[str, int] = Field(default_factory=dict)
    by_rating: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThirdPartySecurityScorer:
    """Assess third-party vendor security posture, track ratings, identify vendor gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[VendorRecord] = []
        self._analyses: list[VendorAnalysis] = []
        logger.info(
            "third_party_security_scorer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_vendor(
        self,
        vendor_name: str,
        vendor_tier: VendorTier = VendorTier.CRITICAL,
        assessment_type: AssessmentType = AssessmentType.QUESTIONNAIRE,
        security_rating: SecurityRating = SecurityRating.EXCELLENT,
        vendor_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> VendorRecord:
        record = VendorRecord(
            vendor_name=vendor_name,
            vendor_tier=vendor_tier,
            assessment_type=assessment_type,
            security_rating=security_rating,
            vendor_score=vendor_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "third_party_security_scorer.vendor_recorded",
            record_id=record.id,
            vendor_name=vendor_name,
            vendor_tier=vendor_tier.value,
            assessment_type=assessment_type.value,
        )
        return record

    def get_record(self, record_id: str) -> VendorRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        vendor_tier: VendorTier | None = None,
        security_rating: SecurityRating | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[VendorRecord]:
        results = list(self._records)
        if vendor_tier is not None:
            results = [r for r in results if r.vendor_tier == vendor_tier]
        if security_rating is not None:
            results = [r for r in results if r.security_rating == security_rating]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        vendor_name: str,
        vendor_tier: VendorTier = VendorTier.CRITICAL,
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
            "third_party_security_scorer.analysis_added",
            vendor_name=vendor_name,
            vendor_tier=vendor_tier.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by vendor_tier; return count and avg vendor_score."""
        tier_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.vendor_tier.value
            tier_data.setdefault(key, []).append(r.vendor_score)
        result: dict[str, Any] = {}
        for tier, scores in tier_data.items():
            result[tier] = {
                "count": len(scores),
                "avg_vendor_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where vendor_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.vendor_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "vendor_name": r.vendor_name,
                        "vendor_tier": r.vendor_tier.value,
                        "vendor_score": r.vendor_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["vendor_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg vendor_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.vendor_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_vendor_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_vendor_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
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

    def generate_report(self) -> VendorSecurityReport:
        by_tier: dict[str, int] = {}
        by_assessment: dict[str, int] = {}
        by_rating: dict[str, int] = {}
        for r in self._records:
            by_tier[r.vendor_tier.value] = by_tier.get(r.vendor_tier.value, 0) + 1
            by_assessment[r.assessment_type.value] = (
                by_assessment.get(r.assessment_type.value, 0) + 1
            )
            by_rating[r.security_rating.value] = by_rating.get(r.security_rating.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.vendor_score < self._threshold)
        scores = [r.vendor_score for r in self._records]
        avg_vendor_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["vendor_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} vendor(s) below security threshold ({self._threshold})")
        if self._records and avg_vendor_score < self._threshold:
            recs.append(f"Avg vendor score {avg_vendor_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Third-party security posture is healthy")
        return VendorSecurityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_vendor_score=avg_vendor_score,
            by_tier=by_tier,
            by_assessment=by_assessment,
            by_rating=by_rating,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("third_party_security_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.vendor_tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "tier_distribution": tier_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
