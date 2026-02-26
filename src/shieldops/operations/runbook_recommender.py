"""Runbook Recommendation Engine — match incidents to relevant runbooks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MatchCriteria(StrEnum):
    SYMPTOM_MATCH = "symptom_match"
    SERVICE_MATCH = "service_match"
    ERROR_PATTERN = "error_pattern"
    HISTORICAL_SUCCESS = "historical_success"
    KEYWORD_MATCH = "keyword_match"


class RecommendationConfidence(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"
    NO_MATCH = "no_match"


class RunbookRelevance(StrEnum):
    EXACT_FIT = "exact_fit"
    GOOD_FIT = "good_fit"
    PARTIAL_FIT = "partial_fit"
    RELATED = "related"
    GENERIC = "generic"


# --- Models ---


class RecommendationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    criteria: MatchCriteria = MatchCriteria.KEYWORD_MATCH
    confidence: RecommendationConfidence = RecommendationConfidence.LOW
    relevance: RunbookRelevance = RunbookRelevance.GENERIC
    accuracy_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookMatch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    match_name: str = ""
    criteria: MatchCriteria = MatchCriteria.KEYWORD_MATCH
    confidence: RecommendationConfidence = RecommendationConfidence.LOW
    effectiveness_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookRecommenderReport(BaseModel):
    total_recommendations: int = 0
    total_matches: int = 0
    avg_accuracy_pct: float = 0.0
    by_criteria: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    high_accuracy_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookRecommendationEngine:
    """Match incidents to relevant runbooks with confidence scoring."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[RecommendationRecord] = []
        self._matches: list[RunbookMatch] = []
        logger.info(
            "runbook_recommender.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_recommendation(
        self,
        service_name: str,
        criteria: MatchCriteria = MatchCriteria.KEYWORD_MATCH,
        confidence: RecommendationConfidence = RecommendationConfidence.LOW,
        relevance: RunbookRelevance = RunbookRelevance.GENERIC,
        accuracy_score: float = 0.0,
        details: str = "",
    ) -> RecommendationRecord:
        record = RecommendationRecord(
            service_name=service_name,
            criteria=criteria,
            confidence=confidence,
            relevance=relevance,
            accuracy_score=accuracy_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runbook_recommender.recommendation_recorded",
            record_id=record.id,
            service_name=service_name,
            criteria=criteria.value,
            confidence=confidence.value,
        )
        return record

    def get_recommendation(self, record_id: str) -> RecommendationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_recommendations(
        self,
        service_name: str | None = None,
        criteria: MatchCriteria | None = None,
        limit: int = 50,
    ) -> list[RecommendationRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if criteria is not None:
            results = [r for r in results if r.criteria == criteria]
        return results[-limit:]

    def add_match(
        self,
        match_name: str,
        criteria: MatchCriteria = MatchCriteria.KEYWORD_MATCH,
        confidence: RecommendationConfidence = RecommendationConfidence.LOW,
        effectiveness_score: float = 0.0,
        description: str = "",
    ) -> RunbookMatch:
        match = RunbookMatch(
            match_name=match_name,
            criteria=criteria,
            confidence=confidence,
            effectiveness_score=effectiveness_score,
            description=description,
        )
        self._matches.append(match)
        if len(self._matches) > self._max_records:
            self._matches = self._matches[-self._max_records :]
        logger.info(
            "runbook_recommender.match_added",
            match_id=match.id,
            match_name=match_name,
            criteria=criteria.value,
        )
        return match

    # -- domain operations -----------------------------------------------

    def analyze_recommendation_accuracy(self, service_name: str) -> dict[str, Any]:
        """Analyze recommendation accuracy for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_accuracy = round(sum(r.accuracy_score for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total": len(records),
            "avg_accuracy": avg_accuracy,
            "meets_threshold": avg_accuracy >= self._min_confidence_pct,
        }

    def identify_top_runbooks(self) -> list[dict[str, Any]]:
        """Find services with >1 HIGH or MODERATE confidence recommendations, sorted desc."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.confidence in (
                RecommendationConfidence.HIGH,
                RecommendationConfidence.MODERATE,
            ):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 1:
                results.append({"service_name": svc, "high_confidence_count": count})
        results.sort(key=lambda x: x["high_confidence_count"], reverse=True)
        return results

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        """Average accuracy score per service, sorted desc."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service_name, []).append(r.accuracy_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append({"service_name": svc, "avg_accuracy_score": avg})
        results.sort(key=lambda x: x["avg_accuracy_score"], reverse=True)
        return results

    def detect_recommendation_gaps(self) -> list[dict[str, Any]]:
        """Detect services with >3 recommendation records (high demand)."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append({"service_name": svc, "recommendation_count": count})
        results.sort(key=lambda x: x["recommendation_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RunbookRecommenderReport:
        by_criteria: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_criteria[r.criteria.value] = by_criteria.get(r.criteria.value, 0) + 1
            by_confidence[r.confidence.value] = by_confidence.get(r.confidence.value, 0) + 1
        avg_acc = (
            round(
                sum(r.accuracy_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_acc = sum(1 for r in self._records if r.accuracy_score >= self._min_confidence_pct)
        recs: list[str] = []
        low_conf = sum(
            1
            for r in self._records
            if r.confidence in (RecommendationConfidence.LOW, RecommendationConfidence.NO_MATCH)
        )
        if low_conf > 0:
            recs.append(f"{low_conf} low/no-match recommendation(s) need improvement")
        no_match = sum(
            1 for r in self._records if r.confidence == RecommendationConfidence.NO_MATCH
        )
        if no_match > 0:
            recs.append(f"{no_match} incident(s) had no matching runbook")
        if not recs:
            recs.append("Runbook recommendations are performing well")
        return RunbookRecommenderReport(
            total_recommendations=len(self._records),
            total_matches=len(self._matches),
            avg_accuracy_pct=avg_acc,
            by_criteria=by_criteria,
            by_confidence=by_confidence,
            high_accuracy_count=high_acc,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._matches.clear()
        logger.info("runbook_recommender.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        criteria_dist: dict[str, int] = {}
        for r in self._records:
            key = r.criteria.value
            criteria_dist[key] = criteria_dist.get(key, 0) + 1
        return {
            "total_recommendations": len(self._records),
            "total_matches": len(self._matches),
            "min_confidence_pct": self._min_confidence_pct,
            "criteria_distribution": criteria_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
