"""Infrastructure Cost Budget Manager — budget ceilings, burn rate tracking."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BudgetPeriod(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class BudgetStatus(StrEnum):
    ON_TRACK = "on_track"
    WARNING = "warning"
    OVER_BUDGET = "over_budget"
    EXHAUSTED = "exhausted"


class SpendCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    OTHER = "other"


# --- Models ---


class Budget(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    owner: str = ""
    team: str = ""
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    limit_amount: float = 0.0
    spent_amount: float = 0.0
    status: BudgetStatus = BudgetStatus.ON_TRACK
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class SpendEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    budget_id: str
    amount: float
    category: SpendCategory = SpendCategory.OTHER
    description: str = ""
    recorded_at: float = Field(default_factory=time.time)


class BurnRateReport(BaseModel):
    budget_id: str
    budget_name: str = ""
    limit_amount: float = 0.0
    spent_amount: float = 0.0
    remaining: float = 0.0
    burn_rate_per_day: float = 0.0
    days_remaining: float | None = None
    status: BudgetStatus = BudgetStatus.ON_TRACK


# --- Engine ---


class InfrastructureCostBudgetManager:
    """Budget ceilings per team/project, burn rate tracking, overspend alerts."""

    def __init__(
        self,
        max_budgets: int = 2000,
        warning_threshold: float = 0.8,
    ) -> None:
        self._max_budgets = max_budgets
        self._warning_threshold = warning_threshold
        self._budgets: dict[str, Budget] = {}
        self._entries: list[SpendEntry] = []
        logger.info(
            "budget_manager.initialized",
            max_budgets=max_budgets,
            warning_threshold=warning_threshold,
        )

    def create_budget(
        self,
        name: str,
        limit_amount: float,
        period: BudgetPeriod = BudgetPeriod.MONTHLY,
        **kw: Any,
    ) -> Budget:
        budget = Budget(
            name=name,
            limit_amount=limit_amount,
            period=period,
            **kw,
        )
        self._budgets[budget.id] = budget
        if len(self._budgets) > self._max_budgets:
            oldest = next(iter(self._budgets))
            del self._budgets[oldest]
        logger.info(
            "budget_manager.budget_created",
            budget_id=budget.id,
            name=name,
            limit_amount=limit_amount,
        )
        return budget

    def get_budget(self, budget_id: str) -> Budget | None:
        return self._budgets.get(budget_id)

    def list_budgets(
        self,
        team: str | None = None,
        status: BudgetStatus | None = None,
    ) -> list[Budget]:
        results = list(self._budgets.values())
        if team is not None:
            results = [b for b in results if b.team == team]
        if status is not None:
            results = [b for b in results if b.status == status]
        return results

    def record_spend(
        self,
        budget_id: str,
        amount: float,
        category: SpendCategory = SpendCategory.OTHER,
        description: str = "",
    ) -> SpendEntry | None:
        budget = self._budgets.get(budget_id)
        if budget is None:
            return None
        entry = SpendEntry(
            budget_id=budget_id,
            amount=amount,
            category=category,
            description=description,
        )
        self._entries.append(entry)
        budget.spent_amount = round(budget.spent_amount + amount, 2)
        budget.updated_at = time.time()
        self._update_status(budget)
        logger.info(
            "budget_manager.spend_recorded",
            budget_id=budget_id,
            amount=amount,
            total_spent=budget.spent_amount,
        )
        return entry

    def _update_status(self, budget: Budget) -> None:
        if budget.limit_amount <= 0:
            budget.status = BudgetStatus.ON_TRACK
            return
        ratio = budget.spent_amount / budget.limit_amount
        if ratio >= 1.0:
            budget.status = BudgetStatus.EXHAUSTED
        elif ratio >= 0.95:
            budget.status = BudgetStatus.OVER_BUDGET
        elif ratio >= self._warning_threshold:
            budget.status = BudgetStatus.WARNING
        else:
            budget.status = BudgetStatus.ON_TRACK

    def compute_burn_rate(self, budget_id: str) -> BurnRateReport | None:
        budget = self._budgets.get(budget_id)
        if budget is None:
            return None
        entries = [e for e in self._entries if e.budget_id == budget_id]
        if not entries:
            return BurnRateReport(
                budget_id=budget_id,
                budget_name=budget.name,
                limit_amount=budget.limit_amount,
                spent_amount=budget.spent_amount,
                remaining=round(budget.limit_amount - budget.spent_amount, 2),
                status=budget.status,
            )
        timestamps = [e.recorded_at for e in entries]
        span_days = max((max(timestamps) - min(timestamps)) / 86400, 1.0)
        burn_rate = round(budget.spent_amount / span_days, 2)
        remaining = round(budget.limit_amount - budget.spent_amount, 2)
        days_left = round(remaining / burn_rate, 1) if burn_rate > 0 else None
        return BurnRateReport(
            budget_id=budget_id,
            budget_name=budget.name,
            limit_amount=budget.limit_amount,
            spent_amount=budget.spent_amount,
            remaining=remaining,
            burn_rate_per_day=burn_rate,
            days_remaining=days_left,
            status=budget.status,
        )

    def check_budget_status(self, budget_id: str) -> BudgetStatus | None:
        budget = self._budgets.get(budget_id)
        if budget is None:
            return None
        return budget.status

    def adjust_limit(self, budget_id: str, new_limit: float) -> Budget | None:
        budget = self._budgets.get(budget_id)
        if budget is None:
            return None
        budget.limit_amount = new_limit
        budget.updated_at = time.time()
        self._update_status(budget)
        logger.info(
            "budget_manager.limit_adjusted",
            budget_id=budget_id,
            new_limit=new_limit,
        )
        return budget

    def list_spend_entries(
        self,
        budget_id: str,
        category: SpendCategory | None = None,
        limit: int = 100,
    ) -> list[SpendEntry]:
        results = [e for e in self._entries if e.budget_id == budget_id]
        if category is not None:
            results = [e for e in results if e.category == category]
        return results[-limit:]

    def get_over_budget_alerts(self) -> list[Budget]:
        return [
            b
            for b in self._budgets.values()
            if b.status in (BudgetStatus.OVER_BUDGET, BudgetStatus.EXHAUSTED)
        ]

    def get_stats(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        period_counts: dict[str, int] = {}
        total_limit = 0.0
        total_spent = 0.0
        for b in self._budgets.values():
            status_counts[b.status] = status_counts.get(b.status, 0) + 1
            period_counts[b.period] = period_counts.get(b.period, 0) + 1
            total_limit += b.limit_amount
            total_spent += b.spent_amount
        return {
            "total_budgets": len(self._budgets),
            "total_entries": len(self._entries),
            "total_limit": round(total_limit, 2),
            "total_spent": round(total_spent, 2),
            "status_distribution": status_counts,
            "period_distribution": period_counts,
        }
