"""Postmortem Quality Scorer — score postmortem completeness, actionability, and learning value."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class QualityDimension(StrEnum):
    TIMELINE_ACCURACY = "timeline_accuracy"
    ROOT_CAUSE_DEPTH = "root_cause_depth"
    ACTION_ITEM_CLARITY = "action_item_clarity"
    BLAMELESSNESS = "blamelessness"
    LEARNING_VALUE = "learning_value"


class QualityGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    INCOMPLETE = "incomplete"


class QualityTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class PostmortemRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    dimension: QualityDimension = QualityDimension.TIMELINE_ACCURACY
    grade: QualityGrade = QualityGrade.ADEQUATE
    quality_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DimensionScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dimension_name: str = ""
    dimension: QualityDimension = QualityDimension.TIMELINE_ACCURACY
    grade: QualityGrade = QualityGrade.ADEQUATE
    score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PostmortemQualityReport(BaseModel):
    total_records: int = 0
    total_dimensions: int = 0
    avg_quality_score_pct: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    poor_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PostmortemQualityScorer:
    """Score postmortem completeness, actionability, and learning value."""

    def __init__(
        self,
        max_records: int = 200000,
        min_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_score = min_score
        self._records: list[PostmortemRecord] = []
        self._dimensions: list[DimensionScore] = []
        logger.info(
            "postmortem_quality.initialized",
            max_records=max_records,
            min_score=min_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_postmortem(
        self,
        service_name: str,
        dimension: QualityDimension = QualityDimension.TIMELINE_ACCURACY,
        grade: QualityGrade = QualityGrade.ADEQUATE,
        quality_score: float = 0.0,
        details: str = "",
    ) -> PostmortemRecord:
        record = PostmortemRecord(
            service_name=service_name,
            dimension=dimension,
            grade=grade,
            quality_score=quality_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "postmortem_quality.postmortem_recorded",
            record_id=record.id,
            service_name=service_name,
            grade=grade.value,
        )
        return record

    def get_postmortem(self, record_id: str) -> PostmortemRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_postmortems(
        self,
        service_name: str | None = None,
        dimension: QualityDimension | None = None,
        limit: int = 50,
    ) -> list[PostmortemRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if dimension is not None:
            results = [r for r in results if r.dimension == dimension]
        return results[-limit:]

    def add_dimension_score(
        self,
        dimension_name: str,
        dimension: QualityDimension = QualityDimension.TIMELINE_ACCURACY,
        grade: QualityGrade = QualityGrade.ADEQUATE,
        score: float = 0.0,
        description: str = "",
    ) -> DimensionScore:
        dim_score = DimensionScore(
            dimension_name=dimension_name,
            dimension=dimension,
            grade=grade,
            score=score,
            description=description,
        )
        self._dimensions.append(dim_score)
        if len(self._dimensions) > self._max_records:
            self._dimensions = self._dimensions[-self._max_records :]
        logger.info(
            "postmortem_quality.dimension_score_added",
            dimension_name=dimension_name,
            grade=grade.value,
        )
        return dim_score

    # -- domain operations -----------------------------------------------

    def analyze_postmortem_quality(self, service_name: str) -> dict[str, Any]:
        """Analyze average quality score for a service and check threshold."""
        svc_records = [r for r in self._records if r.service_name == service_name]
        if not svc_records:
            return {"service_name": service_name, "status": "no_data"}
        avg_score = round(
            sum(r.quality_score for r in svc_records) / len(svc_records),
            2,
        )
        meets_threshold = avg_score >= self._min_score
        return {
            "service_name": service_name,
            "avg_quality_score": avg_score,
            "record_count": len(svc_records),
            "meets_threshold": meets_threshold,
            "min_score": self._min_score,
        }

    def identify_poor_postmortems(self) -> list[dict[str, Any]]:
        """Find services with more than one POOR or INCOMPLETE grade."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.grade in (QualityGrade.POOR, QualityGrade.INCOMPLETE):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 1:
                results.append({"service_name": svc, "poor_incomplete_count": count})
        results.sort(key=lambda x: x["poor_incomplete_count"], reverse=True)
        return results

    def rank_by_quality_score(self) -> list[dict[str, Any]]:
        """Rank services by average quality score descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service_name, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_quality_score": avg,
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_quality_score"], reverse=True)
        return results

    def detect_quality_trends(self) -> list[dict[str, Any]]:
        """Detect services with more than 3 postmortem records."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append({"service_name": svc, "record_count": count})
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> PostmortemQualityReport:
        by_dimension: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.dimension.value] = by_dimension.get(r.dimension.value, 0) + 1
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
        avg_score = (
            round(
                sum(r.quality_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        poor_count = sum(1 for r in self._records if r.grade == QualityGrade.POOR)
        recs: list[str] = []
        if poor_count > 0:
            recs.append(f"{poor_count} postmortem(s) with poor quality detected")
        incomplete_count = sum(1 for r in self._records if r.grade == QualityGrade.INCOMPLETE)
        if incomplete_count > 0:
            recs.append(f"{incomplete_count} incomplete postmortem(s) detected")
        if not recs:
            recs.append("Postmortem quality levels are healthy")
        return PostmortemQualityReport(
            total_records=len(self._records),
            total_dimensions=len(self._dimensions),
            avg_quality_score_pct=avg_score,
            by_dimension=by_dimension,
            by_grade=by_grade,
            poor_count=poor_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._dimensions.clear()
        logger.info("postmortem_quality.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dimension_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dimension.value
            dimension_dist[key] = dimension_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_dimensions": len(self._dimensions),
            "min_score": self._min_score,
            "dimension_distribution": dimension_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
