"""Operational Hygiene Scorer — score operational hygiene across services and dimensions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HygieneDimension(StrEnum):
    RUNBOOK_FRESHNESS = "runbook_freshness"
    ALERT_COVERAGE = "alert_coverage"
    DOCUMENTATION = "documentation"
    ONCALL_HEALTH = "oncall_health"
    CONFIG_DRIFT = "config_drift"


class HygieneGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    CRITICAL = "critical"


class RemediationPriority(StrEnum):
    IMMEDIATE = "immediate"
    THIS_SPRINT = "this_sprint"
    NEXT_SPRINT = "next_sprint"
    QUARTERLY = "quarterly"
    BACKLOG = "backlog"


# --- Models ---


class HygieneRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    hygiene_dimension: HygieneDimension = HygieneDimension.RUNBOOK_FRESHNESS
    hygiene_grade: HygieneGrade = HygieneGrade.EXCELLENT
    remediation_priority: RemediationPriority = RemediationPriority.IMMEDIATE
    hygiene_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class HygieneAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    hygiene_dimension: HygieneDimension = HygieneDimension.RUNBOOK_FRESHNESS
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OperationalHygieneReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    poor_hygiene_count: int = 0
    avg_hygiene_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    top_poor_hygiene: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class OperationalHygieneScorer:
    """Score operational hygiene across services and dimensions."""

    def __init__(
        self,
        max_records: int = 200000,
        min_hygiene_score: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_hygiene_score = min_hygiene_score
        self._records: list[HygieneRecord] = []
        self._assessments: list[HygieneAssessment] = []
        logger.info(
            "operational_hygiene_scorer.initialized",
            max_records=max_records,
            min_hygiene_score=min_hygiene_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_hygiene(
        self,
        service_name: str,
        hygiene_dimension: HygieneDimension = HygieneDimension.RUNBOOK_FRESHNESS,
        hygiene_grade: HygieneGrade = HygieneGrade.EXCELLENT,
        remediation_priority: RemediationPriority = RemediationPriority.IMMEDIATE,
        hygiene_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> HygieneRecord:
        record = HygieneRecord(
            service_name=service_name,
            hygiene_dimension=hygiene_dimension,
            hygiene_grade=hygiene_grade,
            remediation_priority=remediation_priority,
            hygiene_score=hygiene_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "operational_hygiene_scorer.hygiene_recorded",
            record_id=record.id,
            service_name=service_name,
            hygiene_dimension=hygiene_dimension.value,
            hygiene_grade=hygiene_grade.value,
        )
        return record

    def get_hygiene(self, record_id: str) -> HygieneRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_hygiene_records(
        self,
        hygiene_dimension: HygieneDimension | None = None,
        hygiene_grade: HygieneGrade | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[HygieneRecord]:
        results = list(self._records)
        if hygiene_dimension is not None:
            results = [r for r in results if r.hygiene_dimension == hygiene_dimension]
        if hygiene_grade is not None:
            results = [r for r in results if r.hygiene_grade == hygiene_grade]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        service_name: str,
        hygiene_dimension: HygieneDimension = HygieneDimension.RUNBOOK_FRESHNESS,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> HygieneAssessment:
        assessment = HygieneAssessment(
            service_name=service_name,
            hygiene_dimension=hygiene_dimension,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "operational_hygiene_scorer.assessment_added",
            service_name=service_name,
            hygiene_dimension=hygiene_dimension.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_hygiene_distribution(self) -> dict[str, Any]:
        """Group by hygiene_dimension; return count and avg hygiene_score."""
        dim_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.hygiene_dimension.value
            dim_data.setdefault(key, []).append(r.hygiene_score)
        result: dict[str, Any] = {}
        for dim, scores in dim_data.items():
            result[dim] = {
                "count": len(scores),
                "avg_hygiene_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_poor_hygiene(self) -> list[dict[str, Any]]:
        """Return records where hygiene_score < min_hygiene_score."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.hygiene_score < self._min_hygiene_score:
                results.append(
                    {
                        "record_id": r.id,
                        "service_name": r.service_name,
                        "hygiene_dimension": r.hygiene_dimension.value,
                        "hygiene_score": r.hygiene_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["hygiene_score"])

    def rank_by_hygiene(self) -> list[dict[str, Any]]:
        """Group by service, avg hygiene_score, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.hygiene_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_hygiene_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_hygiene_score"])
        return results

    def detect_hygiene_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> OperationalHygieneReport:
        by_dimension: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.hygiene_dimension.value] = (
                by_dimension.get(r.hygiene_dimension.value, 0) + 1
            )
            by_grade[r.hygiene_grade.value] = by_grade.get(r.hygiene_grade.value, 0) + 1
            by_priority[r.remediation_priority.value] = (
                by_priority.get(r.remediation_priority.value, 0) + 1
            )
        poor_hygiene_count = sum(
            1 for r in self._records if r.hygiene_score < self._min_hygiene_score
        )
        scores = [r.hygiene_score for r in self._records]
        avg_hygiene_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        poor_list = self.identify_poor_hygiene()
        top_poor_hygiene = [o["service_name"] for o in poor_list[:5]]
        recs: list[str] = []
        if self._records and poor_hygiene_count > 0:
            recs.append(
                f"{poor_hygiene_count} service(s) below hygiene threshold "
                f"({self._min_hygiene_score})"
            )
        if self._records and avg_hygiene_score < self._min_hygiene_score:
            recs.append(
                f"Avg hygiene score {avg_hygiene_score} below threshold ({self._min_hygiene_score})"
            )
        if not recs:
            recs.append("Operational hygiene levels are healthy")
        return OperationalHygieneReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            poor_hygiene_count=poor_hygiene_count,
            avg_hygiene_score=avg_hygiene_score,
            by_dimension=by_dimension,
            by_grade=by_grade,
            by_priority=by_priority,
            top_poor_hygiene=top_poor_hygiene,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("operational_hygiene_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dimension_dist: dict[str, int] = {}
        for r in self._records:
            key = r.hygiene_dimension.value
            dimension_dist[key] = dimension_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "min_hygiene_score": self._min_hygiene_score,
            "dimension_distribution": dimension_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
