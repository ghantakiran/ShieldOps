"""Self Evolution Convergence Engine —
monitors convergence of the self-evolution loop."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ConvergenceStatus(StrEnum):
    PRE_CONVERGENCE = "pre_convergence"
    APPROACHING = "approaching"
    CONVERGED = "converged"
    DIVERGING = "diverging"


class StoppingCriterion(StrEnum):
    REWARD_PLATEAU = "reward_plateau"
    ITERATION_LIMIT = "iteration_limit"
    PERFORMANCE_CEILING = "performance_ceiling"
    COST_THRESHOLD = "cost_threshold"


class ConvergenceSpeed(StrEnum):
    FAST = "fast"
    MODERATE = "moderate"
    SLOW = "slow"
    STALLED = "stalled"


# --- Models ---


class ConvergenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evolution_id: str = ""
    iteration: int = 0
    status: ConvergenceStatus = ConvergenceStatus.PRE_CONVERGENCE
    criterion: StoppingCriterion = StoppingCriterion.REWARD_PLATEAU
    speed: ConvergenceSpeed = ConvergenceSpeed.MODERATE
    reward_value: float = 0.0
    reward_delta: float = 0.0
    cost_incurred: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConvergenceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evolution_id: str = ""
    current_status: ConvergenceStatus = ConvergenceStatus.PRE_CONVERGENCE
    avg_reward: float = 0.0
    convergence_speed: ConvergenceSpeed = ConvergenceSpeed.MODERATE
    iteration_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConvergenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_reward: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_criterion: dict[str, int] = Field(default_factory=dict)
    by_speed: dict[str, int] = Field(default_factory=dict)
    converged_evolutions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SelfEvolutionConvergenceEngine:
    """Monitors convergence of the self-evolution loop."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ConvergenceRecord] = []
        self._analyses: dict[str, ConvergenceAnalysis] = {}
        logger.info(
            "self_evolution_convergence_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        evolution_id: str = "",
        iteration: int = 0,
        status: ConvergenceStatus = ConvergenceStatus.PRE_CONVERGENCE,
        criterion: StoppingCriterion = StoppingCriterion.REWARD_PLATEAU,
        speed: ConvergenceSpeed = ConvergenceSpeed.MODERATE,
        reward_value: float = 0.0,
        reward_delta: float = 0.0,
        cost_incurred: float = 0.0,
        description: str = "",
    ) -> ConvergenceRecord:
        record = ConvergenceRecord(
            evolution_id=evolution_id,
            iteration=iteration,
            status=status,
            criterion=criterion,
            speed=speed,
            reward_value=reward_value,
            reward_delta=reward_delta,
            cost_incurred=cost_incurred,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "self_evolution_convergence.record_added",
            record_id=record.id,
            evolution_id=evolution_id,
        )
        return record

    def process(self, key: str) -> ConvergenceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        evo_recs = [r for r in self._records if r.evolution_id == rec.evolution_id]
        rewards = [r.reward_value for r in evo_recs]
        avg_reward = round(sum(rewards) / len(rewards), 4) if rewards else 0.0
        analysis = ConvergenceAnalysis(
            evolution_id=rec.evolution_id,
            current_status=rec.status,
            avg_reward=avg_reward,
            convergence_speed=rec.speed,
            iteration_count=len(evo_recs),
            description=f"Evolution {rec.evolution_id} status {rec.status.value}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ConvergenceReport:
        by_st: dict[str, int] = {}
        by_cr: dict[str, int] = {}
        by_sp: dict[str, int] = {}
        rewards: list[float] = []
        for r in self._records:
            k1 = r.status.value
            by_st[k1] = by_st.get(k1, 0) + 1
            k2 = r.criterion.value
            by_cr[k2] = by_cr.get(k2, 0) + 1
            k3 = r.speed.value
            by_sp[k3] = by_sp.get(k3, 0) + 1
            rewards.append(r.reward_value)
        avg_reward = round(sum(rewards) / len(rewards), 4) if rewards else 0.0
        converged_ids: set[str] = set()
        for r in self._records:
            if r.status == ConvergenceStatus.CONVERGED:
                converged_ids.add(r.evolution_id)
        converged_list = sorted(converged_ids)[:10]
        recs_list: list[str] = []
        diverging = by_st.get("diverging", 0)
        stalled = by_sp.get("stalled", 0)
        if diverging > 0:
            recs_list.append(f"{diverging} diverging evolutions — check hyperparameters")
        if stalled > 0:
            recs_list.append(f"{stalled} stalled convergences — consider early stopping")
        if not recs_list:
            recs_list.append("Self-evolution convergence is progressing normally")
        return ConvergenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_reward=avg_reward,
            by_status=by_st,
            by_criterion=by_cr,
            by_speed=by_sp,
            converged_evolutions=converged_list,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            k = r.status.value
            status_dist[k] = status_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "status_distribution": status_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("self_evolution_convergence_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def detect_convergence_point(
        self,
        evolution_id: str,
        delta_threshold: float = 0.001,
        window: int = 5,
    ) -> dict[str, Any]:
        """Detect the iteration at which an evolution converged."""
        evo_recs = [r for r in self._records if r.evolution_id == evolution_id]
        if len(evo_recs) < window:
            return {
                "evolution_id": evolution_id,
                "converged": False,
                "reason": "insufficient_data",
            }
        evo_sorted = sorted(evo_recs, key=lambda x: x.iteration)
        convergence_iter = None
        for i in range(window, len(evo_sorted)):
            window_recs = evo_sorted[i - window : i]
            deltas = [abs(r.reward_delta) for r in window_recs]
            avg_delta = sum(deltas) / len(deltas)
            if avg_delta < delta_threshold:
                convergence_iter = evo_sorted[i - 1].iteration
                break
        return {
            "evolution_id": evolution_id,
            "converged": convergence_iter is not None,
            "convergence_iteration": convergence_iter,
            "delta_threshold": delta_threshold,
            "window_size": window,
        }

    def compute_convergence_rate(self, evolution_id: str) -> dict[str, Any]:
        """Compute the rate of convergence (reward improvement per iteration)."""
        evo_recs = [r for r in self._records if r.evolution_id == evolution_id]
        if len(evo_recs) < 2:
            return {"evolution_id": evolution_id, "convergence_rate": 0.0, "data_points": 0}
        evo_sorted = sorted(evo_recs, key=lambda x: x.iteration)
        first_reward = evo_sorted[0].reward_value
        last_reward = evo_sorted[-1].reward_value
        total_iters = evo_sorted[-1].iteration - evo_sorted[0].iteration
        rate = 0.0 if total_iters == 0 else round((last_reward - first_reward) / total_iters, 6)
        deltas = [r.reward_delta for r in evo_sorted]
        avg_delta = round(sum(deltas) / len(deltas), 6) if deltas else 0.0
        return {
            "evolution_id": evolution_id,
            "convergence_rate": rate,
            "avg_delta_per_iteration": avg_delta,
            "first_reward": first_reward,
            "last_reward": last_reward,
            "data_points": len(evo_sorted),
        }

    def recommend_stopping_iteration(
        self,
        evolution_id: str,
        cost_budget: float = 1000.0,
    ) -> dict[str, Any]:
        """Recommend when to stop the evolution loop based on cost and reward."""
        evo_recs = [r for r in self._records if r.evolution_id == evolution_id]
        if not evo_recs:
            return {"evolution_id": evolution_id, "recommended_stop": 0, "reason": "no_data"}
        evo_sorted = sorted(evo_recs, key=lambda x: x.iteration)
        total_cost = sum(r.cost_incurred for r in evo_sorted)
        cumulative_cost = 0.0
        budget_iteration = None
        for r in evo_sorted:
            cumulative_cost += r.cost_incurred
            if cumulative_cost >= cost_budget and budget_iteration is None:
                budget_iteration = r.iteration
        latest = evo_sorted[-1]
        reward_plateau = abs(latest.reward_delta) < 0.001
        recommended_stop = budget_iteration or latest.iteration
        reason = (
            "cost_threshold"
            if budget_iteration
            else ("reward_plateau" if reward_plateau else "continue")
        )
        return {
            "evolution_id": evolution_id,
            "recommended_stop": recommended_stop,
            "reason": reason,
            "total_cost": round(total_cost, 4),
            "budget": cost_budget,
            "reward_plateau": reward_plateau,
        }
