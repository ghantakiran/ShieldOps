"""Access Review Tracker — track periodic access reviews and detect stale permissions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReviewType(StrEnum):
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    AD_HOC = "ad_hoc"
    CONTINUOUS = "continuous"


class ReviewStatus(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    OVERDUE = "overdue"
    NOT_STARTED = "not_started"
    CANCELLED = "cancelled"


class AccessRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


# --- Models ---


class AccessReviewRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    review_id: str = ""
    review_type: ReviewType = ReviewType.QUARTERLY
    review_status: ReviewStatus = ReviewStatus.NOT_STARTED
    access_risk: AccessRisk = AccessRisk.MINIMAL
    completion_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ReviewFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    review_id: str = ""
    review_type: ReviewType = ReviewType.QUARTERLY
    finding_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AccessReviewReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_findings: int = 0
    overdue_reviews: int = 0
    avg_completion_pct: float = 0.0
    by_review_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_overdue: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AccessReviewTracker:
    """Track periodic access reviews, detect stale permissions, review completion tracking."""

    def __init__(
        self,
        max_records: int = 200000,
        min_review_completion_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_review_completion_pct = min_review_completion_pct
        self._records: list[AccessReviewRecord] = []
        self._findings: list[ReviewFinding] = []
        logger.info(
            "access_review.initialized",
            max_records=max_records,
            min_review_completion_pct=min_review_completion_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_review(
        self,
        review_id: str,
        review_type: ReviewType = ReviewType.QUARTERLY,
        review_status: ReviewStatus = ReviewStatus.NOT_STARTED,
        access_risk: AccessRisk = AccessRisk.MINIMAL,
        completion_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AccessReviewRecord:
        record = AccessReviewRecord(
            review_id=review_id,
            review_type=review_type,
            review_status=review_status,
            access_risk=access_risk,
            completion_pct=completion_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "access_review.review_recorded",
            record_id=record.id,
            review_id=review_id,
            review_type=review_type.value,
            review_status=review_status.value,
        )
        return record

    def get_review(self, record_id: str) -> AccessReviewRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_reviews(
        self,
        review_type: ReviewType | None = None,
        status: ReviewStatus | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AccessReviewRecord]:
        results = list(self._records)
        if review_type is not None:
            results = [r for r in results if r.review_type == review_type]
        if status is not None:
            results = [r for r in results if r.review_status == status]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_finding(
        self,
        review_id: str,
        review_type: ReviewType = ReviewType.QUARTERLY,
        finding_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ReviewFinding:
        finding = ReviewFinding(
            review_id=review_id,
            review_type=review_type,
            finding_score=finding_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._findings.append(finding)
        if len(self._findings) > self._max_records:
            self._findings = self._findings[-self._max_records :]
        logger.info(
            "access_review.finding_added",
            review_id=review_id,
            review_type=review_type.value,
            finding_score=finding_score,
        )
        return finding

    # -- domain operations --------------------------------------------------

    def analyze_review_compliance(self) -> dict[str, Any]:
        """Group by review type; return count and avg completion."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.review_type.value
            type_data.setdefault(key, []).append(r.completion_pct)
        result: dict[str, Any] = {}
        for rtype, pcts in type_data.items():
            result[rtype] = {
                "count": len(pcts),
                "avg_completion": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_overdue_reviews(self) -> list[dict[str, Any]]:
        """Return records where status is OVERDUE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.review_status == ReviewStatus.OVERDUE:
                results.append(
                    {
                        "record_id": r.id,
                        "review_id": r.review_id,
                        "review_type": r.review_type.value,
                        "access_risk": r.access_risk.value,
                        "completion_pct": r.completion_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_completion(self) -> list[dict[str, Any]]:
        """Group by service, avg completion, sort ascending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.completion_pct)
        results: list[dict[str, Any]] = []
        for svc, pcts in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_completion": round(sum(pcts) / len(pcts), 2),
                    "record_count": len(pcts),
                }
            )
        results.sort(key=lambda x: x["avg_completion"])
        return results

    def detect_review_trends(self) -> dict[str, Any]:
        """Split-half comparison on finding_score; delta threshold 5.0."""
        if len(self._findings) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [f.finding_score for f in self._findings]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> AccessReviewReport:
        by_review_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_review_type[r.review_type.value] = by_review_type.get(r.review_type.value, 0) + 1
            by_status[r.review_status.value] = by_status.get(r.review_status.value, 0) + 1
            by_risk[r.access_risk.value] = by_risk.get(r.access_risk.value, 0) + 1
        overdue_reviews = sum(1 for r in self._records if r.review_status == ReviewStatus.OVERDUE)
        avg_completion_pct = (
            round(
                sum(r.completion_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        overdue = self.identify_overdue_reviews()
        top_overdue = [o["review_id"] for o in overdue[:5]]
        recs: list[str] = []
        if overdue_reviews > 0:
            recs.append(
                f"{overdue_reviews} overdue review(s) — complete access reviews immediately"
            )
        low_comp = sum(
            1 for r in self._records if r.completion_pct < self._min_review_completion_pct
        )
        if low_comp > 0:
            recs.append(
                f"{low_comp} review(s) below completion threshold"
                f" ({self._min_review_completion_pct}%)"
            )
        if not recs:
            recs.append("Access review completion levels are healthy")
        return AccessReviewReport(
            total_records=len(self._records),
            total_findings=len(self._findings),
            overdue_reviews=overdue_reviews,
            avg_completion_pct=avg_completion_pct,
            by_review_type=by_review_type,
            by_status=by_status,
            by_risk=by_risk,
            top_overdue=top_overdue,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._findings.clear()
        logger.info("access_review.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.review_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_findings": len(self._findings),
            "min_review_completion_pct": self._min_review_completion_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
