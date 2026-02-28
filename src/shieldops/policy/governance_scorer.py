"""Platform Governance Scorer — score and track platform governance across domains."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GovernanceDomain(StrEnum):
    ACCESS_MANAGEMENT = "access_management"
    CHANGE_CONTROL = "change_control"
    RISK_MANAGEMENT = "risk_management"
    COMPLIANCE_OVERSIGHT = "compliance_oversight"
    INCIDENT_GOVERNANCE = "incident_governance"


class GovernanceGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    FAILING = "failing"


class GovernanceMaturity(StrEnum):
    OPTIMIZED = "optimized"
    MANAGED = "managed"
    DEFINED = "defined"
    DEVELOPING = "developing"
    INITIAL = "initial"


# --- Models ---


class GovernanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str = ""
    domain: GovernanceDomain = GovernanceDomain.ACCESS_MANAGEMENT
    grade: GovernanceGrade = GovernanceGrade.ADEQUATE
    maturity: GovernanceMaturity = GovernanceMaturity.DEFINED
    score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class GovernanceMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str = ""
    domain: GovernanceDomain = GovernanceDomain.ACCESS_MANAGEMENT
    grade: GovernanceGrade = GovernanceGrade.ADEQUATE
    min_score: float = 70.0
    review_frequency_days: float = 30.0
    created_at: float = Field(default_factory=time.time)


class GovernanceScorerReport(BaseModel):
    total_records: int = 0
    total_metrics: int = 0
    passing_rate_pct: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    weak_domain_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PlatformGovernanceScorer:
    """Score and track platform governance across domains."""

    def __init__(
        self,
        max_records: int = 200000,
        min_governance_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_governance_score = min_governance_score
        self._records: list[GovernanceRecord] = []
        self._metrics: list[GovernanceMetric] = []
        logger.info(
            "governance_scorer.initialized",
            max_records=max_records,
            min_governance_score=min_governance_score,
        )

    # -- record / get / list -------------------------------------------

    def record_governance(
        self,
        domain_name: str,
        domain: GovernanceDomain = GovernanceDomain.ACCESS_MANAGEMENT,
        grade: GovernanceGrade = GovernanceGrade.ADEQUATE,
        maturity: GovernanceMaturity = GovernanceMaturity.DEFINED,
        score: float = 0.0,
        details: str = "",
    ) -> GovernanceRecord:
        record = GovernanceRecord(
            domain_name=domain_name,
            domain=domain,
            grade=grade,
            maturity=maturity,
            score=score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "governance_scorer.governance_recorded",
            record_id=record.id,
            domain_name=domain_name,
            domain=domain.value,
            grade=grade.value,
        )
        return record

    def get_governance(self, record_id: str) -> GovernanceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_governance_records(
        self,
        domain_name: str | None = None,
        domain: GovernanceDomain | None = None,
        limit: int = 50,
    ) -> list[GovernanceRecord]:
        results = list(self._records)
        if domain_name is not None:
            results = [r for r in results if r.domain_name == domain_name]
        if domain is not None:
            results = [r for r in results if r.domain == domain]
        return results[-limit:]

    def add_metric(
        self,
        domain_name: str,
        domain: GovernanceDomain = GovernanceDomain.ACCESS_MANAGEMENT,
        grade: GovernanceGrade = GovernanceGrade.ADEQUATE,
        min_score: float = 70.0,
        review_frequency_days: float = 30.0,
    ) -> GovernanceMetric:
        metric = GovernanceMetric(
            domain_name=domain_name,
            domain=domain,
            grade=grade,
            min_score=min_score,
            review_frequency_days=review_frequency_days,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "governance_scorer.metric_added",
            domain_name=domain_name,
            domain=domain.value,
            grade=grade.value,
        )
        return metric

    # -- domain operations --------------------------------------------

    def analyze_governance_by_domain(self, domain_name: str) -> dict[str, Any]:
        """Analyze governance for a specific domain."""
        records = [r for r in self._records if r.domain_name == domain_name]
        if not records:
            return {"domain_name": domain_name, "status": "no_data"}
        passing_count = sum(
            1 for r in records if r.grade in (GovernanceGrade.EXCELLENT, GovernanceGrade.GOOD)
        )
        passing_rate = round(passing_count / len(records) * 100, 2)
        avg_score = round(sum(r.score for r in records) / len(records), 2)
        return {
            "domain_name": domain_name,
            "record_count": len(records),
            "passing_count": passing_count,
            "passing_rate_pct": passing_rate,
            "avg_score": avg_score,
            "meets_threshold": avg_score >= self._min_governance_score,
        }

    def identify_weak_domains(self) -> list[dict[str, Any]]:
        """Find domains with repeated poor/failing governance."""
        weak_counts: dict[str, int] = {}
        for r in self._records:
            if r.grade in (GovernanceGrade.POOR, GovernanceGrade.FAILING):
                weak_counts[r.domain_name] = weak_counts.get(r.domain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for domain, count in weak_counts.items():
            if count > 1:
                results.append(
                    {
                        "domain_name": domain,
                        "weak_count": count,
                    }
                )
        results.sort(key=lambda x: x["weak_count"], reverse=True)
        return results

    def rank_by_governance_score(self) -> list[dict[str, Any]]:
        """Rank domains by avg governance score descending."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            totals[r.domain_name] = totals.get(r.domain_name, 0.0) + r.score
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
        results.sort(key=lambda x: x["avg_score"], reverse=True)
        return results

    def detect_governance_trends(self) -> list[dict[str, Any]]:
        """Detect domains with >3 non-excellent/good governance records."""
        non_passing: dict[str, int] = {}
        for r in self._records:
            if r.grade not in (GovernanceGrade.EXCELLENT, GovernanceGrade.GOOD):
                non_passing[r.domain_name] = non_passing.get(r.domain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for domain, count in non_passing.items():
            if count > 3:
                results.append(
                    {
                        "domain_name": domain,
                        "non_passing_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_passing_count"], reverse=True)
        return results

    # -- report / stats -----------------------------------------------

    def generate_report(self) -> GovernanceScorerReport:
        by_domain: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_domain[r.domain.value] = by_domain.get(r.domain.value, 0) + 1
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
        passing_count = sum(
            1 for r in self._records if r.grade in (GovernanceGrade.EXCELLENT, GovernanceGrade.GOOD)
        )
        passing_rate = round(passing_count / len(self._records) * 100, 2) if self._records else 0.0
        weak_domains = sum(1 for _ in self.identify_weak_domains())
        recs: list[str] = []
        if self._records and passing_rate < 80.0:
            recs.append(f"Passing rate {passing_rate}% is below 80.0% threshold")
        if weak_domains > 0:
            recs.append(f"{weak_domains} domain(s) with repeated weak governance")
        trends = len(self.detect_governance_trends())
        if trends > 0:
            recs.append(f"{trends} domain(s) detected with governance trends")
        if not recs:
            recs.append("Platform governance meets all targets")
        return GovernanceScorerReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            passing_rate_pct=passing_rate,
            by_domain=by_domain,
            by_grade=by_grade,
            weak_domain_count=weak_domains,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("governance_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_governance_score": self._min_governance_score,
            "domain_distribution": domain_dist,
            "unique_domains": len({r.domain_name for r in self._records}),
        }
