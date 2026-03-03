"""Incident Recurrence Predictor — predict and prevent recurring incidents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RecurrencePattern(StrEnum):
    PERIODIC = "periodic"
    RANDOM = "random"
    TRIGGERED = "triggered"
    SEASONAL = "seasonal"
    TRENDING = "trending"


class PredictionConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"
    INSUFFICIENT_DATA = "insufficient_data"


class PreventionStrategy(StrEnum):
    ROOT_CAUSE_FIX = "root_cause_fix"
    AUTOMATION = "automation"
    MONITORING = "monitoring"
    PROCESS_CHANGE = "process_change"
    ARCHITECTURE = "architecture"


# --- Models ---


class RecurrencePrediction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recurrence_pattern: RecurrencePattern = RecurrencePattern.PERIODIC
    prediction_confidence: PredictionConfidence = PredictionConfidence.MEDIUM
    prevention_strategy: PreventionStrategy = PreventionStrategy.ROOT_CAUSE_FIX
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RecurrenceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recurrence_pattern: RecurrencePattern = RecurrencePattern.PERIODIC
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RecurrencePredictionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_pattern: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentRecurrencePredictor:
    """Predict recurring incidents and recommend prevention strategies."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[RecurrencePrediction] = []
        self._analyses: list[RecurrenceAnalysis] = []
        logger.info(
            "incident_recurrence_predictor.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_prediction(
        self,
        service: str,
        recurrence_pattern: RecurrencePattern = RecurrencePattern.PERIODIC,
        prediction_confidence: PredictionConfidence = PredictionConfidence.MEDIUM,
        prevention_strategy: PreventionStrategy = PreventionStrategy.ROOT_CAUSE_FIX,
        score: float = 0.0,
        team: str = "",
    ) -> RecurrencePrediction:
        record = RecurrencePrediction(
            recurrence_pattern=recurrence_pattern,
            prediction_confidence=prediction_confidence,
            prevention_strategy=prevention_strategy,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_recurrence_predictor.prediction_recorded",
            record_id=record.id,
            service=service,
            recurrence_pattern=recurrence_pattern.value,
            prediction_confidence=prediction_confidence.value,
        )
        return record

    def get_prediction(self, record_id: str) -> RecurrencePrediction | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_predictions(
        self,
        recurrence_pattern: RecurrencePattern | None = None,
        prediction_confidence: PredictionConfidence | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RecurrencePrediction]:
        results = list(self._records)
        if recurrence_pattern is not None:
            results = [r for r in results if r.recurrence_pattern == recurrence_pattern]
        if prediction_confidence is not None:
            results = [r for r in results if r.prediction_confidence == prediction_confidence]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        recurrence_pattern: RecurrencePattern = RecurrencePattern.PERIODIC,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RecurrenceAnalysis:
        analysis = RecurrenceAnalysis(
            recurrence_pattern=recurrence_pattern,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "incident_recurrence_predictor.analysis_added",
            recurrence_pattern=recurrence_pattern.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by recurrence_pattern; return count and avg score."""
        pattern_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.recurrence_pattern.value
            pattern_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for pattern, scores in pattern_data.items():
            result[pattern] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_recurrence_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "recurrence_pattern": r.recurrence_pattern.value,
                        "score": r.score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_score_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> RecurrencePredictionReport:
        by_pattern: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_pattern[r.recurrence_pattern.value] = (
                by_pattern.get(r.recurrence_pattern.value, 0) + 1
            )
            by_confidence[r.prediction_confidence.value] = (
                by_confidence.get(r.prediction_confidence.value, 0) + 1
            )
            by_strategy[r.prevention_strategy.value] = (
                by_strategy.get(r.prevention_strategy.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_recurrence_gaps()
        top_gaps = [o["service"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} service(s) with high recurrence risk (threshold {self._threshold})"
            )
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Incident recurrence risk is well-managed")
        return RecurrencePredictionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_pattern=by_pattern,
            by_confidence=by_confidence,
            by_strategy=by_strategy,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("incident_recurrence_predictor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        pattern_dist: dict[str, int] = {}
        for r in self._records:
            key = r.recurrence_pattern.value
            pattern_dist[key] = pattern_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "pattern_distribution": pattern_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
