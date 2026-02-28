"""Agent Routing Optimizer — route tasks to optimal model based on complexity and cost."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ModelTier(StrEnum):
    FLAGSHIP = "flagship"
    STANDARD = "standard"
    FAST = "fast"
    MINI = "mini"
    CACHED = "cached"


class RoutingCriteria(StrEnum):
    COMPLEXITY = "complexity"
    URGENCY = "urgency"
    COST_BUDGET = "cost_budget"
    ACCURACY_NEEDED = "accuracy_needed"
    LATENCY = "latency"


class RoutingOutcome(StrEnum):
    OPTIMAL = "optimal"
    ACCEPTABLE = "acceptable"
    OVER_PROVISIONED = "over_provisioned"
    UNDER_PROVISIONED = "under_provisioned"
    FALLBACK = "fallback"


# --- Models ---


class RoutingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_name: str = ""
    model_tier: ModelTier = ModelTier.STANDARD
    routing_criteria: RoutingCriteria = RoutingCriteria.COMPLEXITY
    routing_outcome: RoutingOutcome = RoutingOutcome.OPTIMAL
    cost_dollars: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RoutingDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_label: str = ""
    model_tier: ModelTier = ModelTier.STANDARD
    routing_outcome: RoutingOutcome = RoutingOutcome.OPTIMAL
    latency_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


class RoutingOptimizerReport(BaseModel):
    total_routings: int = 0
    total_decisions: int = 0
    optimal_rate_pct: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    fallback_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentRoutingOptimizer:
    """Route tasks to optimal model based on complexity, cost, and latency."""

    def __init__(
        self,
        max_records: int = 200000,
        cost_limit: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._cost_limit = cost_limit
        self._records: list[RoutingRecord] = []
        self._decisions: list[RoutingDecision] = []
        logger.info(
            "routing_optimizer.initialized",
            max_records=max_records,
            cost_limit=cost_limit,
        )

    # -- record / get / list ---------------------------------------------

    def record_routing(
        self,
        task_name: str,
        model_tier: ModelTier = ModelTier.STANDARD,
        routing_criteria: RoutingCriteria = RoutingCriteria.COMPLEXITY,
        routing_outcome: RoutingOutcome = RoutingOutcome.OPTIMAL,
        cost_dollars: float = 0.0,
        details: str = "",
    ) -> RoutingRecord:
        record = RoutingRecord(
            task_name=task_name,
            model_tier=model_tier,
            routing_criteria=routing_criteria,
            routing_outcome=routing_outcome,
            cost_dollars=cost_dollars,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "routing_optimizer.recorded",
            record_id=record.id,
            task_name=task_name,
            model_tier=model_tier.value,
        )
        return record

    def get_routing(self, record_id: str) -> RoutingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_routings(
        self,
        task_name: str | None = None,
        model_tier: ModelTier | None = None,
        limit: int = 50,
    ) -> list[RoutingRecord]:
        results = list(self._records)
        if task_name is not None:
            results = [r for r in results if r.task_name == task_name]
        if model_tier is not None:
            results = [r for r in results if r.model_tier == model_tier]
        return results[-limit:]

    def add_decision(
        self,
        decision_label: str,
        model_tier: ModelTier = ModelTier.STANDARD,
        routing_outcome: RoutingOutcome = RoutingOutcome.OPTIMAL,
        latency_ms: float = 0.0,
    ) -> RoutingDecision:
        decision = RoutingDecision(
            decision_label=decision_label,
            model_tier=model_tier,
            routing_outcome=routing_outcome,
            latency_ms=latency_ms,
        )
        self._decisions.append(decision)
        if len(self._decisions) > self._max_records:
            self._decisions = self._decisions[-self._max_records :]
        logger.info(
            "routing_optimizer.decision_added",
            decision_label=decision_label,
            model_tier=model_tier.value,
        )
        return decision

    # -- domain operations -----------------------------------------------

    def analyze_routing_efficiency(self, task_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.task_name == task_name]
        if not records:
            return {"task_name": task_name, "status": "no_data"}
        optimal_count = sum(1 for r in records if r.routing_outcome == RoutingOutcome.OPTIMAL)
        optimal_rate = round(optimal_count / len(records) * 100, 2)
        avg_cost = round(sum(r.cost_dollars for r in records) / len(records), 2)
        return {
            "task_name": task_name,
            "total_routings": len(records),
            "optimal_count": optimal_count,
            "optimal_rate_pct": optimal_rate,
            "avg_cost_dollars": avg_cost,
            "meets_threshold": avg_cost <= self._cost_limit,
        }

    def identify_suboptimal_routings(self) -> list[dict[str, Any]]:
        by_task: dict[str, int] = {}
        suboptimal = {
            RoutingOutcome.OVER_PROVISIONED,
            RoutingOutcome.UNDER_PROVISIONED,
            RoutingOutcome.FALLBACK,
        }
        for r in self._records:
            if r.routing_outcome in suboptimal:
                by_task[r.task_name] = by_task.get(r.task_name, 0) + 1
        results: list[dict[str, Any]] = []
        for task, count in by_task.items():
            if count > 1:
                results.append({"task_name": task, "suboptimal_count": count})
        results.sort(key=lambda x: x["suboptimal_count"], reverse=True)
        return results

    def rank_by_cost_efficiency(self) -> list[dict[str, Any]]:
        by_task: dict[str, float] = {}
        for r in self._records:
            by_task[r.task_name] = by_task.get(r.task_name, 0.0) + r.cost_dollars
        results: list[dict[str, Any]] = []
        for task, total in by_task.items():
            results.append(
                {
                    "task_name": task,
                    "total_cost_dollars": round(total, 2),
                }
            )
        results.sort(key=lambda x: x["total_cost_dollars"])
        return results

    def detect_routing_failures(self) -> list[dict[str, Any]]:
        by_task: dict[str, int] = {}
        for r in self._records:
            if r.routing_outcome == RoutingOutcome.FALLBACK:
                by_task[r.task_name] = by_task.get(r.task_name, 0) + 1
        results: list[dict[str, Any]] = []
        for task, count in by_task.items():
            if count > 3:
                results.append(
                    {
                        "task_name": task,
                        "fallback_count": count,
                        "failing": True,
                    }
                )
        results.sort(key=lambda x: x["fallback_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RoutingOptimizerReport:
        by_tier: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_tier[r.model_tier.value] = by_tier.get(r.model_tier.value, 0) + 1
            by_outcome[r.routing_outcome.value] = by_outcome.get(r.routing_outcome.value, 0) + 1
        optimal_count = sum(1 for r in self._records if r.routing_outcome == RoutingOutcome.OPTIMAL)
        optimal_rate = round(optimal_count / len(self._records) * 100, 2) if self._records else 0.0
        fallback_count = sum(
            1 for r in self._records if r.routing_outcome == RoutingOutcome.FALLBACK
        )
        recs: list[str] = []
        if fallback_count > 0:
            recs.append(f"{fallback_count} fallback routing(s) detected")
        if optimal_rate < 80.0 and self._records:
            recs.append(f"Optimal rate {optimal_rate}% is below 80% target")
        if not recs:
            recs.append("Routing optimization meets targets")
        return RoutingOptimizerReport(
            total_routings=len(self._records),
            total_decisions=len(self._decisions),
            optimal_rate_pct=optimal_rate,
            by_tier=by_tier,
            by_outcome=by_outcome,
            fallback_count=fallback_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._decisions.clear()
        logger.info("routing_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.model_tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_decisions": len(self._decisions),
            "cost_limit": self._cost_limit,
            "tier_distribution": tier_dist,
            "unique_tasks": len({r.task_name for r in self._records}),
        }
