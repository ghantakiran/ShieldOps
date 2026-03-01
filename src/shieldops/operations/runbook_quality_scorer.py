"""Runbook Quality Scorer — score runbook quality, detect outdated runbooks."""

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
    CLARITY = "clarity"
    CURRENCY = "currency"
    TESTABILITY = "testability"


class QualityGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    FAILING = "failing"


class RunbookType(StrEnum):
    AUTOMATED = "automated"
    SEMI_AUTOMATED = "semi_automated"
    MANUAL = "manual"
    REFERENCE = "reference"
    TROUBLESHOOTING = "troubleshooting"


# --- Models ---


class QualityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    quality_dimension: QualityDimension = QualityDimension.COMPLETENESS
    quality_grade: QualityGrade = QualityGrade.ADEQUATE
    runbook_type: RunbookType = RunbookType.AUTOMATED
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class QualityAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    quality_dimension: QualityDimension = QualityDimension.COMPLETENESS
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookQualityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    low_quality_count: int = 0
    avg_quality_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    top_low_quality: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookQualityScorer:
    """Score runbook quality, detect outdated runbooks."""

    def __init__(
        self,
        max_records: int = 200000,
        min_quality_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_quality_score = min_quality_score
        self._records: list[QualityRecord] = []
        self._assessments: list[QualityAssessment] = []
        logger.info(
            "runbook_quality_scorer.initialized",
            max_records=max_records,
            min_quality_score=min_quality_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_quality(
        self,
        runbook_id: str,
        quality_dimension: QualityDimension = QualityDimension.COMPLETENESS,
        quality_grade: QualityGrade = QualityGrade.ADEQUATE,
        runbook_type: RunbookType = RunbookType.AUTOMATED,
        quality_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> QualityRecord:
        record = QualityRecord(
            runbook_id=runbook_id,
            quality_dimension=quality_dimension,
            quality_grade=quality_grade,
            runbook_type=runbook_type,
            quality_score=quality_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runbook_quality_scorer.quality_recorded",
            record_id=record.id,
            runbook_id=runbook_id,
            quality_dimension=quality_dimension.value,
            quality_grade=quality_grade.value,
        )
        return record

    def get_quality(self, record_id: str) -> QualityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_qualities(
        self,
        dimension: QualityDimension | None = None,
        grade: QualityGrade | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[QualityRecord]:
        results = list(self._records)
        if dimension is not None:
            results = [r for r in results if r.quality_dimension == dimension]
        if grade is not None:
            results = [r for r in results if r.quality_grade == grade]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        runbook_id: str,
        quality_dimension: QualityDimension = QualityDimension.COMPLETENESS,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> QualityAssessment:
        assessment = QualityAssessment(
            runbook_id=runbook_id,
            quality_dimension=quality_dimension,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "runbook_quality_scorer.assessment_added",
            runbook_id=runbook_id,
            quality_dimension=quality_dimension.value,
            assessment_score=assessment_score,
        )
        return assessment

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

    def identify_low_quality(self) -> list[dict[str, Any]]:
        """Return records where quality_grade is POOR or FAILING."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.quality_grade in (QualityGrade.POOR, QualityGrade.FAILING):
                results.append(
                    {
                        "record_id": r.id,
                        "runbook_id": r.runbook_id,
                        "quality_dimension": r.quality_dimension.value,
                        "quality_grade": r.quality_grade.value,
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
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.assessment_score for a in self._assessments]
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

    def generate_report(self) -> RunbookQualityReport:
        by_dimension: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.quality_dimension.value] = (
                by_dimension.get(r.quality_dimension.value, 0) + 1
            )
            by_grade[r.quality_grade.value] = by_grade.get(r.quality_grade.value, 0) + 1
            by_type[r.runbook_type.value] = by_type.get(r.runbook_type.value, 0) + 1
        low_quality_count = sum(
            1 for r in self._records if r.quality_grade in (QualityGrade.POOR, QualityGrade.FAILING)
        )
        scores = [r.quality_score for r in self._records]
        avg_quality_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        lq_list = self.identify_low_quality()
        top_low_quality = [o["runbook_id"] for o in lq_list[:5]]
        recs: list[str] = []
        if self._records and avg_quality_score < self._min_quality_score:
            recs.append(
                f"Avg quality score {avg_quality_score} below threshold ({self._min_quality_score})"
            )
        if low_quality_count > 0:
            recs.append(
                f"{low_quality_count} low-quality runbook(s) — review and improve documentation"
            )
        if not recs:
            recs.append("Runbook quality levels are healthy")
        return RunbookQualityReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            low_quality_count=low_quality_count,
            avg_quality_score=avg_quality_score,
            by_dimension=by_dimension,
            by_grade=by_grade,
            by_type=by_type,
            top_low_quality=top_low_quality,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("runbook_quality_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dim_dist: dict[str, int] = {}
        for r in self._records:
            key = r.quality_dimension.value
            dim_dist[key] = dim_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "min_quality_score": self._min_quality_score,
            "dimension_distribution": dim_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
