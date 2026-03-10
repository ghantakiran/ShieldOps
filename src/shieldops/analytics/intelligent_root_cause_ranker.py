"""Intelligent Root Cause Ranker — root cause ranking and correlation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CauseCategory(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    CONFIGURATION = "configuration"
    EXTERNAL = "external"


class RankingMethod(StrEnum):
    BAYESIAN = "bayesian"
    FREQUENCY = "frequency"
    RECENCY = "recency"
    IMPACT = "impact"


class ConfidenceLevel(StrEnum):
    DEFINITIVE = "definitive"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    SPECULATIVE = "speculative"


# --- Models ---


class RootCauseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    cause_category: CauseCategory = CauseCategory.INFRASTRUCTURE
    ranking_method: RankingMethod = RankingMethod.BAYESIAN
    confidence_level: ConfidenceLevel = ConfidenceLevel.POSSIBLE
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RootCauseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    cause_category: CauseCategory = CauseCategory.INFRASTRUCTURE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IntelligentRootCauseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_cause_category: dict[str, int] = Field(default_factory=dict)
    by_ranking_method: dict[str, int] = Field(default_factory=dict)
    by_confidence_level: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IntelligentRootCauseRanker:
    """Intelligent Root Cause Ranker
    for root cause ranking and correlation.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[RootCauseRecord] = []
        self._analyses: list[RootCauseAnalysis] = []
        logger.info(
            "intelligent_root_cause_ranker.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        cause_category: CauseCategory = (CauseCategory.INFRASTRUCTURE),
        ranking_method: RankingMethod = (RankingMethod.BAYESIAN),
        confidence_level: ConfidenceLevel = (ConfidenceLevel.POSSIBLE),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RootCauseRecord:
        record = RootCauseRecord(
            name=name,
            cause_category=cause_category,
            ranking_method=ranking_method,
            confidence_level=confidence_level,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "intelligent_root_cause_ranker.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> RootCauseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        cause_category: CauseCategory | None = None,
        confidence_level: ConfidenceLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RootCauseRecord]:
        results = list(self._records)
        if cause_category is not None:
            results = [r for r in results if r.cause_category == cause_category]
        if confidence_level is not None:
            results = [r for r in results if r.confidence_level == confidence_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        cause_category: CauseCategory = (CauseCategory.INFRASTRUCTURE),
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RootCauseAnalysis:
        analysis = RootCauseAnalysis(
            name=name,
            cause_category=cause_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "intelligent_root_cause_ranker.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def rank_probable_causes(
        self,
    ) -> list[dict[str, Any]]:
        """Rank causes by probability score."""
        conf_weight = {
            "definitive": 1.0,
            "probable": 0.75,
            "possible": 0.5,
            "speculative": 0.25,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            weight = conf_weight.get(r.confidence_level.value, 0.5)
            ranked_score = round(r.score * weight, 2)
            results.append(
                {
                    "record_id": r.id,
                    "name": r.name,
                    "category": r.cause_category.value,
                    "confidence": r.confidence_level.value,
                    "raw_score": r.score,
                    "ranked_score": ranked_score,
                    "service": r.service,
                }
            )
        results.sort(key=lambda x: x["ranked_score"], reverse=True)
        return results

    def compute_cause_correlation(
        self,
    ) -> dict[str, Any]:
        """Compute correlation between cause categories."""
        cat_svc: dict[str, set[str]] = {}
        cat_scores: dict[str, list[float]] = {}
        for r in self._records:
            cat_svc.setdefault(r.cause_category.value, set()).add(r.service)
            cat_scores.setdefault(r.cause_category.value, []).append(r.score)
        correlations: dict[str, Any] = {}
        for cat, services in cat_svc.items():
            scores = cat_scores[cat]
            correlations[cat] = {
                "affected_services": len(services),
                "occurrence_count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
                "services": sorted(services),
            }
        return {
            "correlations": correlations,
            "total_causes": len(self._records),
        }

    def detect_cascading_failures(
        self,
    ) -> list[dict[str, Any]]:
        """Detect potential cascading failure patterns."""
        svc_causes: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            svc_causes.setdefault(r.service, []).append(
                {
                    "category": r.cause_category.value,
                    "score": r.score,
                    "time": r.created_at,
                }
            )
        cascades: list[dict[str, Any]] = []
        for svc, causes in svc_causes.items():
            if len(causes) > 1:
                cats = {c["category"] for c in causes}
                avg_score = round(sum(c["score"] for c in causes) / len(causes), 2)
                cascades.append(
                    {
                        "service": svc,
                        "cause_count": len(causes),
                        "unique_categories": len(cats),
                        "categories": sorted(cats),
                        "avg_score": avg_score,
                        "is_cascade": len(cats) > 1,
                    }
                )
        cascades.sort(key=lambda x: x["cause_count"], reverse=True)
        return cascades

    # -- report / stats -----------------------------------------------

    def generate_report(
        self,
    ) -> IntelligentRootCauseReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.cause_category.value] = by_e1.get(r.cause_category.value, 0) + 1
            by_e2[r.ranking_method.value] = by_e2.get(r.ranking_method.value, 0) + 1
            by_e3[r.confidence_level.value] = by_e3.get(r.confidence_level.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = [r.name for r in self._records if r.score < self._threshold][:5]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Intelligent Root Cause Ranker is healthy")
        return IntelligentRootCauseReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_cause_category=by_e1,
            by_ranking_method=by_e2,
            by_confidence_level=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("intelligent_root_cause_ranker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.cause_category.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "cause_category_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
