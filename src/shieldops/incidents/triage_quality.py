"""Triage Quality Analyzer — assess triage accuracy, speed, and outcomes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TriageAccuracy(StrEnum):
    CORRECT = "correct"
    MOSTLY_CORRECT = "mostly_correct"
    PARTIALLY_CORRECT = "partially_correct"
    INCORRECT = "incorrect"
    UNVERIFIED = "unverified"


class TriageSpeed(StrEnum):
    IMMEDIATE = "immediate"
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    DELAYED = "delayed"


class TriageOutcome(StrEnum):
    RESOLVED_QUICKLY = "resolved_quickly"
    ESCALATED_CORRECTLY = "escalated_correctly"
    MISROUTED = "misrouted"
    DELAYED_RESOLUTION = "delayed_resolution"
    REOPENED = "reopened"


# --- Models ---


class TriageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    triage_accuracy: TriageAccuracy = TriageAccuracy.UNVERIFIED
    triage_speed: TriageSpeed = TriageSpeed.NORMAL
    triage_outcome: TriageOutcome = TriageOutcome.RESOLVED_QUICKLY
    quality_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TriageMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    triage_accuracy: TriageAccuracy = TriageAccuracy.UNVERIFIED
    quality_threshold: float = 0.0
    avg_quality_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TriageQualityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    poor_triages: int = 0
    avg_quality_score: float = 0.0
    by_accuracy: dict[str, int] = Field(default_factory=dict)
    by_speed: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TriageQualityAnalyzer:
    """Assess triage accuracy, speed, and outcomes to improve incident handling."""

    def __init__(
        self,
        max_records: int = 200000,
        min_triage_quality_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_triage_quality_pct = min_triage_quality_pct
        self._records: list[TriageRecord] = []
        self._metrics: list[TriageMetric] = []
        logger.info(
            "triage_quality.initialized",
            max_records=max_records,
            min_triage_quality_pct=min_triage_quality_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_triage(
        self,
        incident_id: str,
        triage_accuracy: TriageAccuracy = TriageAccuracy.UNVERIFIED,
        triage_speed: TriageSpeed = TriageSpeed.NORMAL,
        triage_outcome: TriageOutcome = TriageOutcome.RESOLVED_QUICKLY,
        quality_score: float = 0.0,
        team: str = "",
    ) -> TriageRecord:
        record = TriageRecord(
            incident_id=incident_id,
            triage_accuracy=triage_accuracy,
            triage_speed=triage_speed,
            triage_outcome=triage_outcome,
            quality_score=quality_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "triage_quality.triage_recorded",
            record_id=record.id,
            incident_id=incident_id,
            triage_accuracy=triage_accuracy.value,
            triage_speed=triage_speed.value,
        )
        return record

    def get_triage(self, record_id: str) -> TriageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_triages(
        self,
        accuracy: TriageAccuracy | None = None,
        speed: TriageSpeed | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TriageRecord]:
        results = list(self._records)
        if accuracy is not None:
            results = [r for r in results if r.triage_accuracy == accuracy]
        if speed is not None:
            results = [r for r in results if r.triage_speed == speed]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        metric_name: str,
        triage_accuracy: TriageAccuracy = TriageAccuracy.UNVERIFIED,
        quality_threshold: float = 0.0,
        avg_quality_score: float = 0.0,
        description: str = "",
    ) -> TriageMetric:
        metric = TriageMetric(
            metric_name=metric_name,
            triage_accuracy=triage_accuracy,
            quality_threshold=quality_threshold,
            avg_quality_score=avg_quality_score,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "triage_quality.metric_added",
            metric_name=metric_name,
            triage_accuracy=triage_accuracy.value,
            quality_threshold=quality_threshold,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_triage_accuracy(self) -> dict[str, Any]:
        """Group by accuracy; return count and avg quality score per accuracy level."""
        accuracy_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.triage_accuracy.value
            accuracy_data.setdefault(key, []).append(r.quality_score)
        result: dict[str, Any] = {}
        for accuracy, scores in accuracy_data.items():
            result[accuracy] = {
                "count": len(scores),
                "avg_quality_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_poor_triages(self) -> list[dict[str, Any]]:
        """Return records where accuracy is INCORRECT or PARTIALLY_CORRECT."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.triage_accuracy in (
                TriageAccuracy.INCORRECT,
                TriageAccuracy.PARTIALLY_CORRECT,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "triage_accuracy": r.triage_accuracy.value,
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

    def detect_triage_trends(self) -> dict[str, Any]:
        """Split-half on avg_quality_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [m.avg_quality_score for m in self._metrics]
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

    def generate_report(self) -> TriageQualityReport:
        by_accuracy: dict[str, int] = {}
        by_speed: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_accuracy[r.triage_accuracy.value] = by_accuracy.get(r.triage_accuracy.value, 0) + 1
            by_speed[r.triage_speed.value] = by_speed.get(r.triage_speed.value, 0) + 1
            by_outcome[r.triage_outcome.value] = by_outcome.get(r.triage_outcome.value, 0) + 1
        poor_count = sum(
            1
            for r in self._records
            if r.triage_accuracy in (TriageAccuracy.INCORRECT, TriageAccuracy.PARTIALLY_CORRECT)
        )
        avg_score = (
            round(sum(r.quality_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_quality_score()
        top_items = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if avg_score < self._min_triage_quality_pct:
            recs.append(
                f"Avg quality score {avg_score}% is below "
                f"threshold ({self._min_triage_quality_pct}%)"
            )
        if poor_count > 0:
            recs.append(f"{poor_count} poor triage(s) detected — review accuracy")
        if not recs:
            recs.append("Triage quality is within acceptable limits")
        return TriageQualityReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            poor_triages=poor_count,
            avg_quality_score=avg_score,
            by_accuracy=by_accuracy,
            by_speed=by_speed,
            by_outcome=by_outcome,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("triage_quality.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        accuracy_dist: dict[str, int] = {}
        for r in self._records:
            key = r.triage_accuracy.value
            accuracy_dist[key] = accuracy_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_triage_quality_pct": self._min_triage_quality_pct,
            "accuracy_distribution": accuracy_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
