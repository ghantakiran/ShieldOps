"""Agent Experiment Engine

Hypothesis-driven experiment loops for agent optimization
with single-metric evaluation and resource-managed iterations.
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


class ExperimentType(StrEnum):
    HYPERPARAMETER = "hyperparameter"
    ARCHITECTURE = "architecture"
    PROMPT = "prompt"
    STRATEGY = "strategy"


class ExperimentOutcome(StrEnum):
    IMPROVED = "improved"
    DEGRADED = "degraded"
    NEUTRAL = "neutral"
    INCONCLUSIVE = "inconclusive"


class ResourceBudget(StrEnum):
    MINIMAL = "minimal"
    STANDARD = "standard"
    EXTENDED = "extended"
    UNLIMITED = "unlimited"


# --- Models ---


class ExperimentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_name: str = ""
    experiment_type: ExperimentType = ExperimentType.HYPERPARAMETER
    outcome: ExperimentOutcome = ExperimentOutcome.INCONCLUSIVE
    resource_budget: ResourceBudget = ResourceBudget.STANDARD
    metric_value: float = 0.0
    baseline_value: float = 0.0
    agent_id: str = ""
    service: str = ""
    created_at: float = Field(default_factory=time.time)


class ExperimentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_name: str = ""
    experiment_type: ExperimentType = ExperimentType.HYPERPARAMETER
    analysis_score: float = 0.0
    metric_delta: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ExperimentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    improved_count: int = 0
    avg_metric_delta: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_budget: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentExperimentEngine:
    """Hypothesis-driven experiment loops for agent
    optimization with single-metric evaluation.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ExperimentRecord] = []
        self._analyses: dict[str, ExperimentAnalysis] = {}
        logger.info(
            "agent_experiment_engine.initialized",
            max_records=max_records,
        )

    def add_record(
        self,
        experiment_name: str = "",
        experiment_type: ExperimentType = (ExperimentType.HYPERPARAMETER),
        outcome: ExperimentOutcome = (ExperimentOutcome.INCONCLUSIVE),
        resource_budget: ResourceBudget = (ResourceBudget.STANDARD),
        metric_value: float = 0.0,
        baseline_value: float = 0.0,
        agent_id: str = "",
        service: str = "",
    ) -> ExperimentRecord:
        record = ExperimentRecord(
            experiment_name=experiment_name,
            experiment_type=experiment_type,
            outcome=outcome,
            resource_budget=resource_budget,
            metric_value=metric_value,
            baseline_value=baseline_value,
            agent_id=agent_id,
            service=service,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "agent_experiment_engine.record_added",
            record_id=record.id,
            experiment_name=experiment_name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        delta = rec.metric_value - rec.baseline_value
        analysis = ExperimentAnalysis(
            experiment_name=rec.experiment_name,
            experiment_type=rec.experiment_type,
            analysis_score=rec.metric_value,
            metric_delta=round(delta, 4),
            description=(f"Experiment {rec.experiment_name} delta={delta:.4f}"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "metric_delta": analysis.metric_delta,
        }

    def generate_report(self) -> ExperimentReport:
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        by_budget: dict[str, int] = {}
        improved = 0
        deltas: list[float] = []
        for r in self._records:
            t = r.experiment_type.value
            by_type[t] = by_type.get(t, 0) + 1
            o = r.outcome.value
            by_outcome[o] = by_outcome.get(o, 0) + 1
            b = r.resource_budget.value
            by_budget[b] = by_budget.get(b, 0) + 1
            if r.outcome == ExperimentOutcome.IMPROVED:
                improved += 1
            deltas.append(r.metric_value - r.baseline_value)
        avg_delta = round(sum(deltas) / len(deltas), 4) if deltas else 0.0
        recs: list[str] = []
        total = len(self._records)
        if total > 0 and improved / total < 0.2:
            recs.append("Low improvement rate — refine hypothesis generation")
        if avg_delta < 0:
            recs.append("Negative avg delta — review experiment design")
        if not recs:
            recs.append("Experiment pipeline performing nominally")
        return ExperimentReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            improved_count=improved,
            avg_metric_delta=avg_delta,
            by_type=by_type,
            by_outcome=by_outcome,
            by_budget=by_budget,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            k = r.experiment_type.value
            type_dist[k] = type_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "type_distribution": type_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("agent_experiment_engine.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def run_experiment_cycle(self, agent_id: str) -> list[dict[str, Any]]:
        """Run full experiment cycle for an agent."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return []
        results = []
        for r in matching:
            delta = r.metric_value - r.baseline_value
            results.append(
                {
                    "experiment_name": r.experiment_name,
                    "outcome": r.outcome.value,
                    "metric_delta": round(delta, 4),
                }
            )
        return results

    def evaluate_metric_delta(self, experiment_name: str) -> dict[str, Any]:
        """Evaluate metric delta for an experiment."""
        matching = [r for r in self._records if r.experiment_name == experiment_name]
        if not matching:
            return {
                "experiment_name": experiment_name,
                "status": "no_data",
            }
        deltas = [r.metric_value - r.baseline_value for r in matching]
        avg = round(sum(deltas) / len(deltas), 4)
        return {
            "experiment_name": experiment_name,
            "avg_delta": avg,
            "sample_count": len(matching),
        }

    def select_next_hypothesis(self, agent_id: str) -> dict[str, Any]:
        """Select next hypothesis based on past results."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return {
                "agent_id": agent_id,
                "status": "no_history",
            }
        type_perf: dict[str, list[float]] = {}
        for r in matching:
            t = r.experiment_type.value
            if t not in type_perf:
                type_perf[t] = []
            delta = r.metric_value - r.baseline_value
            type_perf[t].append(delta)
        best_type = max(
            type_perf,
            key=lambda k: sum(type_perf[k]) / len(type_perf[k]),
        )
        return {
            "agent_id": agent_id,
            "recommended_type": best_type,
            "avg_delta": round(
                sum(type_perf[best_type]) / len(type_perf[best_type]),
                4,
            ),
        }
