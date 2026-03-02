"""Data Quality Scorer — score data quality across pipelines, identify low-quality sources."""

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
    FRESHNESS = "freshness"
    CONSISTENCY = "consistency"
    ACCURACY = "accuracy"
    TIMELINESS = "timeliness"


class DataSource(StrEnum):
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"
    EVENTS = "events"
    CONFIGURATIONS = "configurations"


class QualityGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAILING = "failing"


# --- Models ---


class QualityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    quality_dimension: QualityDimension = QualityDimension.COMPLETENESS
    data_source: DataSource = DataSource.METRICS
    quality_grade: QualityGrade = QualityGrade.EXCELLENT
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class QualityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    quality_dimension: QualityDimension = QualityDimension.COMPLETENESS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DataQualityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_quality_count: int = 0
    avg_quality_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    top_low_quality: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataQualityScorer:
    """Score data quality across pipelines, identify low-quality sources, track improvements."""

    def __init__(
        self,
        max_records: int = 200000,
        quality_score_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._quality_score_threshold = quality_score_threshold
        self._records: list[QualityRecord] = []
        self._analyses: list[QualityAnalysis] = []
        logger.info(
            "data_quality_scorer.initialized",
            max_records=max_records,
            quality_score_threshold=quality_score_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_quality(
        self,
        pipeline_name: str,
        quality_dimension: QualityDimension = QualityDimension.COMPLETENESS,
        data_source: DataSource = DataSource.METRICS,
        quality_grade: QualityGrade = QualityGrade.EXCELLENT,
        quality_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> QualityRecord:
        record = QualityRecord(
            pipeline_name=pipeline_name,
            quality_dimension=quality_dimension,
            data_source=data_source,
            quality_grade=quality_grade,
            quality_score=quality_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_quality_scorer.quality_recorded",
            record_id=record.id,
            pipeline_name=pipeline_name,
            quality_dimension=quality_dimension.value,
            data_source=data_source.value,
        )
        return record

    def get_quality(self, record_id: str) -> QualityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_quality_records(
        self,
        quality_dimension: QualityDimension | None = None,
        data_source: DataSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[QualityRecord]:
        results = list(self._records)
        if quality_dimension is not None:
            results = [r for r in results if r.quality_dimension == quality_dimension]
        if data_source is not None:
            results = [r for r in results if r.data_source == data_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        pipeline_name: str,
        quality_dimension: QualityDimension = QualityDimension.COMPLETENESS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> QualityAnalysis:
        analysis = QualityAnalysis(
            pipeline_name=pipeline_name,
            quality_dimension=quality_dimension,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_quality_scorer.analysis_added",
            pipeline_name=pipeline_name,
            quality_dimension=quality_dimension.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_quality_distribution(self) -> dict[str, Any]:
        """Group by quality_dimension; return count and avg quality_score."""
        dim_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.quality_dimension.value
            dim_data.setdefault(key, []).append(r.quality_score)
        result: dict[str, Any] = {}
        for dim, scores in dim_data.items():
            result[dim] = {
                "count": len(scores),
                "avg_quality_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_quality_pipelines(self) -> list[dict[str, Any]]:
        """Return records where quality_score < quality_score_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.quality_score < self._quality_score_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "pipeline_name": r.pipeline_name,
                        "quality_dimension": r.quality_dimension.value,
                        "quality_score": r.quality_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["quality_score"])

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

    def generate_report(self) -> DataQualityReport:
        by_dimension: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.quality_dimension.value] = (
                by_dimension.get(r.quality_dimension.value, 0) + 1
            )
            by_source[r.data_source.value] = by_source.get(r.data_source.value, 0) + 1
            by_grade[r.quality_grade.value] = by_grade.get(r.quality_grade.value, 0) + 1
        low_quality_count = sum(
            1 for r in self._records if r.quality_score < self._quality_score_threshold
        )
        scores = [r.quality_score for r in self._records]
        avg_quality_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_quality_pipelines()
        top_low_quality = [o["pipeline_name"] for o in low_list[:5]]
        recs: list[str] = []
        if low_quality_count > 0:
            recs.append(f"{low_quality_count} low-quality pipeline(s) — review for improvement")
        if self._records and avg_quality_score < self._quality_score_threshold:
            recs.append(
                f"Avg quality score {avg_quality_score} below threshold "
                f"({self._quality_score_threshold})"
            )
        if not recs:
            recs.append("Data quality levels are healthy")
        return DataQualityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_quality_count=low_quality_count,
            avg_quality_score=avg_quality_score,
            by_dimension=by_dimension,
            by_source=by_source,
            by_grade=by_grade,
            top_low_quality=top_low_quality,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_quality_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dim_dist: dict[str, int] = {}
        for r in self._records:
            key = r.quality_dimension.value
            dim_dist[key] = dim_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_score_threshold": self._quality_score_threshold,
            "quality_dimension_distribution": dim_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
