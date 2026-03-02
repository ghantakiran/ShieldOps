"""Governance Maturity Assessor — assess and track governance maturity levels."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MaturityLevel(StrEnum):
    OPTIMIZED = "optimized"
    MANAGED = "managed"
    DEFINED = "defined"
    REPEATABLE = "repeatable"
    INITIAL = "initial"


class GovernanceDomain(StrEnum):
    RISK_MANAGEMENT = "risk_management"
    POLICY_MANAGEMENT = "policy_management"
    COMPLIANCE = "compliance"
    AUDIT = "audit"
    SECURITY_OPERATIONS = "security_operations"


class AssessmentFrequency(StrEnum):
    CONTINUOUS = "continuous"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    AD_HOC = "ad_hoc"


# --- Models ---


class MaturityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str = ""
    maturity_level: MaturityLevel = MaturityLevel.OPTIMIZED
    governance_domain: GovernanceDomain = GovernanceDomain.RISK_MANAGEMENT
    assessment_frequency: AssessmentFrequency = AssessmentFrequency.CONTINUOUS
    maturity_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MaturityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str = ""
    maturity_level: MaturityLevel = MaturityLevel.OPTIMIZED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class GovernanceMaturityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_maturity_score: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class GovernanceMaturityAssessor:
    """Assess governance maturity across domains, track levels, identify maturity gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[MaturityRecord] = []
        self._analyses: list[MaturityAnalysis] = []
        logger.info(
            "governance_maturity_assessor.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_maturity(
        self,
        domain_name: str,
        maturity_level: MaturityLevel = MaturityLevel.OPTIMIZED,
        governance_domain: GovernanceDomain = GovernanceDomain.RISK_MANAGEMENT,
        assessment_frequency: AssessmentFrequency = AssessmentFrequency.CONTINUOUS,
        maturity_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MaturityRecord:
        record = MaturityRecord(
            domain_name=domain_name,
            maturity_level=maturity_level,
            governance_domain=governance_domain,
            assessment_frequency=assessment_frequency,
            maturity_score=maturity_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "governance_maturity_assessor.maturity_recorded",
            record_id=record.id,
            domain_name=domain_name,
            maturity_level=maturity_level.value,
            governance_domain=governance_domain.value,
        )
        return record

    def get_record(self, record_id: str) -> MaturityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        maturity_level: MaturityLevel | None = None,
        governance_domain: GovernanceDomain | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MaturityRecord]:
        results = list(self._records)
        if maturity_level is not None:
            results = [r for r in results if r.maturity_level == maturity_level]
        if governance_domain is not None:
            results = [r for r in results if r.governance_domain == governance_domain]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        domain_name: str,
        maturity_level: MaturityLevel = MaturityLevel.OPTIMIZED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MaturityAnalysis:
        analysis = MaturityAnalysis(
            domain_name=domain_name,
            maturity_level=maturity_level,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "governance_maturity_assessor.analysis_added",
            domain_name=domain_name,
            maturity_level=maturity_level.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by maturity_level; return count and avg maturity_score."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.maturity_level.value
            level_data.setdefault(key, []).append(r.maturity_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_maturity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where maturity_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.maturity_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "domain_name": r.domain_name,
                        "maturity_level": r.maturity_level.value,
                        "maturity_score": r.maturity_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["maturity_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg maturity_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.maturity_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_maturity_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_maturity_score"])
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

    def generate_report(self) -> GovernanceMaturityReport:
        by_level: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        for r in self._records:
            by_level[r.maturity_level.value] = by_level.get(r.maturity_level.value, 0) + 1
            by_domain[r.governance_domain.value] = by_domain.get(r.governance_domain.value, 0) + 1
            by_frequency[r.assessment_frequency.value] = (
                by_frequency.get(r.assessment_frequency.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.maturity_score < self._threshold)
        scores = [r.maturity_score for r in self._records]
        avg_maturity_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["domain_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} domain(s) below maturity threshold ({self._threshold})")
        if self._records and avg_maturity_score < self._threshold:
            recs.append(
                f"Avg maturity score {avg_maturity_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Governance maturity is healthy")
        return GovernanceMaturityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_maturity_score=avg_maturity_score,
            by_level=by_level,
            by_domain=by_domain,
            by_frequency=by_frequency,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("governance_maturity_assessor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.maturity_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "level_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
