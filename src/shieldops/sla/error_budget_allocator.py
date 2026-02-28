"""Error Budget Allocator — allocate error budgets across teams and services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AllocationStrategy(StrEnum):
    PROPORTIONAL = "proportional"
    RISK_WEIGHTED = "risk_weighted"
    EQUAL = "equal"
    PRIORITY_BASED = "priority_based"
    DYNAMIC = "dynamic"


class BudgetStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"
    FROZEN = "frozen"


class ConsumptionRate(StrEnum):
    UNDERSPENDING = "underspending"
    NORMAL = "normal"
    ELEVATED = "elevated"
    RAPID = "rapid"
    BURST = "burst"


# --- Models ---


class AllocationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    strategy: AllocationStrategy = AllocationStrategy.PROPORTIONAL
    status: BudgetStatus = BudgetStatus.HEALTHY
    consumption: ConsumptionRate = ConsumptionRate.NORMAL
    budget_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AllocationPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    strategy: AllocationStrategy = AllocationStrategy.PROPORTIONAL
    status: BudgetStatus = BudgetStatus.HEALTHY
    freeze_threshold_pct: float = 5.0
    alert_threshold_pct: float = 20.0
    created_at: float = Field(default_factory=time.time)


class BudgetAllocatorReport(BaseModel):
    total_allocations: int = 0
    total_policies: int = 0
    healthy_rate_pct: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    exhausted_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ErrorBudgetAllocator:
    """Allocate error budgets across teams and services."""

    def __init__(
        self,
        max_records: int = 200000,
        min_healthy_rate_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_healthy_rate_pct = min_healthy_rate_pct
        self._records: list[AllocationRecord] = []
        self._policies: list[AllocationPolicy] = []
        logger.info(
            "error_budget_allocator.initialized",
            max_records=max_records,
            min_healthy_rate_pct=min_healthy_rate_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_allocation(
        self,
        service_name: str,
        strategy: AllocationStrategy = (AllocationStrategy.PROPORTIONAL),
        status: BudgetStatus = BudgetStatus.HEALTHY,
        consumption: ConsumptionRate = (ConsumptionRate.NORMAL),
        budget_pct: float = 0.0,
        details: str = "",
    ) -> AllocationRecord:
        record = AllocationRecord(
            service_name=service_name,
            strategy=strategy,
            status=status,
            consumption=consumption,
            budget_pct=budget_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "error_budget_allocator.recorded",
            record_id=record.id,
            service_name=service_name,
            strategy=strategy.value,
            status=status.value,
        )
        return record

    def get_allocation(self, record_id: str) -> AllocationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_allocations(
        self,
        service_name: str | None = None,
        strategy: AllocationStrategy | None = None,
        limit: int = 50,
    ) -> list[AllocationRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if strategy is not None:
            results = [r for r in results if r.strategy == strategy]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        strategy: AllocationStrategy = (AllocationStrategy.PROPORTIONAL),
        status: BudgetStatus = BudgetStatus.HEALTHY,
        freeze_threshold_pct: float = 5.0,
        alert_threshold_pct: float = 20.0,
    ) -> AllocationPolicy:
        policy = AllocationPolicy(
            policy_name=policy_name,
            strategy=strategy,
            status=status,
            freeze_threshold_pct=freeze_threshold_pct,
            alert_threshold_pct=alert_threshold_pct,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "error_budget_allocator.policy_added",
            policy_name=policy_name,
            strategy=strategy.value,
            status=status.value,
        )
        return policy

    # -- domain operations -------------------------------------------

    def analyze_budget_health(self, service_name: str) -> dict[str, Any]:
        """Analyze budget health for a service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {
                "service_name": service_name,
                "status": "no_data",
            }
        healthy = sum(1 for r in records if r.status == BudgetStatus.HEALTHY)
        healthy_rate = round(healthy / len(records) * 100, 2)
        avg_budget = round(
            sum(r.budget_pct for r in records) / len(records),
            2,
        )
        return {
            "service_name": service_name,
            "allocation_count": len(records),
            "healthy_count": healthy,
            "healthy_rate": healthy_rate,
            "avg_budget_pct": avg_budget,
            "meets_threshold": (healthy_rate >= self._min_healthy_rate_pct),
        }

    def identify_exhausted_budgets(
        self,
    ) -> list[dict[str, Any]]:
        """Find services with exhausted budgets."""
        counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (
                BudgetStatus.EXHAUSTED,
                BudgetStatus.CRITICAL,
            ):
                counts[r.service_name] = counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "exhausted_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["exhausted_count"],
            reverse=True,
        )
        return results

    def rank_by_budget_usage(
        self,
    ) -> list[dict[str, Any]]:
        """Rank services by avg budget_pct desc."""
        svc_vals: dict[str, list[float]] = {}
        for r in self._records:
            svc_vals.setdefault(r.service_name, []).append(r.budget_pct)
        results: list[dict[str, Any]] = []
        for svc, vals in svc_vals.items():
            avg = round(sum(vals) / len(vals), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_budget_pct": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_budget_pct"],
            reverse=True,
        )
        return results

    def detect_budget_anomalies(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with budget anomalies (>3 non-HEALTHY)."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.status != BudgetStatus.HEALTHY:
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "anomaly_count": count,
                        "anomaly_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["anomaly_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> BudgetAllocatorReport:
        by_strategy: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.strategy.value] = by_strategy.get(r.strategy.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        healthy_count = sum(1 for r in self._records if r.status == BudgetStatus.HEALTHY)
        healthy_rate = (
            round(
                healthy_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        exhausted = sum(1 for r in self._records if r.status == BudgetStatus.EXHAUSTED)
        exhausted_svcs = len(self.identify_exhausted_budgets())
        recs: list[str] = []
        if healthy_rate < self._min_healthy_rate_pct:
            recs.append(
                f"Healthy rate {healthy_rate}% is below {self._min_healthy_rate_pct}% threshold"
            )
        if exhausted_svcs > 0:
            recs.append(f"{exhausted_svcs} service(s) with exhausted budgets")
        anomalies = len(self.detect_budget_anomalies())
        if anomalies > 0:
            recs.append(f"{anomalies} service(s) with budget anomalies")
        if not recs:
            recs.append("Error budget allocation is optimal")
        return BudgetAllocatorReport(
            total_allocations=len(self._records),
            total_policies=len(self._policies),
            healthy_rate_pct=healthy_rate,
            by_strategy=by_strategy,
            by_status=by_status,
            exhausted_count=exhausted,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("error_budget_allocator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        strategy_dist: dict[str, int] = {}
        for r in self._records:
            key = r.strategy.value
            strategy_dist[key] = strategy_dist.get(key, 0) + 1
        return {
            "total_allocations": len(self._records),
            "total_policies": len(self._policies),
            "min_healthy_rate_pct": (self._min_healthy_rate_pct),
            "strategy_distribution": strategy_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
