"""Access Governance Reviewer — review and govern access rights and permissions."""

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
    PERIODIC = "periodic"
    TRIGGERED = "triggered"
    CERTIFICATION = "certification"
    PRIVILEGED_ACCESS = "privileged_access"
    SERVICE_ACCOUNT = "service_account"


class ReviewOutcome(StrEnum):
    APPROVED = "approved"
    REVOKED = "revoked"
    MODIFIED = "modified"
    ESCALATED = "escalated"
    DEFERRED = "deferred"


class AccessRisk(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"
    NONE = "none"


# --- Models ---


class ReviewRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    review_name: str = ""
    review_type: ReviewType = ReviewType.PERIODIC
    review_outcome: ReviewOutcome = ReviewOutcome.APPROVED
    access_risk: AccessRisk = AccessRisk.HIGH
    review_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ReviewAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    review_name: str = ""
    review_type: ReviewType = ReviewType.PERIODIC
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AccessGovernanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_review_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AccessGovernanceReviewer:
    """Review access governance, track outcomes, identify access review gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ReviewRecord] = []
        self._analyses: list[ReviewAnalysis] = []
        logger.info(
            "access_governance_reviewer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_review(
        self,
        review_name: str,
        review_type: ReviewType = ReviewType.PERIODIC,
        review_outcome: ReviewOutcome = ReviewOutcome.APPROVED,
        access_risk: AccessRisk = AccessRisk.HIGH,
        review_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ReviewRecord:
        record = ReviewRecord(
            review_name=review_name,
            review_type=review_type,
            review_outcome=review_outcome,
            access_risk=access_risk,
            review_score=review_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "access_governance_reviewer.review_recorded",
            record_id=record.id,
            review_name=review_name,
            review_type=review_type.value,
            review_outcome=review_outcome.value,
        )
        return record

    def get_record(self, record_id: str) -> ReviewRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        review_type: ReviewType | None = None,
        review_outcome: ReviewOutcome | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ReviewRecord]:
        results = list(self._records)
        if review_type is not None:
            results = [r for r in results if r.review_type == review_type]
        if review_outcome is not None:
            results = [r for r in results if r.review_outcome == review_outcome]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        review_name: str,
        review_type: ReviewType = ReviewType.PERIODIC,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ReviewAnalysis:
        analysis = ReviewAnalysis(
            review_name=review_name,
            review_type=review_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "access_governance_reviewer.analysis_added",
            review_name=review_name,
            review_type=review_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by review_type; return count and avg review_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.review_type.value
            type_data.setdefault(key, []).append(r.review_score)
        result: dict[str, Any] = {}
        for review_type, scores in type_data.items():
            result[review_type] = {
                "count": len(scores),
                "avg_review_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where review_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.review_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "review_name": r.review_name,
                        "review_type": r.review_type.value,
                        "review_score": r.review_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["review_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg review_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.review_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_review_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_review_score"])
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

    def generate_report(self) -> AccessGovernanceReport:
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_type[r.review_type.value] = by_type.get(r.review_type.value, 0) + 1
            by_outcome[r.review_outcome.value] = by_outcome.get(r.review_outcome.value, 0) + 1
            by_risk[r.access_risk.value] = by_risk.get(r.access_risk.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.review_score < self._threshold)
        scores = [r.review_score for r in self._records]
        avg_review_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["review_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} review(s) below score threshold ({self._threshold})")
        if self._records and avg_review_score < self._threshold:
            recs.append(f"Avg review score {avg_review_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Access governance is healthy")
        return AccessGovernanceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_review_score=avg_review_score,
            by_type=by_type,
            by_outcome=by_outcome,
            by_risk=by_risk,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("access_governance_reviewer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.review_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
