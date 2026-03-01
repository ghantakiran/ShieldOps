"""Operational Readiness Scorer — score operational readiness across services and teams."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReadinessCategory(StrEnum):
    MONITORING = "monitoring"
    ALERTING = "alerting"
    RUNBOOKS = "runbooks"
    INCIDENT_RESPONSE = "incident_response"
    CAPACITY_PLANNING = "capacity_planning"


class ReadinessGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    FAILING = "failing"


class ReadinessMaturity(StrEnum):
    ADVANCED = "advanced"
    MATURE = "mature"
    DEVELOPING = "developing"
    BASIC = "basic"
    NONE = "none"


# --- Models ---


class ReadinessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_id: str = ""
    readiness_category: ReadinessCategory = ReadinessCategory.MONITORING
    readiness_grade: ReadinessGrade = ReadinessGrade.ADEQUATE
    readiness_maturity: ReadinessMaturity = ReadinessMaturity.BASIC
    readiness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ReadinessCheckpoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_id: str = ""
    readiness_category: ReadinessCategory = ReadinessCategory.MONITORING
    checkpoint_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OperationalReadinessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_checkpoints: int = 0
    failing_count: int = 0
    avg_readiness_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    by_maturity: dict[str, int] = Field(default_factory=dict)
    top_failing: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class OperationalReadinessScorer:
    """Score operational readiness across services and teams."""

    def __init__(
        self,
        max_records: int = 200000,
        min_readiness_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_readiness_score = min_readiness_score
        self._records: list[ReadinessRecord] = []
        self._checkpoints: list[ReadinessCheckpoint] = []
        logger.info(
            "operational_readiness.initialized",
            max_records=max_records,
            min_readiness_score=min_readiness_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_readiness(
        self,
        assessment_id: str,
        readiness_category: ReadinessCategory = ReadinessCategory.MONITORING,
        readiness_grade: ReadinessGrade = ReadinessGrade.ADEQUATE,
        readiness_maturity: ReadinessMaturity = ReadinessMaturity.BASIC,
        readiness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ReadinessRecord:
        record = ReadinessRecord(
            assessment_id=assessment_id,
            readiness_category=readiness_category,
            readiness_grade=readiness_grade,
            readiness_maturity=readiness_maturity,
            readiness_score=readiness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "operational_readiness.readiness_recorded",
            record_id=record.id,
            assessment_id=assessment_id,
            readiness_category=readiness_category.value,
            readiness_grade=readiness_grade.value,
        )
        return record

    def get_readiness(self, record_id: str) -> ReadinessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_readiness(
        self,
        category: ReadinessCategory | None = None,
        grade: ReadinessGrade | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ReadinessRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.readiness_category == category]
        if grade is not None:
            results = [r for r in results if r.readiness_grade == grade]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_checkpoint(
        self,
        assessment_id: str,
        readiness_category: ReadinessCategory = ReadinessCategory.MONITORING,
        checkpoint_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ReadinessCheckpoint:
        checkpoint = ReadinessCheckpoint(
            assessment_id=assessment_id,
            readiness_category=readiness_category,
            checkpoint_score=checkpoint_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._checkpoints.append(checkpoint)
        if len(self._checkpoints) > self._max_records:
            self._checkpoints = self._checkpoints[-self._max_records :]
        logger.info(
            "operational_readiness.checkpoint_added",
            assessment_id=assessment_id,
            readiness_category=readiness_category.value,
            checkpoint_score=checkpoint_score,
        )
        return checkpoint

    # -- domain operations --------------------------------------------------

    def analyze_readiness_distribution(self) -> dict[str, Any]:
        """Group by readiness_category; return count and avg readiness_score per category."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.readiness_category.value
            cat_data.setdefault(key, []).append(r.readiness_score)
        result: dict[str, Any] = {}
        for category, scores in cat_data.items():
            result[category] = {
                "count": len(scores),
                "avg_readiness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_failing_services(self) -> list[dict[str, Any]]:
        """Return records where readiness_grade is FAILING."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.readiness_grade == ReadinessGrade.FAILING:
                results.append(
                    {
                        "record_id": r.id,
                        "assessment_id": r.assessment_id,
                        "readiness_category": r.readiness_category.value,
                        "readiness_score": r.readiness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_readiness_score(self) -> list[dict[str, Any]]:
        """Group by service, avg readiness_score, sort ascending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.readiness_score)
        results: list[dict[str, Any]] = []
        for service, scores in svc_scores.items():
            results.append(
                {
                    "service": service,
                    "avg_readiness_score": round(sum(scores) / len(scores), 2),
                    "readiness_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_readiness_score"])
        return results

    def detect_readiness_trends(self) -> dict[str, Any]:
        """Split-half comparison on checkpoint_score; delta threshold 5.0."""
        if len(self._checkpoints) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [c.checkpoint_score for c in self._checkpoints]
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

    def generate_report(self) -> OperationalReadinessReport:
        by_category: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        by_maturity: dict[str, int] = {}
        for r in self._records:
            by_category[r.readiness_category.value] = (
                by_category.get(r.readiness_category.value, 0) + 1
            )
            by_grade[r.readiness_grade.value] = by_grade.get(r.readiness_grade.value, 0) + 1
            by_maturity[r.readiness_maturity.value] = (
                by_maturity.get(r.readiness_maturity.value, 0) + 1
            )
        failing_count = sum(1 for r in self._records if r.readiness_grade == ReadinessGrade.FAILING)
        avg_readiness_score = (
            round(
                sum(r.readiness_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        rankings = self.rank_by_readiness_score()
        top_failing = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if failing_count > 0:
            recs.append(
                f"{failing_count} failing service(s) detected — review operational readiness"
            )
        if avg_readiness_score < self._min_readiness_score and self._records:
            recs.append(
                f"Average readiness score {avg_readiness_score} is below "
                f"threshold ({self._min_readiness_score})"
            )
        if not recs:
            recs.append("Operational readiness levels are acceptable")
        return OperationalReadinessReport(
            total_records=len(self._records),
            total_checkpoints=len(self._checkpoints),
            failing_count=failing_count,
            avg_readiness_score=avg_readiness_score,
            by_category=by_category,
            by_grade=by_grade,
            by_maturity=by_maturity,
            top_failing=top_failing,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._checkpoints.clear()
        logger.info("operational_readiness.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.readiness_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_checkpoints": len(self._checkpoints),
            "min_readiness_score": self._min_readiness_score,
            "category_distribution": category_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
