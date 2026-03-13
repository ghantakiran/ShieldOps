"""Meta-Learning Hyperselection Engine —
meta-learn optimal hyperparameters, evaluate search strategies,
and rank configurations for agent performance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SearchStrategy(StrEnum):
    GRID = "grid"
    RANDOM = "random"
    BAYESIAN = "bayesian"
    EVOLUTIONARY = "evolutionary"


class HyperparamType(StrEnum):
    LEARNING_RATE = "learning_rate"
    BATCH_SIZE = "batch_size"
    ARCHITECTURE = "architecture"
    REGULARIZATION = "regularization"


class SelectionOutcome(StrEnum):
    IMPROVED = "improved"
    UNCHANGED = "unchanged"
    DEGRADED = "degraded"
    FAILED = "failed"


# --- Models ---


class HyperselectionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    search_strategy: SearchStrategy = SearchStrategy.BAYESIAN
    hyperparam_type: HyperparamType = HyperparamType.LEARNING_RATE
    outcome: SelectionOutcome = SelectionOutcome.IMPROVED
    performance_score: float = 0.0
    iterations_used: int = 0
    search_budget: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class HyperselectionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    avg_performance: float = 0.0
    best_strategy: SearchStrategy = SearchStrategy.BAYESIAN
    dominant_outcome: SelectionOutcome = SelectionOutcome.IMPROVED
    config_count: int = 0
    efficiency_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class HyperselectionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_performance_score: float = 0.0
    by_search_strategy: dict[str, int] = Field(default_factory=dict)
    by_hyperparam_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    top_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetaLearningHyperselectionEngine:
    """Meta-learn optimal hyperparameters, evaluate search
    strategies, and rank configurations for agent optimization."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[HyperselectionRecord] = []
        self._analyses: dict[str, HyperselectionAnalysis] = {}
        logger.info(
            "meta_learning_hyperselection.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        search_strategy: SearchStrategy = SearchStrategy.BAYESIAN,
        hyperparam_type: HyperparamType = HyperparamType.LEARNING_RATE,
        outcome: SelectionOutcome = SelectionOutcome.IMPROVED,
        performance_score: float = 0.0,
        iterations_used: int = 0,
        search_budget: float = 0.0,
        description: str = "",
    ) -> HyperselectionRecord:
        record = HyperselectionRecord(
            agent_id=agent_id,
            search_strategy=search_strategy,
            hyperparam_type=hyperparam_type,
            outcome=outcome,
            performance_score=performance_score,
            iterations_used=iterations_used,
            search_budget=search_budget,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "hyperselection.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> HyperselectionAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        agent_recs = [r for r in self._records if r.agent_id == rec.agent_id]
        scores = [r.performance_score for r in agent_recs]
        avg_perf = round(sum(scores) / len(scores), 2) if scores else 0.0
        strategy_scores: dict[str, list[float]] = {}
        for r in agent_recs:
            strategy_scores.setdefault(r.search_strategy.value, []).append(r.performance_score)
        best_strategy_val = (
            max(
                strategy_scores,
                key=lambda x: sum(strategy_scores[x]) / len(strategy_scores[x]),
            )
            if strategy_scores
            else SearchStrategy.BAYESIAN.value
        )
        best_strategy = SearchStrategy(best_strategy_val)
        outcome_counts: dict[str, int] = {}
        for r in agent_recs:
            outcome_counts[r.outcome.value] = outcome_counts.get(r.outcome.value, 0) + 1
        dominant_outcome = (
            SelectionOutcome(max(outcome_counts, key=lambda x: outcome_counts[x]))
            if outcome_counts
            else SelectionOutcome.IMPROVED
        )
        iters = [r.iterations_used for r in agent_recs if r.iterations_used > 0]
        avg_iter = sum(iters) / len(iters) if iters else 1.0
        efficiency = round(avg_perf / max(avg_iter, 1) * 100, 2)
        analysis = HyperselectionAnalysis(
            agent_id=rec.agent_id,
            avg_performance=avg_perf,
            best_strategy=best_strategy,
            dominant_outcome=dominant_outcome,
            config_count=len(agent_recs),
            efficiency_score=efficiency,
            description=f"Agent {rec.agent_id} best strategy {best_strategy.value}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> HyperselectionReport:
        by_ss: dict[str, int] = {}
        by_ht: dict[str, int] = {}
        by_oc: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            by_ss[r.search_strategy.value] = by_ss.get(r.search_strategy.value, 0) + 1
            by_ht[r.hyperparam_type.value] = by_ht.get(r.hyperparam_type.value, 0) + 1
            by_oc[r.outcome.value] = by_oc.get(r.outcome.value, 0) + 1
            scores.append(r.performance_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        agent_totals: dict[str, float] = {}
        for r in self._records:
            agent_totals[r.agent_id] = agent_totals.get(r.agent_id, 0.0) + r.performance_score
        ranked = sorted(
            agent_totals,
            key=lambda x: agent_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        failed = by_oc.get("failed", 0)
        if failed > 0:
            recs.append(f"{failed} failed hyperparameter searches — check budget")
        degraded = by_oc.get("degraded", 0)
        if degraded > 0:
            recs.append(f"{degraded} degraded outcomes — switch to Bayesian search")
        if not recs:
            recs.append("Hyperparameter search outcomes are healthy")
        return HyperselectionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_performance_score=avg,
            by_search_strategy=by_ss,
            by_hyperparam_type=by_ht,
            by_outcome=by_oc,
            top_agents=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            dist[r.search_strategy.value] = dist.get(r.search_strategy.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "search_strategy_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("meta_learning_hyperselection.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def evaluate_search_strategies(self) -> list[dict[str, Any]]:
        """Evaluate effectiveness of each hyperparameter search strategy."""
        strategy_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            entry = strategy_data.setdefault(
                r.search_strategy.value,
                {"scores": [], "iters": [], "budgets": []},
            )
            entry["scores"].append(r.performance_score)
            entry["iters"].append(r.iterations_used)
            entry["budgets"].append(r.search_budget)
        results: list[dict[str, Any]] = []
        for strategy, data in strategy_data.items():
            avg_score = (
                round(sum(data["scores"]) / len(data["scores"]), 2) if data["scores"] else 0.0
            )
            avg_iters = round(sum(data["iters"]) / len(data["iters"]), 1) if data["iters"] else 1.0
            avg_budget = (
                round(sum(data["budgets"]) / len(data["budgets"]), 2) if data["budgets"] else 1.0
            )
            efficiency = round(avg_score / max(avg_budget, 0.01), 2)
            results.append(
                {
                    "strategy": strategy,
                    "avg_performance": avg_score,
                    "avg_iterations": avg_iters,
                    "avg_budget": avg_budget,
                    "efficiency": efficiency,
                    "sample_count": len(data["scores"]),
                }
            )
        results.sort(key=lambda x: x["efficiency"], reverse=True)
        return results

    def rank_hyperparameter_configs(self) -> list[dict[str, Any]]:
        """Rank hyperparameter types by their performance impact."""
        hp_data: dict[str, list[float]] = {}
        for r in self._records:
            hp_data.setdefault(r.hyperparam_type.value, []).append(r.performance_score)
        results: list[dict[str, Any]] = []
        for hp_type, scores in hp_data.items():
            avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
            max_s = round(max(scores), 2) if scores else 0.0
            results.append(
                {
                    "hyperparam_type": hp_type,
                    "avg_performance": avg_s,
                    "max_performance": max_s,
                    "sample_count": len(scores),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_performance"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results

    def optimize_meta_learning_schedule(self) -> list[dict[str, Any]]:
        """Optimize the meta-learning schedule per agent."""
        agent_data: dict[str, list[HyperselectionRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for aid, recs in agent_data.items():
            scores = [r.performance_score for r in recs]
            iters = [r.iterations_used for r in recs]
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
            total_iters = sum(iters)
            improved_count = sum(1 for r in recs if r.outcome == SelectionOutcome.IMPROVED)
            improvement_rate = round(improved_count / len(recs), 2) if recs else 0.0
            schedule_quality = round(avg_score * 0.6 + improvement_rate * 0.4, 2)
            needs_rerun = schedule_quality < 0.5
            results.append(
                {
                    "agent_id": aid,
                    "avg_performance": avg_score,
                    "total_iterations": total_iters,
                    "improvement_rate": improvement_rate,
                    "schedule_quality": schedule_quality,
                    "needs_rerun": needs_rerun,
                    "config_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["schedule_quality"], reverse=True)
        return results
