"""Evolution Iteration Optimizer Engine —
optimizes number of co-evolution iterations and resource allocation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class OptimizationStrategy(StrEnum):
    FIXED_BUDGET = "fixed_budget"
    ADAPTIVE_BUDGET = "adaptive_budget"
    DIMINISHING_RETURNS = "diminishing_returns"
    GREEDY = "greedy"


class ResourceAllocation(StrEnum):
    COMPUTE_HEAVY = "compute_heavy"
    BALANCED = "balanced"
    MEMORY_HEAVY = "memory_heavy"
    MINIMAL = "minimal"


class IterationEfficiency(StrEnum):
    OPTIMAL = "optimal"
    ACCEPTABLE = "acceptable"
    WASTEFUL = "wasteful"
    INSUFFICIENT = "insufficient"


# --- Models ---


class IterationOptimizerRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    iteration: int = 0
    strategy: OptimizationStrategy = OptimizationStrategy.ADAPTIVE_BUDGET
    allocation: ResourceAllocation = ResourceAllocation.BALANCED
    efficiency: IterationEfficiency = IterationEfficiency.OPTIMAL
    cost_per_iteration: float = 0.0
    improvement_gain: float = 0.0
    compute_units: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IterationOptimizerAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    avg_cost_per_iter: float = 0.0
    avg_improvement: float = 0.0
    efficiency: IterationEfficiency = IterationEfficiency.OPTIMAL
    iteration_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IterationOptimizerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_cost_per_iter: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_allocation: dict[str, int] = Field(default_factory=dict)
    by_efficiency: dict[str, int] = Field(default_factory=dict)
    optimal_runs: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EvolutionIterationOptimizerEngine:
    """Optimizes number of co-evolution iterations and resource allocation."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[IterationOptimizerRecord] = []
        self._analyses: dict[str, IterationOptimizerAnalysis] = {}
        logger.info(
            "evolution_iteration_optimizer_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        run_id: str = "",
        iteration: int = 0,
        strategy: OptimizationStrategy = OptimizationStrategy.ADAPTIVE_BUDGET,
        allocation: ResourceAllocation = ResourceAllocation.BALANCED,
        efficiency: IterationEfficiency = IterationEfficiency.OPTIMAL,
        cost_per_iteration: float = 0.0,
        improvement_gain: float = 0.0,
        compute_units: float = 0.0,
        description: str = "",
    ) -> IterationOptimizerRecord:
        record = IterationOptimizerRecord(
            run_id=run_id,
            iteration=iteration,
            strategy=strategy,
            allocation=allocation,
            efficiency=efficiency,
            cost_per_iteration=cost_per_iteration,
            improvement_gain=improvement_gain,
            compute_units=compute_units,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "evolution_iteration_optimizer.record_added",
            record_id=record.id,
            run_id=run_id,
        )
        return record

    def process(self, key: str) -> IterationOptimizerAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        run_recs = [r for r in self._records if r.run_id == rec.run_id]
        costs = [r.cost_per_iteration for r in run_recs]
        gains = [r.improvement_gain for r in run_recs]
        avg_cost = round(sum(costs) / len(costs), 4) if costs else 0.0
        avg_gain = round(sum(gains) / len(gains), 4) if gains else 0.0
        analysis = IterationOptimizerAnalysis(
            run_id=rec.run_id,
            avg_cost_per_iter=avg_cost,
            avg_improvement=avg_gain,
            efficiency=rec.efficiency,
            iteration_count=len(run_recs),
            description=f"Run {rec.run_id} avg cost {avg_cost} avg gain {avg_gain}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> IterationOptimizerReport:
        by_st: dict[str, int] = {}
        by_al: dict[str, int] = {}
        by_eff: dict[str, int] = {}
        costs: list[float] = []
        for r in self._records:
            k1 = r.strategy.value
            by_st[k1] = by_st.get(k1, 0) + 1
            k2 = r.allocation.value
            by_al[k2] = by_al.get(k2, 0) + 1
            k3 = r.efficiency.value
            by_eff[k3] = by_eff.get(k3, 0) + 1
            costs.append(r.cost_per_iteration)
        avg_cost = round(sum(costs) / len(costs), 4) if costs else 0.0
        run_gains: dict[str, float] = {}
        for r in self._records:
            run_gains[r.run_id] = run_gains.get(r.run_id, 0.0) + r.improvement_gain
        optimal_runs = sorted(
            run_gains,
            key=lambda x: run_gains[x],
            reverse=True,
        )[:10]
        recs_list: list[str] = []
        wasteful = by_eff.get("wasteful", 0)
        insufficient = by_eff.get("insufficient", 0)
        if wasteful > 0:
            recs_list.append(f"{wasteful} wasteful iteration runs — reduce iteration budget")
        if insufficient > 0:
            recs_list.append(f"{insufficient} insufficient runs — increase iteration count")
        if not recs_list:
            recs_list.append("Iteration efficiency is well-optimized")
        return IterationOptimizerReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_cost_per_iter=avg_cost,
            by_strategy=by_st,
            by_allocation=by_al,
            by_efficiency=by_eff,
            optimal_runs=optimal_runs,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        eff_dist: dict[str, int] = {}
        for r in self._records:
            k = r.efficiency.value
            eff_dist[k] = eff_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "efficiency_distribution": eff_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("evolution_iteration_optimizer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_cost_per_improvement(self) -> list[dict[str, Any]]:
        """Compute cost-per-unit-improvement for each run."""
        run_data: dict[str, dict[str, float]] = {}
        for r in self._records:
            if r.run_id not in run_data:
                run_data[r.run_id] = {"cost": 0.0, "gain": 0.0, "count": 0.0}
            run_data[r.run_id]["cost"] += r.cost_per_iteration
            run_data[r.run_id]["gain"] += r.improvement_gain
            run_data[r.run_id]["count"] += 1
        results: list[dict[str, Any]] = []
        for rid, data in run_data.items():
            total_cost = data["cost"]
            total_gain = data["gain"]
            cpi = round(total_cost / total_gain, 4) if total_gain > 0 else float("inf")
            results.append(
                {
                    "run_id": rid,
                    "total_cost": round(total_cost, 4),
                    "total_gain": round(total_gain, 4),
                    "cost_per_improvement": cpi,
                    "iterations": int(data["count"]),
                }
            )
        results.sort(key=lambda x: x["cost_per_improvement"])
        return results

    def recommend_iteration_budget(
        self,
        target_improvement: float = 0.1,
        cost_budget: float = 500.0,
    ) -> dict[str, Any]:
        """Recommend iteration budget to hit target improvement within cost."""
        if not self._records:
            return {
                "recommended_iterations": 0,
                "estimated_cost": 0.0,
                "reason": "no_data",
            }
        costs = [r.cost_per_iteration for r in self._records]
        gains = [r.improvement_gain for r in self._records]
        avg_cost = sum(costs) / len(costs) if costs else 0.0
        avg_gain = sum(gains) / len(gains) if gains else 0.0
        if avg_gain <= 0:
            return {
                "recommended_iterations": 0,
                "estimated_cost": 0.0,
                "reason": "zero_avg_gain",
            }
        iters_for_target = int(target_improvement / avg_gain) + 1
        iters_for_budget = int(cost_budget / avg_cost) if avg_cost > 0 else iters_for_target
        recommended = min(iters_for_target, iters_for_budget)
        return {
            "recommended_iterations": recommended,
            "estimated_cost": round(recommended * avg_cost, 4),
            "estimated_improvement": round(recommended * avg_gain, 4),
            "target_improvement": target_improvement,
            "cost_budget": cost_budget,
            "avg_cost_per_iter": round(avg_cost, 4),
            "avg_gain_per_iter": round(avg_gain, 4),
        }

    def analyze_diminishing_returns(self, run_id: str) -> dict[str, Any]:
        """Detect diminishing returns in a specific run."""
        run_recs = [r for r in self._records if r.run_id == run_id]
        if len(run_recs) < 4:
            return {"run_id": run_id, "diminishing_returns": False, "reason": "insufficient_data"}
        run_sorted = sorted(run_recs, key=lambda x: x.iteration)
        gains = [r.improvement_gain for r in run_sorted]
        half = len(gains) // 2
        first_half_avg = sum(gains[:half]) / half if half > 0 else 0.0
        second_half_avg = sum(gains[half:]) / (len(gains) - half) if len(gains) > half else 0.0
        diminishing = second_half_avg < first_half_avg * 0.5
        drop_ratio = (
            round((first_half_avg - second_half_avg) / first_half_avg, 4)
            if first_half_avg > 0
            else 0.0
        )
        return {
            "run_id": run_id,
            "diminishing_returns": diminishing,
            "first_half_avg_gain": round(first_half_avg, 4),
            "second_half_avg_gain": round(second_half_avg, 4),
            "drop_ratio": drop_ratio,
            "recommended_stop_at": half if diminishing else len(run_sorted),
        }
