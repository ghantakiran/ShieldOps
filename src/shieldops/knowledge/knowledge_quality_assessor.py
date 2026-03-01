"""Knowledge Quality Assessor — assess knowledge base quality, detect inconsistencies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class QualityAspect(StrEnum):
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"
    RELEVANCE = "relevance"
    CONSISTENCY = "consistency"


class QualityRating(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNACCEPTABLE = "unacceptable"


class ContentCategory(StrEnum):
    TECHNICAL = "technical"
    PROCEDURAL = "procedural"
    ARCHITECTURAL = "architectural"
    OPERATIONAL = "operational"
    REFERENCE = "reference"


# --- Models ---


class QualityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    article_id: str = ""
    quality_aspect: QualityAspect = QualityAspect.ACCURACY
    quality_rating: QualityRating = QualityRating.ACCEPTABLE
    content_category: ContentCategory = ContentCategory.TECHNICAL
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class QualityMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    article_id: str = ""
    quality_aspect: QualityAspect = QualityAspect.ACCURACY
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeQualityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    poor_quality_count: int = 0
    avg_quality_score: float = 0.0
    by_aspect: dict[str, int] = Field(default_factory=dict)
    by_rating: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_poor: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeQualityAssessor:
    """Assess knowledge base quality, detect inconsistencies, track improvement progress."""

    def __init__(
        self,
        max_records: int = 200000,
        min_quality_score: float = 65.0,
    ) -> None:
        self._max_records = max_records
        self._min_quality_score = min_quality_score
        self._records: list[QualityRecord] = []
        self._metrics: list[QualityMetric] = []
        logger.info(
            "knowledge_quality_assessor.initialized",
            max_records=max_records,
            min_quality_score=min_quality_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_quality(
        self,
        article_id: str,
        quality_aspect: QualityAspect = QualityAspect.ACCURACY,
        quality_rating: QualityRating = QualityRating.ACCEPTABLE,
        content_category: ContentCategory = ContentCategory.TECHNICAL,
        quality_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> QualityRecord:
        record = QualityRecord(
            article_id=article_id,
            quality_aspect=quality_aspect,
            quality_rating=quality_rating,
            content_category=content_category,
            quality_score=quality_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_quality_assessor.quality_recorded",
            record_id=record.id,
            article_id=article_id,
            quality_aspect=quality_aspect.value,
            quality_rating=quality_rating.value,
        )
        return record

    def get_quality(self, record_id: str) -> QualityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_qualities(
        self,
        aspect: QualityAspect | None = None,
        rating: QualityRating | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[QualityRecord]:
        results = list(self._records)
        if aspect is not None:
            results = [r for r in results if r.quality_aspect == aspect]
        if rating is not None:
            results = [r for r in results if r.quality_rating == rating]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        article_id: str,
        quality_aspect: QualityAspect = QualityAspect.ACCURACY,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> QualityMetric:
        metric = QualityMetric(
            article_id=article_id,
            quality_aspect=quality_aspect,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "knowledge_quality_assessor.metric_added",
            article_id=article_id,
            quality_aspect=quality_aspect.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_quality_distribution(self) -> dict[str, Any]:
        """Group by quality_aspect; return count and avg quality_score."""
        aspect_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.quality_aspect.value
            aspect_data.setdefault(key, []).append(r.quality_score)
        result: dict[str, Any] = {}
        for aspect, scores in aspect_data.items():
            result[aspect] = {
                "count": len(scores),
                "avg_quality_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_poor_quality(self) -> list[dict[str, Any]]:
        """Return records where quality_rating is POOR or UNACCEPTABLE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.quality_rating in (QualityRating.POOR, QualityRating.UNACCEPTABLE):
                results.append(
                    {
                        "record_id": r.id,
                        "article_id": r.article_id,
                        "quality_rating": r.quality_rating.value,
                        "quality_score": r.quality_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_quality(self) -> list[dict[str, Any]]:
        """Group by service, avg quality_score, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_quality_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_quality_score"])
        return results

    def detect_quality_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.metric_score for m in self._metrics]
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

    def generate_report(self) -> KnowledgeQualityReport:
        by_aspect: dict[str, int] = {}
        by_rating: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_aspect[r.quality_aspect.value] = by_aspect.get(r.quality_aspect.value, 0) + 1
            by_rating[r.quality_rating.value] = by_rating.get(r.quality_rating.value, 0) + 1
            by_category[r.content_category.value] = by_category.get(r.content_category.value, 0) + 1
        poor_quality_count = sum(
            1
            for r in self._records
            if r.quality_rating in (QualityRating.POOR, QualityRating.UNACCEPTABLE)
        )
        scores = [r.quality_score for r in self._records]
        avg_quality_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        poor_list = self.identify_poor_quality()
        top_poor = [o["article_id"] for o in poor_list[:5]]
        recs: list[str] = []
        if self._records and avg_quality_score < self._min_quality_score:
            recs.append(
                f"Avg quality score {avg_quality_score} below threshold ({self._min_quality_score})"
            )
        if poor_quality_count > 0:
            recs.append(f"{poor_quality_count} poor-quality article(s) — initiate improvement")
        if not recs:
            recs.append("Knowledge quality levels are healthy")
        return KnowledgeQualityReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            poor_quality_count=poor_quality_count,
            avg_quality_score=avg_quality_score,
            by_aspect=by_aspect,
            by_rating=by_rating,
            by_category=by_category,
            top_poor=top_poor,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("knowledge_quality_assessor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        aspect_dist: dict[str, int] = {}
        for r in self._records:
            key = r.quality_aspect.value
            aspect_dist[key] = aspect_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_quality_score": self._min_quality_score,
            "aspect_distribution": aspect_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
