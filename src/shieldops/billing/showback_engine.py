"""Showback Engine — generate showback reports for internal consumers."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ShowbackCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    PLATFORM_SERVICES = "platform_services"


class ShowbackGranularity(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class ShowbackAccuracy(StrEnum):
    EXACT = "exact"
    ESTIMATED = "estimated"
    PROJECTED = "projected"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


# --- Models ---


class ShowbackRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    consumer_id: str = ""
    showback_category: ShowbackCategory = ShowbackCategory.COMPUTE
    showback_granularity: ShowbackGranularity = ShowbackGranularity.MONTHLY
    showback_accuracy: ShowbackAccuracy = ShowbackAccuracy.UNKNOWN
    cost_amount: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ShowbackAllocation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    consumer_id: str = ""
    showback_category: ShowbackCategory = ShowbackCategory.COMPUTE
    allocation_amount: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ShowbackReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_allocations: int = 0
    over_budget_count: int = 0
    avg_cost_amount: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_granularity: dict[str, int] = Field(default_factory=dict)
    by_accuracy: dict[str, int] = Field(default_factory=dict)
    top_consumers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ShowbackEngine:
    """Generate showback reports for internal consumers, cost visibility without chargeback."""

    def __init__(
        self,
        max_records: int = 200000,
        max_over_budget_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_over_budget_pct = max_over_budget_pct
        self._records: list[ShowbackRecord] = []
        self._allocations: list[ShowbackAllocation] = []
        logger.info(
            "showback_engine.initialized",
            max_records=max_records,
            max_over_budget_pct=max_over_budget_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_showback(
        self,
        consumer_id: str,
        showback_category: ShowbackCategory = ShowbackCategory.COMPUTE,
        showback_granularity: ShowbackGranularity = ShowbackGranularity.MONTHLY,
        showback_accuracy: ShowbackAccuracy = ShowbackAccuracy.UNKNOWN,
        cost_amount: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ShowbackRecord:
        record = ShowbackRecord(
            consumer_id=consumer_id,
            showback_category=showback_category,
            showback_granularity=showback_granularity,
            showback_accuracy=showback_accuracy,
            cost_amount=cost_amount,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "showback_engine.showback_recorded",
            record_id=record.id,
            consumer_id=consumer_id,
            showback_category=showback_category.value,
            showback_granularity=showback_granularity.value,
        )
        return record

    def get_showback(self, record_id: str) -> ShowbackRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_showbacks(
        self,
        category: ShowbackCategory | None = None,
        granularity: ShowbackGranularity | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ShowbackRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.showback_category == category]
        if granularity is not None:
            results = [r for r in results if r.showback_granularity == granularity]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_allocation(
        self,
        consumer_id: str,
        showback_category: ShowbackCategory = ShowbackCategory.COMPUTE,
        allocation_amount: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ShowbackAllocation:
        allocation = ShowbackAllocation(
            consumer_id=consumer_id,
            showback_category=showback_category,
            allocation_amount=allocation_amount,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._allocations.append(allocation)
        if len(self._allocations) > self._max_records:
            self._allocations = self._allocations[-self._max_records :]
        logger.info(
            "showback_engine.allocation_added",
            consumer_id=consumer_id,
            showback_category=showback_category.value,
            allocation_amount=allocation_amount,
        )
        return allocation

    # -- domain operations --------------------------------------------------

    def analyze_cost_distribution(self) -> dict[str, Any]:
        """Group by showback_category; return count and avg cost_amount."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.showback_category.value
            cat_data.setdefault(key, []).append(r.cost_amount)
        result: dict[str, Any] = {}
        for cat, amounts in cat_data.items():
            result[cat] = {
                "count": len(amounts),
                "avg_cost_amount": round(sum(amounts) / len(amounts), 2),
            }
        return result

    def identify_over_budget_consumers(self) -> list[dict[str, Any]]:
        """Return allocations where breached is True."""
        results: list[dict[str, Any]] = []
        for a in self._allocations:
            if a.breached:
                results.append(
                    {
                        "allocation_id": a.id,
                        "consumer_id": a.consumer_id,
                        "showback_category": a.showback_category.value,
                        "allocation_amount": a.allocation_amount,
                        "threshold": a.threshold,
                        "description": a.description,
                    }
                )
        return results

    def rank_by_cost_amount(self) -> list[dict[str, Any]]:
        """Group by service, total cost_amount, sort descending."""
        svc_costs: dict[str, list[float]] = {}
        for r in self._records:
            svc_costs.setdefault(r.service, []).append(r.cost_amount)
        results: list[dict[str, Any]] = []
        for svc, amounts in svc_costs.items():
            results.append(
                {
                    "service": svc,
                    "total_cost_amount": round(sum(amounts), 2),
                    "record_count": len(amounts),
                }
            )
        results.sort(key=lambda x: x["total_cost_amount"], reverse=True)
        return results

    def detect_cost_trends(self) -> dict[str, Any]:
        """Split-half comparison on allocation_amount; delta threshold 5.0."""
        if len(self._allocations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        amounts = [a.allocation_amount for a in self._allocations]
        mid = len(amounts) // 2
        first_half = amounts[:mid]
        second_half = amounts[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ShowbackReport:
        by_category: dict[str, int] = {}
        by_granularity: dict[str, int] = {}
        by_accuracy: dict[str, int] = {}
        for r in self._records:
            by_category[r.showback_category.value] = (
                by_category.get(r.showback_category.value, 0) + 1
            )
            by_granularity[r.showback_granularity.value] = (
                by_granularity.get(r.showback_granularity.value, 0) + 1
            )
            by_accuracy[r.showback_accuracy.value] = (
                by_accuracy.get(r.showback_accuracy.value, 0) + 1
            )
        over_budget = self.identify_over_budget_consumers()
        over_budget_count = len(over_budget)
        avg_cost_amount = (
            round(sum(r.cost_amount for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_cost_amount()
        top_consumers = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if over_budget_count > 0:
            recs.append(
                f"{over_budget_count} over-budget consumer(s) detected — review allocations"
            )
        if self._allocations:
            over_pct = round(
                over_budget_count / len(self._allocations) * 100,
                2,
            )
            if over_pct > self._max_over_budget_pct:
                recs.append(
                    f"Over-budget rate {over_pct}% exceeds threshold ({self._max_over_budget_pct}%)"
                )
        if not recs:
            recs.append("Showback cost levels are acceptable")
        return ShowbackReport(
            total_records=len(self._records),
            total_allocations=len(self._allocations),
            over_budget_count=over_budget_count,
            avg_cost_amount=avg_cost_amount,
            by_category=by_category,
            by_granularity=by_granularity,
            by_accuracy=by_accuracy,
            top_consumers=top_consumers,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._allocations.clear()
        logger.info("showback_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.showback_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_allocations": len(self._allocations),
            "max_over_budget_pct": self._max_over_budget_pct,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
