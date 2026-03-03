"""Resilience Score Calculator — compute multi-dimensional resilience scores."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResilienceDimension(StrEnum):
    AVAILABILITY = "availability"
    RECOVERABILITY = "recoverability"
    SCALABILITY = "scalability"
    OBSERVABILITY = "observability"
    REDUNDANCY = "redundancy"


class ScoreCategory(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class AssessmentScope(StrEnum):
    SERVICE = "service"
    TEAM = "team"
    PLATFORM = "platform"
    REGION = "region"
    GLOBAL = "global"


# --- Models ---


class ResilienceScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dimension: ResilienceDimension = ResilienceDimension.AVAILABILITY
    category: ScoreCategory = ScoreCategory.GOOD
    scope: AssessmentScope = AssessmentScope.SERVICE
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ResilienceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dimension: ResilienceDimension = ResilienceDimension.AVAILABILITY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResilienceScoreReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResilienceScoreCalculator:
    """Calculate resilience scores across dimensions and identify weak spots."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ResilienceScore] = []
        self._analyses: list[ResilienceAnalysis] = []
        logger.info(
            "resilience_score_calculator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_score(
        self,
        service: str,
        dimension: ResilienceDimension = ResilienceDimension.AVAILABILITY,
        category: ScoreCategory = ScoreCategory.GOOD,
        scope: AssessmentScope = AssessmentScope.SERVICE,
        score: float = 0.0,
        team: str = "",
    ) -> ResilienceScore:
        record = ResilienceScore(
            dimension=dimension,
            category=category,
            scope=scope,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "resilience_score_calculator.score_recorded",
            record_id=record.id,
            service=service,
            dimension=dimension.value,
            score=score,
        )
        return record

    def get_score(self, record_id: str) -> ResilienceScore | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scores(
        self,
        dimension: ResilienceDimension | None = None,
        category: ScoreCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ResilienceScore]:
        results = list(self._records)
        if dimension is not None:
            results = [r for r in results if r.dimension == dimension]
        if category is not None:
            results = [r for r in results if r.category == category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        dimension: ResilienceDimension = ResilienceDimension.AVAILABILITY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ResilienceAnalysis:
        analysis = ResilienceAnalysis(
            dimension=dimension,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "resilience_score_calculator.analysis_added",
            dimension=dimension.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by dimension; return count and avg score."""
        dim_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.dimension.value
            dim_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for dim, scores in dim_data.items():
            result[dim] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_score_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "dimension": r.dimension.value,
                        "score": r.score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_score_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ResilienceScoreReport:
        by_dimension: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.dimension.value] = by_dimension.get(r.dimension.value, 0) + 1
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_scope[r.scope.value] = by_scope.get(r.scope.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_score_gaps()
        top_gaps = [o["service"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} service(s) below resilience threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg resilience score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Resilience scores are healthy")
        return ResilienceScoreReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_dimension=by_dimension,
            by_category=by_category,
            by_scope=by_scope,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("resilience_score_calculator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dim_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dimension.value
            dim_dist[key] = dim_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "dimension_distribution": dim_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
