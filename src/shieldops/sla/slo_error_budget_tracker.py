"""SLO Error Budget Tracker — track SLO error budget consumption and remaining budgets."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BudgetStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"
    UNKNOWN = "unknown"


class BudgetScope(StrEnum):
    SERVICE = "service"
    ENDPOINT = "endpoint"
    REGION = "region"
    TEAM = "team"
    PLATFORM = "platform"


class BurnRate(StrEnum):
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"
    CRITICAL = "critical"
    EXCEEDED = "exceeded"


# --- Models ---


class BudgetRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_id: str = ""
    budget_status: BudgetStatus = BudgetStatus.UNKNOWN
    budget_scope: BudgetScope = BudgetScope.SERVICE
    burn_rate: BurnRate = BurnRate.NORMAL
    remaining_budget_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BudgetAllocation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_id: str = ""
    budget_status: BudgetStatus = BudgetStatus.UNKNOWN
    allocation_pct: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SLOErrorBudgetReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_allocations: int = 0
    exhausted_count: int = 0
    avg_remaining_budget_pct: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_burn_rate: dict[str, int] = Field(default_factory=dict)
    top_exhausted: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOErrorBudgetTracker:
    """Track SLO error budget consumption and remaining budgets."""

    def __init__(
        self,
        max_records: int = 200000,
        min_remaining_budget_pct: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._min_remaining_budget_pct = min_remaining_budget_pct
        self._records: list[BudgetRecord] = []
        self._allocations: list[BudgetAllocation] = []
        logger.info(
            "slo_error_budget.initialized",
            max_records=max_records,
            min_remaining_budget_pct=min_remaining_budget_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_budget(
        self,
        slo_id: str,
        budget_status: BudgetStatus = BudgetStatus.UNKNOWN,
        budget_scope: BudgetScope = BudgetScope.SERVICE,
        burn_rate: BurnRate = BurnRate.NORMAL,
        remaining_budget_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BudgetRecord:
        record = BudgetRecord(
            slo_id=slo_id,
            budget_status=budget_status,
            budget_scope=budget_scope,
            burn_rate=burn_rate,
            remaining_budget_pct=remaining_budget_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_error_budget.budget_recorded",
            record_id=record.id,
            slo_id=slo_id,
            budget_status=budget_status.value,
            budget_scope=budget_scope.value,
        )
        return record

    def get_budget(self, record_id: str) -> BudgetRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_budgets(
        self,
        status: BudgetStatus | None = None,
        scope: BudgetScope | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BudgetRecord]:
        results = list(self._records)
        if status is not None:
            results = [r for r in results if r.budget_status == status]
        if scope is not None:
            results = [r for r in results if r.budget_scope == scope]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_allocation(
        self,
        slo_id: str,
        budget_status: BudgetStatus = BudgetStatus.UNKNOWN,
        allocation_pct: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BudgetAllocation:
        allocation = BudgetAllocation(
            slo_id=slo_id,
            budget_status=budget_status,
            allocation_pct=allocation_pct,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._allocations.append(allocation)
        if len(self._allocations) > self._max_records:
            self._allocations = self._allocations[-self._max_records :]
        logger.info(
            "slo_error_budget.allocation_added",
            slo_id=slo_id,
            budget_status=budget_status.value,
            allocation_pct=allocation_pct,
        )
        return allocation

    # -- domain operations --------------------------------------------------

    def analyze_budget_distribution(self) -> dict[str, Any]:
        """Group by budget_status; return count and avg remaining_budget_pct per status."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.budget_status.value
            status_data.setdefault(key, []).append(r.remaining_budget_pct)
        result: dict[str, Any] = {}
        for status, pcts in status_data.items():
            result[status] = {
                "count": len(pcts),
                "avg_remaining_budget_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_exhausted_budgets(self) -> list[dict[str, Any]]:
        """Return records where budget_status is EXHAUSTED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.budget_status == BudgetStatus.EXHAUSTED:
                results.append(
                    {
                        "record_id": r.id,
                        "slo_id": r.slo_id,
                        "budget_scope": r.budget_scope.value,
                        "remaining_budget_pct": r.remaining_budget_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_remaining_budget(self) -> list[dict[str, Any]]:
        """Group by service, avg remaining_budget_pct, sort ascending (lowest first)."""
        svc_pcts: dict[str, list[float]] = {}
        for r in self._records:
            svc_pcts.setdefault(r.service, []).append(r.remaining_budget_pct)
        results: list[dict[str, Any]] = []
        for service, pcts in svc_pcts.items():
            results.append(
                {
                    "service": service,
                    "avg_remaining_budget_pct": round(sum(pcts) / len(pcts), 2),
                    "budget_count": len(pcts),
                }
            )
        results.sort(key=lambda x: x["avg_remaining_budget_pct"])
        return results

    def detect_budget_trends(self) -> dict[str, Any]:
        """Split-half comparison on allocation_pct; delta threshold 5.0."""
        if len(self._allocations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.allocation_pct for a in self._allocations]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> SLOErrorBudgetReport:
        by_status: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        by_burn_rate: dict[str, int] = {}
        for r in self._records:
            by_status[r.budget_status.value] = by_status.get(r.budget_status.value, 0) + 1
            by_scope[r.budget_scope.value] = by_scope.get(r.budget_scope.value, 0) + 1
            by_burn_rate[r.burn_rate.value] = by_burn_rate.get(r.burn_rate.value, 0) + 1
        exhausted_count = sum(1 for r in self._records if r.budget_status == BudgetStatus.EXHAUSTED)
        avg_remaining_budget_pct = (
            round(
                sum(r.remaining_budget_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        rankings = self.rank_by_remaining_budget()
        top_exhausted = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if exhausted_count > 0:
            recs.append(f"{exhausted_count} exhausted budget(s) detected — review SLO targets")
        if avg_remaining_budget_pct < self._min_remaining_budget_pct and self._records:
            recs.append(
                f"Average remaining budget {avg_remaining_budget_pct}% is below "
                f"threshold ({self._min_remaining_budget_pct}%)"
            )
        if not recs:
            recs.append("SLO error budget levels are acceptable")
        return SLOErrorBudgetReport(
            total_records=len(self._records),
            total_allocations=len(self._allocations),
            exhausted_count=exhausted_count,
            avg_remaining_budget_pct=avg_remaining_budget_pct,
            by_status=by_status,
            by_scope=by_scope,
            by_burn_rate=by_burn_rate,
            top_exhausted=top_exhausted,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._allocations.clear()
        logger.info("slo_error_budget.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.budget_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_allocations": len(self._allocations),
            "min_remaining_budget_pct": self._min_remaining_budget_pct,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
