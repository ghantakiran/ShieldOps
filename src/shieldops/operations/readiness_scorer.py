"""Operational Readiness Scorer — score operational readiness across dimensions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReadinessDimension(StrEnum):
    MONITORING = "monitoring"
    RUNBOOKS = "runbooks"
    ONCALL = "oncall"
    ROLLBACK = "rollback"
    DOCUMENTATION = "documentation"


class ReadinessGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    INSUFFICIENT = "insufficient"
    FAILING = "failing"


class AssessmentTrigger(StrEnum):
    PRE_DEPLOYMENT = "pre_deployment"
    SCHEDULED = "scheduled"
    POST_INCIDENT = "post_incident"
    BUSINESS_EVENT = "business_event"
    MANUAL = "manual"


# --- Models ---


class ReadinessAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    dimension: ReadinessDimension = ReadinessDimension.MONITORING
    grade: ReadinessGrade = ReadinessGrade.ADEQUATE
    score: float = 0.0
    trigger: AssessmentTrigger = AssessmentTrigger.MANUAL
    assessor: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ReadinessGap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    dimension: ReadinessDimension = ReadinessDimension.MONITORING
    current_grade: ReadinessGrade = ReadinessGrade.FAILING
    target_grade: ReadinessGrade = ReadinessGrade.GOOD
    remediation: str = ""
    priority: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ReadinessReport(BaseModel):
    total_assessments: int = 0
    total_gaps: int = 0
    avg_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    failing_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class OperationalReadinessScorer:
    """Score operational readiness across dimensions."""

    def __init__(
        self,
        max_records: int = 200000,
        min_readiness_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_readiness_score = min_readiness_score
        self._records: list[ReadinessAssessment] = []
        self._gaps: list[ReadinessGap] = []
        logger.info(
            "readiness_scorer.initialized",
            max_records=max_records,
            min_readiness_score=min_readiness_score,
        )

    # -- record / get / list -------------------------------------------------

    def record_assessment(
        self,
        service_name: str,
        dimension: ReadinessDimension = ReadinessDimension.MONITORING,
        grade: ReadinessGrade = ReadinessGrade.ADEQUATE,
        score: float = 0.0,
        trigger: AssessmentTrigger = AssessmentTrigger.MANUAL,
        assessor: str = "",
        details: str = "",
    ) -> ReadinessAssessment:
        record = ReadinessAssessment(
            service_name=service_name,
            dimension=dimension,
            grade=grade,
            score=score,
            trigger=trigger,
            assessor=assessor,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "readiness_scorer.assessment_recorded",
            record_id=record.id,
            service_name=service_name,
            dimension=dimension.value,
        )
        return record

    def get_assessment(self, record_id: str) -> ReadinessAssessment | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_assessments(
        self,
        service_name: str | None = None,
        dimension: ReadinessDimension | None = None,
        limit: int = 50,
    ) -> list[ReadinessAssessment]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if dimension is not None:
            results = [r for r in results if r.dimension == dimension]
        return results[-limit:]

    def record_gap(
        self,
        service_name: str,
        dimension: ReadinessDimension = ReadinessDimension.MONITORING,
        current_grade: ReadinessGrade = ReadinessGrade.FAILING,
        target_grade: ReadinessGrade = ReadinessGrade.GOOD,
        remediation: str = "",
        priority: int = 0,
        details: str = "",
    ) -> ReadinessGap:
        gap = ReadinessGap(
            service_name=service_name,
            dimension=dimension,
            current_grade=current_grade,
            target_grade=target_grade,
            remediation=remediation,
            priority=priority,
            details=details,
        )
        self._gaps.append(gap)
        if len(self._gaps) > self._max_records:
            self._gaps = self._gaps[-self._max_records :]
        logger.info(
            "readiness_scorer.gap_recorded",
            service_name=service_name,
            dimension=dimension.value,
        )
        return gap

    # -- domain operations ---------------------------------------------------

    def analyze_service_readiness(self, service_name: str) -> dict[str, Any]:
        """Analyze readiness for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        latest = records[-1]
        avg_score = round(sum(r.score for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total_assessments": len(records),
            "avg_score": avg_score,
            "latest_grade": latest.grade.value,
            "latest_dimension": latest.dimension.value,
        }

    def identify_failing_services(self) -> list[dict[str, Any]]:
        """Find services with readiness score below minimum threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._min_readiness_score:
                results.append(
                    {
                        "service_name": r.service_name,
                        "score": r.score,
                        "grade": r.grade.value,
                        "dimension": r.dimension.value,
                    }
                )
        results.sort(key=lambda x: x["score"])
        return results

    def rank_by_readiness_score(self) -> list[dict[str, Any]]:
        """Rank all assessments by score descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "service_name": r.service_name,
                    "score": r.score,
                    "grade": r.grade.value,
                    "dimension": r.dimension.value,
                }
            )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def detect_dimension_weaknesses(self) -> list[dict[str, Any]]:
        """Detect assessments with INSUFFICIENT or FAILING grades."""
        weak_grades = {ReadinessGrade.INSUFFICIENT, ReadinessGrade.FAILING}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.grade in weak_grades:
                results.append(
                    {
                        "service_name": r.service_name,
                        "dimension": r.dimension.value,
                        "grade": r.grade.value,
                        "score": r.score,
                    }
                )
        return results

    # -- report / stats ------------------------------------------------------

    def generate_report(self) -> ReadinessReport:
        by_dimension: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.dimension.value] = by_dimension.get(r.dimension.value, 0) + 1
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
        total = len(self._records)
        avg_score = round(sum(r.score for r in self._records) / total, 2) if total else 0.0
        failing_count = sum(1 for r in self._records if r.score < self._min_readiness_score)
        recs: list[str] = []
        if failing_count > 0:
            recs.append(
                f"{failing_count} assessment(s) below "
                f"{self._min_readiness_score} readiness threshold"
            )
        weak = sum(
            1
            for r in self._records
            if r.grade in {ReadinessGrade.INSUFFICIENT, ReadinessGrade.FAILING}
        )
        if weak > 0:
            recs.append(f"{weak} assessment(s) with insufficient or failing grades")
        if not recs:
            recs.append("Operational readiness meets targets")
        return ReadinessReport(
            total_assessments=total,
            total_gaps=len(self._gaps),
            avg_score=avg_score,
            by_dimension=by_dimension,
            by_grade=by_grade,
            failing_count=failing_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._gaps.clear()
        logger.info("readiness_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dimension_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dimension.value
            dimension_dist[key] = dimension_dist.get(key, 0) + 1
        return {
            "total_assessments": len(self._records),
            "total_gaps": len(self._gaps),
            "min_readiness_score": self._min_readiness_score,
            "dimension_distribution": dimension_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
