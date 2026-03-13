"""Model Self-Tuning Engine

Automated model hyperparameter optimization with
convergence detection and overfitting prevention.
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


class TuningDimension(StrEnum):
    LEARNING_RATE = "learning_rate"
    BATCH_SIZE = "batch_size"
    TEMPERATURE = "temperature"
    TOP_P = "top_p"


class TuningStrategy(StrEnum):
    GRID_SEARCH = "grid_search"
    BAYESIAN = "bayesian"
    RANDOM = "random"
    ADAPTIVE = "adaptive"


class ConvergenceStatus(StrEnum):
    CONVERGING = "converging"
    OSCILLATING = "oscillating"
    DIVERGING = "diverging"
    CONVERGED = "converged"


# --- Models ---


class TuningRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    dimension: TuningDimension = TuningDimension.LEARNING_RATE
    strategy: TuningStrategy = TuningStrategy.BAYESIAN
    convergence: ConvergenceStatus = ConvergenceStatus.CONVERGING
    metric_value: float = 0.0
    param_value: float = 0.0
    iteration: int = 0
    service: str = ""
    created_at: float = Field(default_factory=time.time)


class TuningAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    dimension: TuningDimension = TuningDimension.LEARNING_RATE
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TuningReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    converged_count: int = 0
    avg_metric: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_convergence: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ModelSelfTuningEngine:
    """Automated model hyperparameter optimization
    with convergence detection.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TuningRecord] = []
        self._analyses: dict[str, TuningAnalysis] = {}
        logger.info(
            "model_self_tuning_engine.initialized",
            max_records=max_records,
        )

    def add_record(
        self,
        model_id: str = "",
        dimension: TuningDimension = (TuningDimension.LEARNING_RATE),
        strategy: TuningStrategy = (TuningStrategy.BAYESIAN),
        convergence: ConvergenceStatus = (ConvergenceStatus.CONVERGING),
        metric_value: float = 0.0,
        param_value: float = 0.0,
        iteration: int = 0,
        service: str = "",
    ) -> TuningRecord:
        record = TuningRecord(
            model_id=model_id,
            dimension=dimension,
            strategy=strategy,
            convergence=convergence,
            metric_value=metric_value,
            param_value=param_value,
            iteration=iteration,
            service=service,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "model_self_tuning_engine.record_added",
            record_id=record.id,
            model_id=model_id,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        analysis = TuningAnalysis(
            model_id=rec.model_id,
            dimension=rec.dimension,
            analysis_score=rec.metric_value,
            description=(f"Tuning {rec.dimension.value} iter={rec.iteration}"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "score": analysis.analysis_score,
        }

    def generate_report(self) -> TuningReport:
        by_dim: dict[str, int] = {}
        by_strat: dict[str, int] = {}
        by_conv: dict[str, int] = {}
        converged = 0
        metrics: list[float] = []
        for r in self._records:
            d = r.dimension.value
            by_dim[d] = by_dim.get(d, 0) + 1
            s = r.strategy.value
            by_strat[s] = by_strat.get(s, 0) + 1
            c = r.convergence.value
            by_conv[c] = by_conv.get(c, 0) + 1
            if r.convergence == ConvergenceStatus.CONVERGED:
                converged += 1
            metrics.append(r.metric_value)
        avg = round(sum(metrics) / len(metrics), 4) if metrics else 0.0
        recs: list[str] = []
        total = len(self._records)
        diverging = by_conv.get("diverging", 0)
        if total > 0 and diverging / total > 0.2:
            recs.append("High divergence rate — reduce learning rate")
        if not recs:
            recs.append("Tuning pipeline is healthy")
        return TuningReport(
            total_records=total,
            total_analyses=len(self._analyses),
            converged_count=converged,
            avg_metric=avg,
            by_dimension=by_dim,
            by_strategy=by_strat,
            by_convergence=by_conv,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dim_dist: dict[str, int] = {}
        for r in self._records:
            k = r.dimension.value
            dim_dist[k] = dim_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "dimension_distribution": dim_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("model_self_tuning_engine.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def compute_tuning_trajectory(self, model_id: str) -> list[dict[str, Any]]:
        """Compute tuning trajectory for a model."""
        matching = [r for r in self._records if r.model_id == model_id]
        if not matching:
            return []
        sorted_recs = sorted(matching, key=lambda r: r.iteration)
        return [
            {
                "iteration": r.iteration,
                "metric_value": r.metric_value,
                "param_value": r.param_value,
                "convergence": r.convergence.value,
            }
            for r in sorted_recs
        ]

    def identify_optimal_config(self, model_id: str) -> dict[str, Any]:
        """Identify optimal config for a model."""
        matching = [r for r in self._records if r.model_id == model_id]
        if not matching:
            return {
                "model_id": model_id,
                "status": "no_data",
            }
        best = max(matching, key=lambda r: r.metric_value)
        return {
            "model_id": model_id,
            "best_metric": best.metric_value,
            "best_param": best.param_value,
            "dimension": best.dimension.value,
            "iteration": best.iteration,
        }

    def detect_overfitting_risk(self, model_id: str) -> dict[str, Any]:
        """Detect overfitting risk for a model."""
        matching = [r for r in self._records if r.model_id == model_id]
        if not matching:
            return {
                "model_id": model_id,
                "status": "no_data",
            }
        sorted_recs = sorted(matching, key=lambda r: r.iteration)
        if len(sorted_recs) < 3:
            return {
                "model_id": model_id,
                "risk": "insufficient_data",
            }
        recent = sorted_recs[-3:]
        deltas = [
            recent[i + 1].metric_value - recent[i].metric_value for i in range(len(recent) - 1)
        ]
        declining = all(d < 0 for d in deltas)
        return {
            "model_id": model_id,
            "risk": "high" if declining else "low",
            "recent_deltas": [round(d, 4) for d in deltas],
        }
