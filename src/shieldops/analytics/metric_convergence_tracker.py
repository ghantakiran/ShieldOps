"""Metric Convergence Tracker

Track metric convergence patterns, compute convergence
rates, and predict final metric values.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ConvergencePattern(StrEnum):
    MONOTONIC = "monotonic"
    OSCILLATING = "oscillating"
    STEP_WISE = "step_wise"
    ASYMPTOTIC = "asymptotic"


class StabilityLevel(StrEnum):
    STABLE = "stable"
    UNSTABLE = "unstable"
    TRANSITIONING = "transitioning"
    CHAOTIC = "chaotic"


class MetricType(StrEnum):
    LOSS = "loss"
    ACCURACY = "accuracy"
    LATENCY = "latency"
    THROUGHPUT = "throughput"


# --- Models ---


class ConvergenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    pattern: ConvergencePattern = ConvergencePattern.MONOTONIC
    stability: StabilityLevel = StabilityLevel.STABLE
    metric_type: MetricType = MetricType.LOSS
    metric_value: float = 0.0
    iteration: int = 0
    service: str = ""
    created_at: float = Field(default_factory=time.time)


class ConvergenceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    pattern: ConvergencePattern = ConvergencePattern.MONOTONIC
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConvergenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    stable_count: int = 0
    avg_metric: float = 0.0
    by_pattern: dict[str, int] = Field(default_factory=dict)
    by_stability: dict[str, int] = Field(default_factory=dict)
    by_metric_type: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetricConvergenceTracker:
    """Track metric convergence, compute rates,
    and predict final metric values.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ConvergenceRecord] = []
        self._analyses: dict[str, ConvergenceAnalysis] = {}
        logger.info(
            "metric_convergence_tracker.initialized",
            max_records=max_records,
        )

    def add_record(
        self,
        experiment_id: str = "",
        pattern: ConvergencePattern = (ConvergencePattern.MONOTONIC),
        stability: StabilityLevel = (StabilityLevel.STABLE),
        metric_type: MetricType = MetricType.LOSS,
        metric_value: float = 0.0,
        iteration: int = 0,
        service: str = "",
    ) -> ConvergenceRecord:
        record = ConvergenceRecord(
            experiment_id=experiment_id,
            pattern=pattern,
            stability=stability,
            metric_type=metric_type,
            metric_value=metric_value,
            iteration=iteration,
            service=service,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "metric_convergence_tracker.record_added",
            record_id=record.id,
            experiment_id=experiment_id,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        analysis = ConvergenceAnalysis(
            experiment_id=rec.experiment_id,
            pattern=rec.pattern,
            analysis_score=rec.metric_value,
            description=(f"Convergence {rec.experiment_id} iter={rec.iteration}"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "score": analysis.analysis_score,
        }

    def generate_report(self) -> ConvergenceReport:
        by_pat: dict[str, int] = {}
        by_stab: dict[str, int] = {}
        by_mt: dict[str, int] = {}
        stable = 0
        metrics: list[float] = []
        for r in self._records:
            p = r.pattern.value
            by_pat[p] = by_pat.get(p, 0) + 1
            s = r.stability.value
            by_stab[s] = by_stab.get(s, 0) + 1
            m = r.metric_type.value
            by_mt[m] = by_mt.get(m, 0) + 1
            if r.stability == StabilityLevel.STABLE:
                stable += 1
            metrics.append(r.metric_value)
        avg = round(sum(metrics) / len(metrics), 4) if metrics else 0.0
        recs: list[str] = []
        chaotic = by_stab.get("chaotic", 0)
        total = len(self._records)
        if total > 0 and chaotic / total > 0.2:
            recs.append("High chaotic rate — review training stability")
        if not recs:
            recs.append("Convergence tracking is healthy")
        return ConvergenceReport(
            total_records=total,
            total_analyses=len(self._analyses),
            stable_count=stable,
            avg_metric=avg,
            by_pattern=by_pat,
            by_stability=by_stab,
            by_metric_type=by_mt,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        pat_dist: dict[str, int] = {}
        for r in self._records:
            k = r.pattern.value
            pat_dist[k] = pat_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "pattern_distribution": pat_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("metric_convergence_tracker.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def detect_convergence_point(self, experiment_id: str) -> dict[str, Any]:
        """Detect convergence point for experiment."""
        matching = [r for r in self._records if r.experiment_id == experiment_id]
        if not matching:
            return {
                "experiment_id": experiment_id,
                "status": "no_data",
            }
        sorted_recs = sorted(matching, key=lambda r: r.iteration)
        for i in range(1, len(sorted_recs)):
            delta = abs(sorted_recs[i].metric_value - sorted_recs[i - 1].metric_value)
            if delta < 0.001:
                return {
                    "experiment_id": experiment_id,
                    "converged_at": (sorted_recs[i].iteration),
                    "final_value": (sorted_recs[i].metric_value),
                }
        return {
            "experiment_id": experiment_id,
            "status": "not_converged",
        }

    def compute_convergence_rate(self, experiment_id: str) -> dict[str, Any]:
        """Compute convergence rate."""
        matching = [r for r in self._records if r.experiment_id == experiment_id]
        if not matching:
            return {
                "experiment_id": experiment_id,
                "status": "no_data",
            }
        sorted_recs = sorted(matching, key=lambda r: r.iteration)
        if len(sorted_recs) < 2:
            return {
                "experiment_id": experiment_id,
                "status": "insufficient_data",
            }
        deltas = [
            abs(sorted_recs[i].metric_value - sorted_recs[i - 1].metric_value)
            for i in range(1, len(sorted_recs))
        ]
        avg_rate = round(sum(deltas) / len(deltas), 4)
        return {
            "experiment_id": experiment_id,
            "avg_rate": avg_rate,
            "sample_count": len(deltas),
        }

    def predict_final_metric(self, experiment_id: str) -> dict[str, Any]:
        """Predict the final metric value."""
        matching = [r for r in self._records if r.experiment_id == experiment_id]
        if not matching:
            return {
                "experiment_id": experiment_id,
                "status": "no_data",
            }
        sorted_recs = sorted(matching, key=lambda r: r.iteration)
        last = sorted_recs[-1]
        if len(sorted_recs) < 2:
            return {
                "experiment_id": experiment_id,
                "predicted_value": last.metric_value,
            }
        recent = sorted_recs[-3:]
        avg_recent = sum(r.metric_value for r in recent) / len(recent)
        return {
            "experiment_id": experiment_id,
            "predicted_value": round(avg_recent, 4),
            "last_iteration": last.iteration,
        }
