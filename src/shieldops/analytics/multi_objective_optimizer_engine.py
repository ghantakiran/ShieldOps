"""Multi-Objective Optimizer Engine —
find Pareto frontiers, evaluate tradeoff strategies,
and rank solutions across competing objectives."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ObjectiveType(StrEnum):
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    COST = "cost"
    RELIABILITY = "reliability"


class TradeoffStrategy(StrEnum):
    PARETO = "pareto"
    WEIGHTED = "weighted"
    LEXICOGRAPHIC = "lexicographic"
    EPSILON_CONSTRAINT = "epsilon_constraint"


class OptimizationStatus(StrEnum):
    OPTIMAL = "optimal"
    SUBOPTIMAL = "suboptimal"
    INFEASIBLE = "infeasible"
    EXPLORING = "exploring"


# --- Models ---


class MultiObjectiveRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    solution_id: str = ""
    objective_type: ObjectiveType = ObjectiveType.RELIABILITY
    tradeoff_strategy: TradeoffStrategy = TradeoffStrategy.PARETO
    status: OptimizationStatus = OptimizationStatus.EXPLORING
    objective_value: float = 0.0
    weight: float = 1.0
    constraint_bound: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MultiObjectiveAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    solution_id: str = ""
    avg_objective: float = 0.0
    dominant_strategy: TradeoffStrategy = TradeoffStrategy.PARETO
    status: OptimizationStatus = OptimizationStatus.EXPLORING
    objective_count: int = 0
    pareto_rank: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MultiObjectiveReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_objective_value: float = 0.0
    by_objective_type: dict[str, int] = Field(default_factory=dict)
    by_tradeoff_strategy: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_solutions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MultiObjectiveOptimizerEngine:
    """Balance competing optimization objectives, find Pareto
    frontiers, and rank solutions by objective performance."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[MultiObjectiveRecord] = []
        self._analyses: dict[str, MultiObjectiveAnalysis] = {}
        logger.info(
            "multi_objective_optimizer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        solution_id: str = "",
        objective_type: ObjectiveType = ObjectiveType.RELIABILITY,
        tradeoff_strategy: TradeoffStrategy = TradeoffStrategy.PARETO,
        status: OptimizationStatus = OptimizationStatus.EXPLORING,
        objective_value: float = 0.0,
        weight: float = 1.0,
        constraint_bound: float = 0.0,
        description: str = "",
    ) -> MultiObjectiveRecord:
        record = MultiObjectiveRecord(
            solution_id=solution_id,
            objective_type=objective_type,
            tradeoff_strategy=tradeoff_strategy,
            status=status,
            objective_value=objective_value,
            weight=weight,
            constraint_bound=constraint_bound,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "multi_objective.record_added",
            record_id=record.id,
            solution_id=solution_id,
        )
        return record

    def process(self, key: str) -> MultiObjectiveAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        sol_recs = [r for r in self._records if r.solution_id == rec.solution_id]
        vals = [r.objective_value for r in sol_recs]
        avg = round(sum(vals) / len(vals), 2) if vals else 0.0
        strategy_counts: dict[str, int] = {}
        for r in sol_recs:
            strategy_counts[r.tradeoff_strategy.value] = (
                strategy_counts.get(r.tradeoff_strategy.value, 0) + 1
            )
        dominant_strategy = (
            TradeoffStrategy(max(strategy_counts, key=lambda x: strategy_counts[x]))
            if strategy_counts
            else TradeoffStrategy.PARETO
        )
        analysis = MultiObjectiveAnalysis(
            solution_id=rec.solution_id,
            avg_objective=avg,
            dominant_strategy=dominant_strategy,
            status=rec.status,
            objective_count=len(sol_recs),
            pareto_rank=0,
            description=f"Solution {rec.solution_id} avg objective {avg}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> MultiObjectiveReport:
        by_ot: dict[str, int] = {}
        by_ts: dict[str, int] = {}
        by_st: dict[str, int] = {}
        vals: list[float] = []
        for r in self._records:
            by_ot[r.objective_type.value] = by_ot.get(r.objective_type.value, 0) + 1
            by_ts[r.tradeoff_strategy.value] = by_ts.get(r.tradeoff_strategy.value, 0) + 1
            by_st[r.status.value] = by_st.get(r.status.value, 0) + 1
            vals.append(r.objective_value)
        avg = round(sum(vals) / len(vals), 2) if vals else 0.0
        sol_totals: dict[str, float] = {}
        for r in self._records:
            sol_totals[r.solution_id] = sol_totals.get(r.solution_id, 0.0) + r.objective_value
        ranked = sorted(
            sol_totals,
            key=lambda x: sol_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        infeasible = by_st.get("infeasible", 0)
        if infeasible > 0:
            recs.append(f"{infeasible} infeasible solutions — relax constraints")
        suboptimal = by_st.get("suboptimal", 0)
        if suboptimal > 0:
            recs.append(f"{suboptimal} suboptimal solutions — run further iterations")
        if not recs:
            recs.append("Optimization landscape is healthy")
        return MultiObjectiveReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_objective_value=avg,
            by_objective_type=by_ot,
            by_tradeoff_strategy=by_ts,
            by_status=by_st,
            top_solutions=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            dist[r.objective_type.value] = dist.get(r.objective_type.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "objective_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("multi_objective_optimizer.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def find_pareto_frontiers(self) -> list[dict[str, Any]]:
        """Identify Pareto-optimal solutions across all objectives."""
        sol_objectives: dict[str, dict[str, float]] = {}
        for r in self._records:
            entry = sol_objectives.setdefault(r.solution_id, {})
            entry[r.objective_type.value] = r.objective_value
        solutions = list(sol_objectives.items())
        pareto: list[dict[str, Any]] = []
        for sid, obj_a in solutions:
            dominated = False
            for other_sid, obj_b in solutions:
                if other_sid == sid:
                    continue
                all_keys = set(obj_a) | set(obj_b)
                if all(obj_b.get(k, 0) >= obj_a.get(k, 0) for k in all_keys) and any(
                    obj_b.get(k, 0) > obj_a.get(k, 0) for k in all_keys
                ):
                    dominated = True
                    break
            if not dominated:
                pareto.append(
                    {
                        "solution_id": sid,
                        "objectives": obj_a,
                        "pareto_optimal": True,
                        "objective_count": len(obj_a),
                    }
                )
        pareto.sort(key=lambda x: sum(x["objectives"].values()), reverse=True)
        return pareto

    def evaluate_tradeoff_strategies(self) -> list[dict[str, Any]]:
        """Evaluate performance of each tradeoff strategy."""
        strategy_data: dict[str, list[float]] = {}
        for r in self._records:
            strategy_data.setdefault(r.tradeoff_strategy.value, []).append(r.objective_value)
        results: list[dict[str, Any]] = []
        for strategy, vals in strategy_data.items():
            avg_v = round(sum(vals) / len(vals), 2) if vals else 0.0
            max_v = round(max(vals), 2) if vals else 0.0
            min_v = round(min(vals), 2) if vals else 0.0
            results.append(
                {
                    "strategy": strategy,
                    "avg_objective": avg_v,
                    "max_objective": max_v,
                    "min_objective": min_v,
                    "sample_count": len(vals),
                    "range": round(max_v - min_v, 2),
                }
            )
        results.sort(key=lambda x: x["avg_objective"], reverse=True)
        return results

    def rank_solutions_by_objective(
        self,
        objective: str = "reliability",
    ) -> list[dict[str, Any]]:
        """Rank solutions by a specific objective type."""
        sol_vals: dict[str, list[float]] = {}
        for r in self._records:
            if r.objective_type.value == objective:
                sol_vals.setdefault(r.solution_id, []).append(r.objective_value)
        results: list[dict[str, Any]] = []
        for sid, vals in sol_vals.items():
            avg_v = round(sum(vals) / len(vals), 2) if vals else 0.0
            results.append(
                {
                    "solution_id": sid,
                    "objective": objective,
                    "avg_value": avg_v,
                    "sample_count": len(vals),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_value"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
