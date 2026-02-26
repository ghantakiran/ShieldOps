"""Incident Similarity Engine — find similar past incidents and match scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SimilarityDimension(StrEnum):
    SYMPTOMS = "symptoms"
    ROOT_CAUSE = "root_cause"
    AFFECTED_SERVICES = "affected_services"
    TIMELINE_PATTERN = "timeline_pattern"
    RESOLUTION_PATH = "resolution_path"


class MatchConfidence(StrEnum):
    EXACT = "exact"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NO_MATCH = "no_match"


class SimilarityScope(StrEnum):
    SAME_SERVICE = "same_service"
    SAME_TEAM = "same_team"
    SAME_CATEGORY = "same_category"
    CROSS_TEAM = "cross_team"
    PLATFORM_WIDE = "platform_wide"


# --- Models ---


class SimilarityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    dimension: SimilarityDimension = SimilarityDimension.SYMPTOMS
    confidence: MatchConfidence = MatchConfidence.MODERATE
    scope: SimilarityScope = SimilarityScope.SAME_SERVICE
    match_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class SimilarityMatch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    match_name: str = ""
    dimension: SimilarityDimension = SimilarityDimension.SYMPTOMS
    confidence: MatchConfidence = MatchConfidence.MODERATE
    score: float = 0.0
    incident_id: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentSimilarityReport(BaseModel):
    total_similarities: int = 0
    total_matches: int = 0
    avg_match_score_pct: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    high_confidence_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentSimilarityEngine:
    """Find similar past incidents, match scoring, similarity pattern detection."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[SimilarityRecord] = []
        self._matches: list[SimilarityMatch] = []
        logger.info(
            "incident_similarity.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_similarity(
        self,
        service_name: str,
        dimension: SimilarityDimension = SimilarityDimension.SYMPTOMS,
        confidence: MatchConfidence = MatchConfidence.MODERATE,
        scope: SimilarityScope = SimilarityScope.SAME_SERVICE,
        match_score: float = 0.0,
        details: str = "",
    ) -> SimilarityRecord:
        record = SimilarityRecord(
            service_name=service_name,
            dimension=dimension,
            confidence=confidence,
            scope=scope,
            match_score=match_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_similarity.recorded",
            record_id=record.id,
            service_name=service_name,
            dimension=dimension.value,
            confidence=confidence.value,
        )
        return record

    def get_similarity(self, record_id: str) -> SimilarityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_similarities(
        self,
        service_name: str | None = None,
        dimension: SimilarityDimension | None = None,
        limit: int = 50,
    ) -> list[SimilarityRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if dimension is not None:
            results = [r for r in results if r.dimension == dimension]
        return results[-limit:]

    def add_match(
        self,
        match_name: str,
        dimension: SimilarityDimension = SimilarityDimension.SYMPTOMS,
        confidence: MatchConfidence = MatchConfidence.MODERATE,
        score: float = 0.0,
        incident_id: str = "",
    ) -> SimilarityMatch:
        match = SimilarityMatch(
            match_name=match_name,
            dimension=dimension,
            confidence=confidence,
            score=score,
            incident_id=incident_id,
        )
        self._matches.append(match)
        if len(self._matches) > self._max_records:
            self._matches = self._matches[-self._max_records :]
        logger.info(
            "incident_similarity.match_added",
            match_name=match_name,
            dimension=dimension.value,
            confidence=confidence.value,
        )
        return match

    # -- domain operations -----------------------------------------------

    def analyze_similarity_patterns(self, service_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_score = round(sum(r.match_score for r in records) / len(records), 2)
        high_conf = sum(
            1 for r in records if r.confidence in (MatchConfidence.EXACT, MatchConfidence.HIGH)
        )
        return {
            "service_name": service_name,
            "total_records": len(records),
            "avg_match_score": avg_score,
            "high_confidence_count": high_conf,
            "meets_threshold": avg_score >= self._min_confidence_pct,
        }

    def identify_high_confidence_matches(self) -> list[dict[str, Any]]:
        confidence_counts: dict[str, int] = {}
        for r in self._records:
            if r.confidence in (MatchConfidence.EXACT, MatchConfidence.HIGH):
                confidence_counts[r.service_name] = confidence_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in confidence_counts.items():
            if count > 1:
                results.append({"service_name": svc, "high_confidence_count": count})
        results.sort(key=lambda x: x["high_confidence_count"], reverse=True)
        return results

    def rank_by_match_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service_name, []).append(r.match_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_match_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_match_score"], reverse=True)
        return results

    def detect_recurring_similarities(self) -> list[dict[str, Any]]:
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "similarity_count": count,
                        "recurring": True,
                    }
                )
        results.sort(key=lambda x: x["similarity_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> IncidentSimilarityReport:
        by_dimension: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.dimension.value] = by_dimension.get(r.dimension.value, 0) + 1
            by_confidence[r.confidence.value] = by_confidence.get(r.confidence.value, 0) + 1
        avg_score = (
            round(sum(r.match_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        high_conf = sum(
            1
            for r in self._records
            if r.confidence in (MatchConfidence.EXACT, MatchConfidence.HIGH)
        )
        recs: list[str] = []
        if avg_score < self._min_confidence_pct:
            recs.append(
                f"Average match score {avg_score}% is below {self._min_confidence_pct}% threshold"
            )
        recurring = len(self.detect_recurring_similarities())
        if recurring > 0:
            recs.append(f"{recurring} service(s) with recurring similarities")
        if not recs:
            recs.append("Incident similarity analysis meets targets")
        return IncidentSimilarityReport(
            total_similarities=len(self._records),
            total_matches=len(self._matches),
            avg_match_score_pct=avg_score,
            by_dimension=by_dimension,
            by_confidence=by_confidence,
            high_confidence_count=high_conf,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._matches.clear()
        logger.info("incident_similarity.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dim_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dimension.value
            dim_dist[key] = dim_dist.get(key, 0) + 1
        return {
            "total_similarities": len(self._records),
            "total_matches": len(self._matches),
            "min_confidence_pct": self._min_confidence_pct,
            "dimension_distribution": dim_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
