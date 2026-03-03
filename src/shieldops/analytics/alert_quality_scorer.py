"""Alert Quality Scorer — score alert quality across dimensions and sources."""

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
    ACCURACY = "accuracy"
    ACTIONABILITY = "actionability"
    TIMELINESS = "timeliness"
    CONTEXT = "context"
    DEDUPLICATION = "deduplication"


class AlertSource(StrEnum):
    SIEM = "siem"
    IDS = "ids"
    EDR = "edr"
    CUSTOM = "custom"
    THIRD_PARTY = "third_party"


class QualityGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


# --- Models ---


class AlertQualityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    quality_id: str = ""
    quality_dimension: QualityDimension = QualityDimension.ACCURACY
    alert_source: AlertSource = AlertSource.SIEM
    quality_grade: QualityGrade = QualityGrade.GOOD
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertQualityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    quality_id: str = ""
    quality_dimension: QualityDimension = QualityDimension.ACCURACY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertQualityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_quality_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertQualityScorer:
    """Score alert quality across dimensions, sources, and grades."""

    def __init__(
        self,
        max_records: int = 200000,
        quality_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[AlertQualityRecord] = []
        self._analyses: list[AlertQualityAnalysis] = []
        logger.info(
            "alert_quality_scorer.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_quality(
        self,
        quality_id: str,
        quality_dimension: QualityDimension = QualityDimension.ACCURACY,
        alert_source: AlertSource = AlertSource.SIEM,
        quality_grade: QualityGrade = QualityGrade.GOOD,
        quality_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AlertQualityRecord:
        record = AlertQualityRecord(
            quality_id=quality_id,
            quality_dimension=quality_dimension,
            alert_source=alert_source,
            quality_grade=quality_grade,
            quality_score=quality_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_quality_scorer.quality_recorded",
            record_id=record.id,
            quality_id=quality_id,
            quality_dimension=quality_dimension.value,
            alert_source=alert_source.value,
        )
        return record

    def get_quality(self, record_id: str) -> AlertQualityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_qualities(
        self,
        quality_dimension: QualityDimension | None = None,
        alert_source: AlertSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AlertQualityRecord]:
        results = list(self._records)
        if quality_dimension is not None:
            results = [r for r in results if r.quality_dimension == quality_dimension]
        if alert_source is not None:
            results = [r for r in results if r.alert_source == alert_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        quality_id: str,
        quality_dimension: QualityDimension = QualityDimension.ACCURACY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AlertQualityAnalysis:
        analysis = AlertQualityAnalysis(
            quality_id=quality_id,
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
            "alert_quality_scorer.analysis_added",
            quality_id=quality_id,
            quality_dimension=quality_dimension.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_dimension_distribution(self) -> dict[str, Any]:
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

    def identify_quality_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.quality_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "quality_id": r.quality_id,
                        "quality_dimension": r.quality_dimension.value,
                        "quality_score": r.quality_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["quality_score"])

    def rank_by_quality(self) -> list[dict[str, Any]]:
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

    def generate_report(self) -> AlertQualityReport:
        by_dimension: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.quality_dimension.value] = (
                by_dimension.get(r.quality_dimension.value, 0) + 1
            )
            by_source[r.alert_source.value] = by_source.get(r.alert_source.value, 0) + 1
            by_grade[r.quality_grade.value] = by_grade.get(r.quality_grade.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.quality_score < self._quality_threshold)
        scores = [r.quality_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_quality_gaps()
        top_gaps = [o["quality_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} alert(s) below quality threshold ({self._quality_threshold})")
        if self._records and avg_score < self._quality_threshold:
            recs.append(
                f"Avg quality score {avg_score} below threshold ({self._quality_threshold})"
            )
        if not recs:
            recs.append("Alert quality is healthy")
        return AlertQualityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_quality_score=avg_score,
            by_dimension=by_dimension,
            by_source=by_source,
            by_grade=by_grade,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("alert_quality_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dimension_dist: dict[str, int] = {}
        for r in self._records:
            key = r.quality_dimension.value
            dimension_dist[key] = dimension_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "dimension_distribution": dimension_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
