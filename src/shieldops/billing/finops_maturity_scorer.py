"""FinOps Maturity Scorer — assess and track FinOps maturity across domains."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MaturityDomain(StrEnum):
    VISIBILITY = "visibility"
    OPTIMIZATION = "optimization"
    OPERATIONS = "operations"
    GOVERNANCE = "governance"
    CULTURE = "culture"


class MaturityLevel(StrEnum):
    CRAWL = "crawl"
    WALK = "walk"
    RUN = "run"
    FLY = "fly"
    OPTIMIZED = "optimized"


class AssessmentArea(StrEnum):
    COST_ALLOCATION = "cost_allocation"
    FORECASTING = "forecasting"
    ANOMALY_DETECTION = "anomaly_detection"
    RIGHTSIZING = "rightsizing"
    COMMITMENT = "commitment"


# --- Models ---


class MaturityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    maturity_domain: MaturityDomain = MaturityDomain.VISIBILITY
    maturity_level: MaturityLevel = MaturityLevel.CRAWL
    assessment_area: AssessmentArea = AssessmentArea.COST_ALLOCATION
    maturity_score: float = 0.0
    target_score: float = 100.0
    gap: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MaturityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    maturity_domain: MaturityDomain = MaturityDomain.VISIBILITY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FinOpsMaturityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    mature_count: int = 0
    avg_maturity_score: float = 0.0
    by_maturity_domain: dict[str, int] = Field(default_factory=dict)
    by_maturity_level: dict[str, int] = Field(default_factory=dict)
    by_assessment_area: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class FinOpsMaturityScorer:
    """Assess and track FinOps maturity across domains and teams."""

    def __init__(
        self,
        max_records: int = 200000,
        maturity_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._maturity_threshold = maturity_threshold
        self._records: list[MaturityRecord] = []
        self._analyses: list[MaturityAnalysis] = []
        logger.info(
            "finops_maturity_scorer.initialized",
            max_records=max_records,
            maturity_threshold=maturity_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_maturity(
        self,
        maturity_domain: MaturityDomain = MaturityDomain.VISIBILITY,
        maturity_level: MaturityLevel = MaturityLevel.CRAWL,
        assessment_area: AssessmentArea = AssessmentArea.COST_ALLOCATION,
        maturity_score: float = 0.0,
        target_score: float = 100.0,
        gap: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MaturityRecord:
        record = MaturityRecord(
            maturity_domain=maturity_domain,
            maturity_level=maturity_level,
            assessment_area=assessment_area,
            maturity_score=maturity_score,
            target_score=target_score,
            gap=gap,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "finops_maturity_scorer.maturity_recorded",
            record_id=record.id,
            maturity_domain=maturity_domain.value,
            maturity_score=maturity_score,
        )
        return record

    def get_maturity(self, record_id: str) -> MaturityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_maturities(
        self,
        maturity_domain: MaturityDomain | None = None,
        maturity_level: MaturityLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MaturityRecord]:
        results = list(self._records)
        if maturity_domain is not None:
            results = [r for r in results if r.maturity_domain == maturity_domain]
        if maturity_level is not None:
            results = [r for r in results if r.maturity_level == maturity_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        maturity_domain: MaturityDomain = MaturityDomain.VISIBILITY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MaturityAnalysis:
        analysis = MaturityAnalysis(
            maturity_domain=maturity_domain,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "finops_maturity_scorer.analysis_added",
            maturity_domain=maturity_domain.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_domain_distribution(self) -> dict[str, Any]:
        """Group by maturity_domain; return count and avg maturity_score."""
        domain_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.maturity_domain.value
            domain_data.setdefault(key, []).append(r.maturity_score)
        result: dict[str, Any] = {}
        for domain, scores in domain_data.items():
            result[domain] = {
                "count": len(scores),
                "avg_maturity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_maturity_gaps(self) -> list[dict[str, Any]]:
        """Return records where maturity_score < maturity_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.maturity_score < self._maturity_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "maturity_domain": r.maturity_domain.value,
                        "maturity_level": r.maturity_level.value,
                        "maturity_score": r.maturity_score,
                        "gap": r.gap,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["maturity_score"])

    def rank_by_maturity_score(self) -> list[dict[str, Any]]:
        """Group by team, avg maturity_score, sort ascending (lowest first)."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.maturity_score)
        results: list[dict[str, Any]] = [
            {
                "team": team,
                "avg_maturity_score": round(sum(s) / len(s), 2),
            }
            for team, s in team_scores.items()
        ]
        results.sort(key=lambda x: x["avg_maturity_score"])
        return results

    def detect_maturity_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
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

    def generate_report(self) -> FinOpsMaturityReport:
        by_domain: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_area: dict[str, int] = {}
        for r in self._records:
            by_domain[r.maturity_domain.value] = by_domain.get(r.maturity_domain.value, 0) + 1
            by_level[r.maturity_level.value] = by_level.get(r.maturity_level.value, 0) + 1
            by_area[r.assessment_area.value] = by_area.get(r.assessment_area.value, 0) + 1
        mature_count = sum(1 for r in self._records if r.maturity_score >= self._maturity_threshold)
        scores = [r.maturity_score for r in self._records]
        avg_maturity_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = self.identify_maturity_gaps()
        top_gaps = [o["record_id"] for o in gaps[:5]]
        recs: list[str] = []
        if gaps:
            recs.append(
                f"{len(gaps)} domain(s) below maturity threshold ({self._maturity_threshold})"
            )
        if avg_maturity_score < self._maturity_threshold and self._records:
            recs.append(
                f"Avg maturity score {avg_maturity_score} below target ({self._maturity_threshold})"
            )
        if not recs:
            recs.append("FinOps maturity is at target level")
        return FinOpsMaturityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            mature_count=mature_count,
            avg_maturity_score=avg_maturity_score,
            by_maturity_domain=by_domain,
            by_maturity_level=by_level,
            by_assessment_area=by_area,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("finops_maturity_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.maturity_domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "maturity_threshold": self._maturity_threshold,
            "maturity_domain_distribution": domain_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
