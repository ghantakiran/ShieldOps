"""Model Fairness Scorer — evaluate and score ML model fairness metrics."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FairnessMetric(StrEnum):
    DEMOGRAPHIC_PARITY = "demographic_parity"
    EQUALIZED_ODDS = "equalized_odds"
    EQUAL_OPPORTUNITY = "equal_opportunity"
    CALIBRATION = "calibration"
    PREDICTIVE_PARITY = "predictive_parity"


class ProtectedAttribute(StrEnum):
    GENDER = "gender"
    RACE = "race"
    AGE = "age"
    DISABILITY = "disability"
    RELIGION = "religion"


class FairnessLevel(StrEnum):
    EXCELLENT = "excellent"
    ACCEPTABLE = "acceptable"
    MARGINAL = "marginal"
    POOR = "poor"
    FAILING = "failing"


# --- Models ---


class FairnessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    fairness_metric: FairnessMetric = FairnessMetric.DEMOGRAPHIC_PARITY
    protected_attribute: ProtectedAttribute = ProtectedAttribute.GENDER
    fairness_level: FairnessLevel = FairnessLevel.ACCEPTABLE
    fairness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FairnessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    fairness_metric: FairnessMetric = FairnessMetric.DEMOGRAPHIC_PARITY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FairnessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    failing_count: int = 0
    avg_fairness_score: float = 0.0
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_attribute: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    top_violations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ModelFairnessScorer:
    """Evaluate and score ML model fairness metrics."""

    def __init__(
        self,
        max_records: int = 200000,
        fairness_threshold: float = 0.8,
    ) -> None:
        self._max_records = max_records
        self._fairness_threshold = fairness_threshold
        self._records: list[FairnessRecord] = []
        self._analyses: list[FairnessAnalysis] = []
        logger.info(
            "model_fairness_scorer.initialized",
            max_records=max_records,
            fairness_threshold=fairness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_fairness(
        self,
        model_id: str,
        fairness_metric: FairnessMetric = FairnessMetric.DEMOGRAPHIC_PARITY,
        protected_attribute: ProtectedAttribute = ProtectedAttribute.GENDER,
        fairness_level: FairnessLevel = FairnessLevel.ACCEPTABLE,
        fairness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FairnessRecord:
        record = FairnessRecord(
            model_id=model_id,
            fairness_metric=fairness_metric,
            protected_attribute=protected_attribute,
            fairness_level=fairness_level,
            fairness_score=fairness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "model_fairness_scorer.fairness_recorded",
            record_id=record.id,
            model_id=model_id,
            fairness_metric=fairness_metric.value,
        )
        return record

    def get_fairness(self, record_id: str) -> FairnessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_fairness(
        self,
        fairness_metric: FairnessMetric | None = None,
        fairness_level: FairnessLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FairnessRecord]:
        results = list(self._records)
        if fairness_metric is not None:
            results = [r for r in results if r.fairness_metric == fairness_metric]
        if fairness_level is not None:
            results = [r for r in results if r.fairness_level == fairness_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        model_id: str,
        fairness_metric: FairnessMetric = FairnessMetric.DEMOGRAPHIC_PARITY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FairnessAnalysis:
        analysis = FairnessAnalysis(
            model_id=model_id,
            fairness_metric=fairness_metric,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "model_fairness_scorer.analysis_added",
            model_id=model_id,
            fairness_metric=fairness_metric.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by fairness_metric; return count and avg fairness_score."""
        metric_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.fairness_metric.value
            metric_data.setdefault(key, []).append(r.fairness_score)
        result: dict[str, Any] = {}
        for metric, scores in metric_data.items():
            result[metric] = {
                "count": len(scores),
                "avg_fairness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_severe_drifts(self) -> list[dict[str, Any]]:
        """Return records where fairness_score < fairness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.fairness_score < self._fairness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "model_id": r.model_id,
                        "fairness_metric": r.fairness_metric.value,
                        "fairness_score": r.fairness_score,
                        "protected_attribute": r.protected_attribute.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["fairness_score"])

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by model_id, avg fairness_score, sort ascending (lowest first)."""
        model_scores: dict[str, list[float]] = {}
        for r in self._records:
            model_scores.setdefault(r.model_id, []).append(r.fairness_score)
        results: list[dict[str, Any]] = []
        for model_id, scores in model_scores.items():
            results.append(
                {
                    "model_id": model_id,
                    "avg_fairness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_fairness_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> FairnessReport:
        by_metric: dict[str, int] = {}
        by_attribute: dict[str, int] = {}
        by_level: dict[str, int] = {}
        for r in self._records:
            by_metric[r.fairness_metric.value] = by_metric.get(r.fairness_metric.value, 0) + 1
            by_attribute[r.protected_attribute.value] = (
                by_attribute.get(r.protected_attribute.value, 0) + 1
            )
            by_level[r.fairness_level.value] = by_level.get(r.fairness_level.value, 0) + 1
        failing_count = sum(1 for r in self._records if r.fairness_score < self._fairness_threshold)
        scores = [r.fairness_score for r in self._records]
        avg_fairness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        violations = self.identify_severe_drifts()
        top_violations = [o["model_id"] for o in violations[:5]]
        recs: list[str] = []
        if self._records and failing_count > 0:
            recs.append(
                f"{failing_count} model(s) below fairness threshold ({self._fairness_threshold})"
            )
        if self._records and avg_fairness_score < self._fairness_threshold:
            recs.append(
                f"Avg fairness score {avg_fairness_score} below threshold "
                f"({self._fairness_threshold})"
            )
        if not recs:
            recs.append("Model fairness is within acceptable bounds")
        return FairnessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            failing_count=failing_count,
            avg_fairness_score=avg_fairness_score,
            by_metric=by_metric,
            by_attribute=by_attribute,
            by_level=by_level,
            top_violations=top_violations,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("model_fairness_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        metric_dist: dict[str, int] = {}
        for r in self._records:
            key = r.fairness_metric.value
            metric_dist[key] = metric_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "fairness_threshold": self._fairness_threshold,
            "metric_distribution": metric_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_models": len({r.model_id for r in self._records}),
        }
