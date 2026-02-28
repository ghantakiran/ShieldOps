"""Compliance Posture Scorer — score overall compliance posture."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PostureDomain(StrEnum):
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    NETWORK_SECURITY = "network_security"
    LOGGING = "logging"
    ENCRYPTION = "encryption"


class PostureGrade(StrEnum):
    EXEMPLARY = "exemplary"
    STRONG = "strong"
    ACCEPTABLE = "acceptable"
    WEAK = "weak"
    NON_COMPLIANT = "non_compliant"


class RemediationUrgency(StrEnum):
    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SCHEDULED = "scheduled"


# --- Models ---


class PostureRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str = ""
    domain: PostureDomain = PostureDomain.ACCESS_CONTROL
    grade: PostureGrade = PostureGrade.ACCEPTABLE
    urgency: RemediationUrgency = RemediationUrgency.MEDIUM
    score_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PosturePolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    domain: PostureDomain = PostureDomain.ACCESS_CONTROL
    grade: PostureGrade = PostureGrade.ACCEPTABLE
    min_score_pct: float = 70.0
    review_frequency_days: float = 30.0
    created_at: float = Field(default_factory=time.time)


class PostureScorerReport(BaseModel):
    total_assessments: int = 0
    total_policies: int = 0
    strong_rate_pct: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    non_compliant_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CompliancePostureScorer:
    """Score overall compliance posture."""

    def __init__(
        self,
        max_records: int = 200000,
        min_score_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_score_pct = min_score_pct
        self._records: list[PostureRecord] = []
        self._policies: list[PosturePolicy] = []
        logger.info(
            "posture_scorer.initialized",
            max_records=max_records,
            min_score_pct=min_score_pct,
        )

    # -- record / get / list ----------------------------------------

    def record_assessment(
        self,
        domain_name: str,
        domain: PostureDomain = (PostureDomain.ACCESS_CONTROL),
        grade: PostureGrade = PostureGrade.ACCEPTABLE,
        urgency: RemediationUrgency = (RemediationUrgency.MEDIUM),
        score_pct: float = 0.0,
        details: str = "",
    ) -> PostureRecord:
        record = PostureRecord(
            domain_name=domain_name,
            domain=domain,
            grade=grade,
            urgency=urgency,
            score_pct=score_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "posture_scorer.assessment_recorded",
            record_id=record.id,
            domain_name=domain_name,
            domain=domain.value,
            grade=grade.value,
        )
        return record

    def get_assessment(self, record_id: str) -> PostureRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_assessments(
        self,
        domain_name: str | None = None,
        domain: PostureDomain | None = None,
        limit: int = 50,
    ) -> list[PostureRecord]:
        results = list(self._records)
        if domain_name is not None:
            results = [r for r in results if r.domain_name == domain_name]
        if domain is not None:
            results = [r for r in results if r.domain == domain]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        domain: PostureDomain = (PostureDomain.ACCESS_CONTROL),
        grade: PostureGrade = PostureGrade.ACCEPTABLE,
        min_score_pct: float = 70.0,
        review_frequency_days: float = 30.0,
    ) -> PosturePolicy:
        policy = PosturePolicy(
            policy_name=policy_name,
            domain=domain,
            grade=grade,
            min_score_pct=min_score_pct,
            review_frequency_days=review_frequency_days,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "posture_scorer.policy_added",
            policy_name=policy_name,
            domain=domain.value,
            grade=grade.value,
        )
        return policy

    # -- domain operations ------------------------------------------

    def analyze_posture_health(self, domain_name: str) -> dict[str, Any]:
        """Analyze posture health for a domain."""
        records = [r for r in self._records if r.domain_name == domain_name]
        if not records:
            return {
                "domain_name": domain_name,
                "status": "no_data",
            }
        strong_count = sum(
            1
            for r in records
            if r.grade
            in (
                PostureGrade.EXEMPLARY,
                PostureGrade.STRONG,
            )
        )
        strong_rate = round(strong_count / len(records) * 100, 2)
        avg_score = round(
            sum(r.score_pct for r in records) / len(records),
            2,
        )
        return {
            "domain_name": domain_name,
            "assessment_count": len(records),
            "strong_count": strong_count,
            "strong_rate": strong_rate,
            "avg_score": avg_score,
            "meets_threshold": (avg_score >= self._min_score_pct),
        }

    def identify_non_compliant(
        self,
    ) -> list[dict[str, Any]]:
        """Find domains with repeated non-compliance."""
        nc_counts: dict[str, int] = {}
        for r in self._records:
            if r.grade in (
                PostureGrade.WEAK,
                PostureGrade.NON_COMPLIANT,
            ):
                nc_counts[r.domain_name] = nc_counts.get(r.domain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for domain, count in nc_counts.items():
            if count > 1:
                results.append(
                    {
                        "domain_name": domain,
                        "non_compliant_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["non_compliant_count"],
            reverse=True,
        )
        return results

    def rank_by_score(
        self,
    ) -> list[dict[str, Any]]:
        """Rank domains by avg score descending."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            totals[r.domain_name] = totals.get(r.domain_name, 0.0) + r.score_pct
            counts[r.domain_name] = counts.get(r.domain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for domain in totals:
            avg = round(totals[domain] / counts[domain], 2)
            results.append(
                {
                    "domain_name": domain,
                    "avg_score": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_score"],
            reverse=True,
        )
        return results

    def detect_posture_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Detect domains with >3 non-EXEMPLARY/STRONG."""
        non_strong: dict[str, int] = {}
        for r in self._records:
            if r.grade not in (
                PostureGrade.EXEMPLARY,
                PostureGrade.STRONG,
            ):
                non_strong[r.domain_name] = non_strong.get(r.domain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for domain, count in non_strong.items():
            if count > 3:
                results.append(
                    {
                        "domain_name": domain,
                        "non_strong_count": count,
                        "gap_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_strong_count"],
            reverse=True,
        )
        return results

    # -- report / stats ---------------------------------------------

    def generate_report(self) -> PostureScorerReport:
        by_domain: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_domain[r.domain.value] = by_domain.get(r.domain.value, 0) + 1
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
        strong_count = sum(
            1
            for r in self._records
            if r.grade
            in (
                PostureGrade.EXEMPLARY,
                PostureGrade.STRONG,
            )
        )
        strong_rate = (
            round(
                strong_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        nc = sum(1 for d in self.identify_non_compliant())
        recs: list[str] = []
        if self._records and strong_rate < 80.0:
            recs.append(f"Strong rate {strong_rate}% is below 80.0% threshold")
        if nc > 0:
            recs.append(f"{nc} domain(s) with repeated non-compliance")
        gaps = len(self.detect_posture_gaps())
        if gaps > 0:
            recs.append(f"{gaps} domain(s) detected with posture gaps")
        if not recs:
            recs.append("Compliance posture is healthy and optimal")
        return PostureScorerReport(
            total_assessments=len(self._records),
            total_policies=len(self._policies),
            strong_rate_pct=strong_rate,
            by_domain=by_domain,
            by_grade=by_grade,
            non_compliant_count=nc,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("posture_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_assessments": len(self._records),
            "total_policies": len(self._policies),
            "min_score_pct": self._min_score_pct,
            "domain_distribution": domain_dist,
            "unique_domains": len({r.domain_name for r in self._records}),
        }
