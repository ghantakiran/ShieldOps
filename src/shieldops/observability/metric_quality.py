"""Metric Quality Scorer — assess metric completeness, accuracy, and relevance."""

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
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    TIMELINESS = "timeliness"
    CONSISTENCY = "consistency"
    RELEVANCE = "relevance"


class QualityLevel(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNUSABLE = "unusable"


class QualityIssue(StrEnum):
    MISSING_DATA = "missing_data"
    STALE_DATA = "stale_data"
    HIGH_CARDINALITY = "high_cardinality"
    INCONSISTENT_LABELS = "inconsistent_labels"
    LOW_RESOLUTION = "low_resolution"


# --- Models ---


class MetricQualityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    quality_dimension: QualityDimension = QualityDimension.COMPLETENESS
    quality_level: QualityLevel = QualityLevel.ACCEPTABLE
    quality_issue: QualityIssue = QualityIssue.MISSING_DATA
    quality_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class QualityAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_name: str = ""
    quality_dimension: QualityDimension = QualityDimension.COMPLETENESS
    score_threshold: float = 0.0
    avg_quality_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MetricQualityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    poor_metrics: int = 0
    avg_quality_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_issue: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetricQualityScorer:
    """Assess metric completeness, accuracy, timeliness, consistency, and relevance."""

    def __init__(
        self,
        max_records: int = 200000,
        min_metric_quality_pct: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._min_metric_quality_pct = min_metric_quality_pct
        self._records: list[MetricQualityRecord] = []
        self._assessments: list[QualityAssessment] = []
        logger.info(
            "metric_quality.initialized",
            max_records=max_records,
            min_metric_quality_pct=min_metric_quality_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_quality(
        self,
        metric_name: str,
        quality_dimension: QualityDimension = QualityDimension.COMPLETENESS,
        quality_level: QualityLevel = QualityLevel.ACCEPTABLE,
        quality_issue: QualityIssue = QualityIssue.MISSING_DATA,
        quality_score: float = 0.0,
        team: str = "",
    ) -> MetricQualityRecord:
        record = MetricQualityRecord(
            metric_name=metric_name,
            quality_dimension=quality_dimension,
            quality_level=quality_level,
            quality_issue=quality_issue,
            quality_score=quality_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "metric_quality.quality_recorded",
            record_id=record.id,
            metric_name=metric_name,
            quality_dimension=quality_dimension.value,
            quality_level=quality_level.value,
        )
        return record

    def get_quality(self, record_id: str) -> MetricQualityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_qualities(
        self,
        dimension: QualityDimension | None = None,
        level: QualityLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MetricQualityRecord]:
        results = list(self._records)
        if dimension is not None:
            results = [r for r in results if r.quality_dimension == dimension]
        if level is not None:
            results = [r for r in results if r.quality_level == level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        assessment_name: str,
        quality_dimension: QualityDimension = QualityDimension.COMPLETENESS,
        score_threshold: float = 0.0,
        avg_quality_score: float = 0.0,
        description: str = "",
    ) -> QualityAssessment:
        assessment = QualityAssessment(
            assessment_name=assessment_name,
            quality_dimension=quality_dimension,
            score_threshold=score_threshold,
            avg_quality_score=avg_quality_score,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "metric_quality.assessment_added",
            assessment_name=assessment_name,
            quality_dimension=quality_dimension.value,
            score_threshold=score_threshold,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_metric_quality(self) -> dict[str, Any]:
        """Group by dimension; return count and avg quality score per dimension."""
        dimension_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.quality_dimension.value
            dimension_data.setdefault(key, []).append(r.quality_score)
        result: dict[str, Any] = {}
        for dimension, scores in dimension_data.items():
            result[dimension] = {
                "count": len(scores),
                "avg_quality_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_poor_metrics(self) -> list[dict[str, Any]]:
        """Return records where level is POOR or UNUSABLE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.quality_level in (QualityLevel.POOR, QualityLevel.UNUSABLE):
                results.append(
                    {
                        "record_id": r.id,
                        "metric_name": r.metric_name,
                        "quality_dimension": r.quality_dimension.value,
                        "quality_score": r.quality_score,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_quality_score(self) -> list[dict[str, Any]]:
        """Group by team, avg quality score, sort descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_quality_score": round(sum(scores) / len(scores), 2),
                    "count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_quality_score"], reverse=True)
        return results

    def detect_quality_degradation(self) -> dict[str, Any]:
        """Split-half on avg_quality_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.avg_quality_score for a in self._assessments]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> MetricQualityReport:
        by_dimension: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_issue: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.quality_dimension.value] = (
                by_dimension.get(r.quality_dimension.value, 0) + 1
            )
            by_level[r.quality_level.value] = by_level.get(r.quality_level.value, 0) + 1
            by_issue[r.quality_issue.value] = by_issue.get(r.quality_issue.value, 0) + 1
        poor_count = sum(
            1
            for r in self._records
            if r.quality_level in (QualityLevel.POOR, QualityLevel.UNUSABLE)
        )
        avg_score = (
            round(sum(r.quality_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_quality_score()
        top_items = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if avg_score < self._min_metric_quality_pct:
            recs.append(
                f"Avg quality score {avg_score}% is below "
                f"threshold ({self._min_metric_quality_pct}%)"
            )
        if poor_count > 0:
            recs.append(f"{poor_count} poor metric(s) detected — review quality")
        if not recs:
            recs.append("Metric quality is within acceptable limits")
        return MetricQualityReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            poor_metrics=poor_count,
            avg_quality_score=avg_score,
            by_dimension=by_dimension,
            by_level=by_level,
            by_issue=by_issue,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("metric_quality.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dimension_dist: dict[str, int] = {}
        for r in self._records:
            key = r.quality_dimension.value
            dimension_dist[key] = dimension_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "min_metric_quality_pct": self._min_metric_quality_pct,
            "dimension_distribution": dimension_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_metrics": len({r.metric_name for r in self._records}),
        }
