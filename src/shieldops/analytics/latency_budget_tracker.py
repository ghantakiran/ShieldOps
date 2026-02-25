"""API Latency Budget Tracker — define per-endpoint latency budgets and track ongoing compliance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BudgetCompliance(StrEnum):
    WITHIN_BUDGET = "within_budget"
    APPROACHING_LIMIT = "approaching_limit"
    OVER_BUDGET = "over_budget"
    CHRONICALLY_OVER = "chronically_over"
    NO_BUDGET_SET = "no_budget_set"


class LatencyPercentile(StrEnum):
    P50 = "p50"
    P75 = "p75"
    P90 = "p90"
    P95 = "p95"
    P99 = "p99"


class EndpointTier(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    STANDARD = "standard"
    LOW_PRIORITY = "low_priority"
    BATCH = "batch"


# --- Models ---


class LatencyBudget(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    endpoint: str = ""
    tier: EndpointTier = EndpointTier.STANDARD
    budget_ms: float = 200.0
    percentile: LatencyPercentile = LatencyPercentile.P95
    current_ms: float = 0.0
    compliance: BudgetCompliance = BudgetCompliance.NO_BUDGET_SET
    violation_count: int = 0
    created_at: float = Field(default_factory=time.time)


class BudgetViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    budget_id: str = ""
    endpoint: str = ""
    measured_ms: float = 0.0
    budget_ms: float = 0.0
    overage_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


class LatencyBudgetReport(BaseModel):
    total_budgets: int = 0
    total_violations: int = 0
    by_compliance: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_percentile: dict[str, int] = Field(default_factory=dict)
    chronic_violators: list[str] = Field(default_factory=list)
    avg_overage_ms: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class LatencyBudgetTracker:
    """Define per-endpoint latency budgets and track ongoing compliance."""

    def __init__(
        self,
        max_records: int = 500000,
        chronic_violation_threshold: int = 10,
    ) -> None:
        self._max_records = max_records
        self._chronic_threshold = chronic_violation_threshold
        self._budgets: list[LatencyBudget] = []
        self._violations: list[BudgetViolation] = []
        logger.info(
            "latency_budget_tracker.initialized",
            max_records=max_records,
            chronic_violation_threshold=chronic_violation_threshold,
        )

    # -- budget / get / list -----------------------------------------

    def create_budget(
        self,
        endpoint: str,
        budget_ms: float = 200.0,
        tier: EndpointTier = EndpointTier.STANDARD,
        percentile: LatencyPercentile = LatencyPercentile.P95,
        **kw: Any,
    ) -> LatencyBudget:
        budget = LatencyBudget(
            endpoint=endpoint,
            budget_ms=budget_ms,
            tier=tier,
            percentile=percentile,
            compliance=BudgetCompliance.WITHIN_BUDGET,
            **kw,
        )
        self._budgets.append(budget)
        if len(self._budgets) > self._max_records:
            self._budgets = self._budgets[-self._max_records :]
        logger.info(
            "latency_budget_tracker.budget_created",
            budget_id=budget.id,
            endpoint=endpoint,
        )
        return budget

    def get_budget(self, budget_id: str) -> LatencyBudget | None:
        for b in self._budgets:
            if b.id == budget_id:
                return b
        return None

    def list_budgets(
        self,
        endpoint: str | None = None,
        tier: EndpointTier | None = None,
        compliance: BudgetCompliance | None = None,
        limit: int = 50,
    ) -> list[LatencyBudget]:
        results = list(self._budgets)
        if endpoint is not None:
            results = [r for r in results if r.endpoint == endpoint]
        if tier is not None:
            results = [r for r in results if r.tier == tier]
        if compliance is not None:
            results = [r for r in results if r.compliance == compliance]
        return results[-limit:]

    # -- measurements ------------------------------------------------

    def record_measurement(
        self,
        budget_id: str,
        measured_ms: float,
    ) -> dict[str, Any]:
        """Record a latency measurement against a budget."""
        budget = self.get_budget(budget_id)
        if budget is None:
            return {"found": False, "violation": False}
        budget.current_ms = measured_ms
        violation = measured_ms > budget.budget_ms
        if violation:
            budget.violation_count += 1
            overage = round(measured_ms - budget.budget_ms, 2)
            v = BudgetViolation(
                budget_id=budget_id,
                endpoint=budget.endpoint,
                measured_ms=measured_ms,
                budget_ms=budget.budget_ms,
                overage_ms=overage,
            )
            self._violations.append(v)
            if len(self._violations) > self._max_records:
                self._violations = self._violations[-self._max_records :]
        # Update compliance status
        if budget.violation_count >= self._chronic_threshold:
            budget.compliance = BudgetCompliance.CHRONICALLY_OVER
        elif violation:
            budget.compliance = BudgetCompliance.OVER_BUDGET
        elif measured_ms > budget.budget_ms * 0.85:
            budget.compliance = BudgetCompliance.APPROACHING_LIMIT
        else:
            budget.compliance = BudgetCompliance.WITHIN_BUDGET
        return {
            "found": True,
            "budget_id": budget_id,
            "violation": violation,
            "compliance": budget.compliance.value,
            "measured_ms": measured_ms,
            "budget_ms": budget.budget_ms,
        }

    def list_violations(
        self,
        budget_id: str | None = None,
        endpoint: str | None = None,
        limit: int = 50,
    ) -> list[BudgetViolation]:
        results = list(self._violations)
        if budget_id is not None:
            results = [r for r in results if r.budget_id == budget_id]
        if endpoint is not None:
            results = [r for r in results if r.endpoint == endpoint]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def check_compliance(
        self,
        budget_id: str,
    ) -> dict[str, Any]:
        """Check current compliance status for a budget."""
        budget = self.get_budget(budget_id)
        if budget is None:
            return {"found": False, "compliance": BudgetCompliance.NO_BUDGET_SET.value}
        return {
            "found": True,
            "budget_id": budget_id,
            "endpoint": budget.endpoint,
            "compliance": budget.compliance.value,
            "current_ms": budget.current_ms,
            "budget_ms": budget.budget_ms,
            "violation_count": budget.violation_count,
        }

    def find_chronic_violators(self) -> list[LatencyBudget]:
        """Find endpoints chronically over budget."""
        return [b for b in self._budgets if b.violation_count >= self._chronic_threshold]

    def adjust_budget(
        self,
        budget_id: str,
        new_budget_ms: float,
    ) -> bool:
        """Adjust the latency budget for an endpoint."""
        budget = self.get_budget(budget_id)
        if budget is None:
            return False
        budget.budget_ms = new_budget_ms
        # Reset compliance
        if budget.current_ms > new_budget_ms:
            budget.compliance = BudgetCompliance.OVER_BUDGET
        elif budget.current_ms > new_budget_ms * 0.85:
            budget.compliance = BudgetCompliance.APPROACHING_LIMIT
        else:
            budget.compliance = BudgetCompliance.WITHIN_BUDGET
        logger.info(
            "latency_budget_tracker.budget_adjusted",
            budget_id=budget_id,
            new_budget_ms=new_budget_ms,
        )
        return True

    # -- report / stats ----------------------------------------------

    def generate_budget_report(self) -> LatencyBudgetReport:
        by_compliance: dict[str, int] = {}
        for b in self._budgets:
            key = b.compliance.value
            by_compliance[key] = by_compliance.get(key, 0) + 1
        by_tier: dict[str, int] = {}
        for b in self._budgets:
            key = b.tier.value
            by_tier[key] = by_tier.get(key, 0) + 1
        by_percentile: dict[str, int] = {}
        for b in self._budgets:
            key = b.percentile.value
            by_percentile[key] = by_percentile.get(key, 0) + 1
        chronic = self.find_chronic_violators()
        chronic_names = [b.endpoint for b in chronic[:5]]
        overages = [v.overage_ms for v in self._violations if v.overage_ms > 0]
        avg_overage = round(sum(overages) / len(overages), 2) if overages else 0.0
        recs: list[str] = []
        if chronic:
            recs.append(f"{len(chronic)} endpoint(s) chronically over latency budget")
        if not recs:
            recs.append("All endpoints within latency budgets")
        return LatencyBudgetReport(
            total_budgets=len(self._budgets),
            total_violations=len(self._violations),
            by_compliance=by_compliance,
            by_tier=by_tier,
            by_percentile=by_percentile,
            chronic_violators=chronic_names,
            avg_overage_ms=avg_overage,
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._budgets)
        self._budgets.clear()
        self._violations.clear()
        logger.info("latency_budget_tracker.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        comp_dist: dict[str, int] = {}
        for b in self._budgets:
            key = b.compliance.value
            comp_dist[key] = comp_dist.get(key, 0) + 1
        return {
            "total_budgets": len(self._budgets),
            "total_violations": len(self._violations),
            "chronic_violation_threshold": self._chronic_threshold,
            "compliance_distribution": comp_dist,
        }
