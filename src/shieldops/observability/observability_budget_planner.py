"""Observability Budget Planner — plan observability budgets and detect overspend."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BudgetCategory(StrEnum):
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"
    ALERTS = "alerts"
    DASHBOARDS = "dashboards"


class SpendLevel(StrEnum):
    UNDER_BUDGET = "under_budget"
    ON_BUDGET = "on_budget"
    APPROACHING_LIMIT = "approaching_limit"
    OVER_BUDGET = "over_budget"
    CRITICAL = "critical"


class BudgetPeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


# --- Models ---


class BudgetRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    budget_id: str = ""
    budget_category: BudgetCategory = BudgetCategory.METRICS
    spend_level: SpendLevel = SpendLevel.ON_BUDGET
    budget_period: BudgetPeriod = BudgetPeriod.MONTHLY
    spend_amount: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BudgetAllocation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    budget_id: str = ""
    budget_category: BudgetCategory = BudgetCategory.METRICS
    allocation_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ObservabilityBudgetReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_allocations: int = 0
    over_budget_count: int = 0
    avg_spend_amount: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_spend_level: dict[str, int] = Field(default_factory=dict)
    by_period: dict[str, int] = Field(default_factory=dict)
    top_overspenders: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ObservabilityBudgetPlanner:
    """Plan observability budgets, track spend vs allocation, detect overspend."""

    def __init__(
        self,
        max_records: int = 200000,
        max_over_budget_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_over_budget_pct = max_over_budget_pct
        self._records: list[BudgetRecord] = []
        self._allocations: list[BudgetAllocation] = []
        logger.info(
            "observability_budget_planner.initialized",
            max_records=max_records,
            max_over_budget_pct=max_over_budget_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_budget(
        self,
        budget_id: str,
        budget_category: BudgetCategory = BudgetCategory.METRICS,
        spend_level: SpendLevel = SpendLevel.ON_BUDGET,
        budget_period: BudgetPeriod = BudgetPeriod.MONTHLY,
        spend_amount: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BudgetRecord:
        record = BudgetRecord(
            budget_id=budget_id,
            budget_category=budget_category,
            spend_level=spend_level,
            budget_period=budget_period,
            spend_amount=spend_amount,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "observability_budget_planner.budget_recorded",
            record_id=record.id,
            budget_id=budget_id,
            budget_category=budget_category.value,
            spend_level=spend_level.value,
        )
        return record

    def get_budget(self, record_id: str) -> BudgetRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_budgets(
        self,
        budget_category: BudgetCategory | None = None,
        spend_level: SpendLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BudgetRecord]:
        results = list(self._records)
        if budget_category is not None:
            results = [r for r in results if r.budget_category == budget_category]
        if spend_level is not None:
            results = [r for r in results if r.spend_level == spend_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_allocation(
        self,
        budget_id: str,
        budget_category: BudgetCategory = BudgetCategory.METRICS,
        allocation_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BudgetAllocation:
        allocation = BudgetAllocation(
            budget_id=budget_id,
            budget_category=budget_category,
            allocation_score=allocation_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._allocations.append(allocation)
        if len(self._allocations) > self._max_records:
            self._allocations = self._allocations[-self._max_records :]
        logger.info(
            "observability_budget_planner.allocation_added",
            budget_id=budget_id,
            budget_category=budget_category.value,
            allocation_score=allocation_score,
        )
        return allocation

    # -- domain operations --------------------------------------------------

    def analyze_budget_distribution(self) -> dict[str, Any]:
        """Group by budget_category; return count and avg spend_amount."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.budget_category.value
            cat_data.setdefault(key, []).append(r.spend_amount)
        result: dict[str, Any] = {}
        for cat, amounts in cat_data.items():
            result[cat] = {
                "count": len(amounts),
                "avg_spend_amount": round(sum(amounts) / len(amounts), 2),
            }
        return result

    def identify_over_budget(self) -> list[dict[str, Any]]:
        """Return records where spend_level is OVER_BUDGET or CRITICAL."""
        over_levels = {SpendLevel.OVER_BUDGET, SpendLevel.CRITICAL}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.spend_level in over_levels:
                results.append(
                    {
                        "record_id": r.id,
                        "budget_id": r.budget_id,
                        "budget_category": r.budget_category.value,
                        "spend_level": r.spend_level.value,
                        "spend_amount": r.spend_amount,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["spend_amount"], reverse=True)
        return results

    def rank_by_spend(self) -> list[dict[str, Any]]:
        """Group by service, avg spend_amount, sort desc."""
        service_amounts: dict[str, list[float]] = {}
        for r in self._records:
            service_amounts.setdefault(r.service, []).append(r.spend_amount)
        results: list[dict[str, Any]] = []
        for svc, amounts in service_amounts.items():
            results.append(
                {
                    "service": svc,
                    "avg_spend_amount": round(sum(amounts) / len(amounts), 2),
                    "record_count": len(amounts),
                }
            )
        results.sort(key=lambda x: x["avg_spend_amount"], reverse=True)
        return results

    def detect_budget_trends(self) -> dict[str, Any]:
        """Split-half comparison on allocation_score; delta threshold 5.0."""
        if len(self._allocations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.allocation_score for a in self._allocations]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> ObservabilityBudgetReport:
        by_category: dict[str, int] = {}
        by_spend_level: dict[str, int] = {}
        by_period: dict[str, int] = {}
        for r in self._records:
            by_category[r.budget_category.value] = by_category.get(r.budget_category.value, 0) + 1
            by_spend_level[r.spend_level.value] = by_spend_level.get(r.spend_level.value, 0) + 1
            by_period[r.budget_period.value] = by_period.get(r.budget_period.value, 0) + 1
        over_budget_count = len(self.identify_over_budget())
        avg_spend = (
            round(
                sum(r.spend_amount for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        over_list = self.identify_over_budget()
        top_overspenders = list(dict.fromkeys(o["service"] for o in over_list))
        recs: list[str] = []
        if over_budget_count > 0:
            recs.append(
                f"{over_budget_count} over-budget record(s) detected — review spend allocations"
            )
        ob_pct = round(over_budget_count / len(self._records) * 100, 2) if self._records else 0.0
        if ob_pct > self._max_over_budget_pct:
            recs.append(
                f"Over-budget rate {ob_pct}% exceeds threshold ({self._max_over_budget_pct}%)"
            )
        if not recs:
            recs.append("Budget levels are acceptable")
        return ObservabilityBudgetReport(
            total_records=len(self._records),
            total_allocations=len(self._allocations),
            over_budget_count=over_budget_count,
            avg_spend_amount=avg_spend,
            by_category=by_category,
            by_spend_level=by_spend_level,
            by_period=by_period,
            top_overspenders=top_overspenders,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._allocations.clear()
        logger.info("observability_budget_planner.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.budget_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_allocations": len(self._allocations),
            "max_over_budget_pct": self._max_over_budget_pct,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
