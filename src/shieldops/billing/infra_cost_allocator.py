"""Infrastructure Cost Allocator — distribute infrastructure costs across teams and services."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AllocationMethod(StrEnum):
    DIRECT = "direct"
    PROPORTIONAL = "proportional"
    USAGE_BASED = "usage_based"
    FIXED_SPLIT = "fixed_split"
    HYBRID = "hybrid"


class CostCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    PLATFORM_SERVICES = "platform_services"


class AllocationAccuracy(StrEnum):
    EXACT = "exact"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    ESTIMATED = "estimated"


# --- Models ---


class AllocationRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    resource_id: str = ""
    resource_name: str = ""
    team: str = ""
    service: str = ""
    cost_category: CostCategory = CostCategory.COMPUTE
    allocation_method: AllocationMethod = AllocationMethod.DIRECT
    total_cost: float = 0.0
    allocated_cost: float = 0.0
    unallocated_cost: float = 0.0
    accuracy: AllocationAccuracy = AllocationAccuracy.HIGH
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AllocationSplit(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    resource_id: str = ""
    team: str = ""
    split_pct: float = 0.0
    split_cost: float = 0.0
    allocation_method: AllocationMethod = AllocationMethod.PROPORTIONAL
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InfraCostAllocatorReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_splits: int = 0
    total_cost: float = 0.0
    total_allocated: float = 0.0
    total_unallocated: float = 0.0
    unallocated_pct: float = 0.0
    by_cost_category: dict[str, float] = Field(default_factory=dict)
    by_allocation_method: dict[str, int] = Field(default_factory=dict)
    by_accuracy: dict[str, int] = Field(default_factory=dict)
    top_cost_teams: list[str] = Field(default_factory=list)
    unallocated_resources: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class InfrastructureCostAllocator:
    """Distribute infrastructure costs accurately across teams, services, and cost centers."""

    def __init__(
        self,
        max_records: int = 200000,
        max_unallocated_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_unallocated_pct = max_unallocated_pct
        self._records: list[AllocationRecord] = []
        self._splits: list[AllocationSplit] = []
        logger.info(
            "infra_cost_allocator.initialized",
            max_records=max_records,
            max_unallocated_pct=max_unallocated_pct,
        )

    # -- CRUD --

    def record_allocation(
        self,
        resource_id: str,
        resource_name: str = "",
        team: str = "",
        service: str = "",
        cost_category: CostCategory = CostCategory.COMPUTE,
        allocation_method: AllocationMethod = AllocationMethod.DIRECT,
        total_cost: float = 0.0,
        allocated_cost: float = 0.0,
        unallocated_cost: float = 0.0,
        accuracy: AllocationAccuracy = AllocationAccuracy.HIGH,
        details: str = "",
    ) -> AllocationRecord:
        record = AllocationRecord(
            resource_id=resource_id,
            resource_name=resource_name,
            team=team,
            service=service,
            cost_category=cost_category,
            allocation_method=allocation_method,
            total_cost=total_cost,
            allocated_cost=allocated_cost,
            unallocated_cost=unallocated_cost,
            accuracy=accuracy,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "infra_cost_allocator.recorded",
            record_id=record.id,
            resource_id=resource_id,
            total_cost=total_cost,
            team=team,
        )
        return record

    def get_allocation(self, record_id: str) -> AllocationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_allocations(
        self,
        cost_category: CostCategory | None = None,
        allocation_method: AllocationMethod | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AllocationRecord]:
        results = list(self._records)
        if cost_category is not None:
            results = [r for r in results if r.cost_category == cost_category]
        if allocation_method is not None:
            results = [r for r in results if r.allocation_method == allocation_method]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_split(
        self,
        resource_id: str,
        team: str = "",
        split_pct: float = 0.0,
        split_cost: float = 0.0,
        allocation_method: AllocationMethod = AllocationMethod.PROPORTIONAL,
        description: str = "",
    ) -> AllocationSplit:
        split = AllocationSplit(
            resource_id=resource_id,
            team=team,
            split_pct=split_pct,
            split_cost=split_cost,
            allocation_method=allocation_method,
            description=description,
        )
        self._splits.append(split)
        if len(self._splits) > self._max_records:
            self._splits = self._splits[-self._max_records :]
        logger.info(
            "infra_cost_allocator.split_added",
            split_id=split.id,
            resource_id=resource_id,
            team=team,
            split_pct=split_pct,
        )
        return split

    # -- Domain operations --

    def analyze_allocation_by_team(self) -> list[dict[str, Any]]:
        """Aggregate cost allocation metrics per team."""
        team_records: dict[str, list[AllocationRecord]] = {}
        for r in self._records:
            if not r.team:
                continue
            team_records.setdefault(r.team, []).append(r)
        results: list[dict[str, Any]] = []
        for team, records in team_records.items():
            total = sum(r.total_cost for r in records)
            allocated = sum(r.allocated_cost for r in records)
            unallocated = sum(r.unallocated_cost for r in records)
            alloc_pct = round(allocated / total * 100, 2) if total else 0.0
            categories: dict[str, float] = {}
            for r in records:
                categories[r.cost_category.value] = (
                    categories.get(r.cost_category.value, 0.0) + r.total_cost
                )
            results.append(
                {
                    "team": team,
                    "total_cost": round(total, 2),
                    "allocated_cost": round(allocated, 2),
                    "unallocated_cost": round(unallocated, 2),
                    "allocation_pct": alloc_pct,
                    "resource_count": len(records),
                    "by_category": categories,
                }
            )
        results.sort(key=lambda x: x["total_cost"], reverse=True)
        return results

    def identify_unallocated_costs(self) -> list[dict[str, Any]]:
        """Find resources where unallocated cost exceeds threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.total_cost <= 0:
                continue
            unalloc_pct = round(r.unallocated_cost / r.total_cost * 100, 2)
            if unalloc_pct > self._max_unallocated_pct:
                results.append(
                    {
                        "id": r.id,
                        "resource_id": r.resource_id,
                        "resource_name": r.resource_name,
                        "team": r.team,
                        "total_cost": r.total_cost,
                        "unallocated_cost": r.unallocated_cost,
                        "unallocated_pct": unalloc_pct,
                        "threshold_pct": self._max_unallocated_pct,
                    }
                )
        results.sort(key=lambda x: x["unallocated_cost"], reverse=True)
        return results

    def rank_by_cost_share(self) -> list[dict[str, Any]]:
        """Rank teams by their share of total infrastructure cost."""
        total_cost = sum(r.total_cost for r in self._records)
        team_cost: dict[str, float] = {}
        for r in self._records:
            label = r.team if r.team else "_untagged"
            team_cost[label] = team_cost.get(label, 0.0) + r.total_cost
        results: list[dict[str, Any]] = []
        for team, cost in team_cost.items():
            share_pct = round(cost / total_cost * 100, 2) if total_cost else 0.0
            results.append(
                {
                    "team": team,
                    "total_cost": round(cost, 2),
                    "cost_share_pct": share_pct,
                }
            )
        results.sort(key=lambda x: x["total_cost"], reverse=True)
        return results

    def detect_allocation_drift(self) -> dict[str, Any]:
        """Detect whether unallocated cost percentage is drifting over time."""
        if len(self._records) < 4:
            return {"drift_detected": False, "reason": "insufficient_data"}
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def _unalloc_pct(records: list[AllocationRecord]) -> float:
            total = sum(r.total_cost for r in records)
            unalloc = sum(r.unallocated_cost for r in records)
            return round(unalloc / total * 100, 2) if total else 0.0

        first_pct = _unalloc_pct(first_half)
        second_pct = _unalloc_pct(second_half)
        delta = round(second_pct - first_pct, 2)
        drift_detected = delta > 5.0
        logger.info(
            "infra_cost_allocator.drift_detected",
            drift_detected=drift_detected,
            first_pct=first_pct,
            second_pct=second_pct,
        )
        return {
            "drift_detected": drift_detected,
            "first_half_unallocated_pct": first_pct,
            "second_half_unallocated_pct": second_pct,
            "delta_pct": delta,
            "total_records": len(self._records),
        }

    # -- Report --

    def generate_report(self) -> InfraCostAllocatorReport:
        by_category: dict[str, float] = {}
        by_method: dict[str, int] = {}
        by_accuracy: dict[str, int] = {}
        total_cost = 0.0
        total_allocated = 0.0
        total_unallocated = 0.0
        for r in self._records:
            by_category[r.cost_category.value] = (
                by_category.get(r.cost_category.value, 0.0) + r.total_cost
            )
            by_method[r.allocation_method.value] = by_method.get(r.allocation_method.value, 0) + 1
            by_accuracy[r.accuracy.value] = by_accuracy.get(r.accuracy.value, 0) + 1
            total_cost += r.total_cost
            total_allocated += r.allocated_cost
            total_unallocated += r.unallocated_cost
        unallocated_pct = round(total_unallocated / total_cost * 100, 2) if total_cost else 0.0
        team_costs = self.analyze_allocation_by_team()
        top_teams = [t["team"] for t in team_costs[:5]]
        unalloc_resources = self.identify_unallocated_costs()
        unalloc_resource_ids = [u["resource_id"] for u in unalloc_resources[:10]]
        recs: list[str] = []
        if unallocated_pct > self._max_unallocated_pct:
            recs.append(
                f"Unallocated cost {unallocated_pct}% exceeds target"
                f" {self._max_unallocated_pct}% — tag untagged resources"
            )
        if unalloc_resource_ids:
            recs.append(f"{len(unalloc_resource_ids)} resource(s) with high unallocated costs")
        low_accuracy = by_accuracy.get(AllocationAccuracy.LOW.value, 0) + by_accuracy.get(
            AllocationAccuracy.ESTIMATED.value, 0
        )
        if low_accuracy > 0:
            recs.append(
                f"{low_accuracy} allocation(s) with LOW/ESTIMATED accuracy — review tagging"
            )
        if not recs:
            recs.append("Cost allocation is within healthy targets")
        return InfraCostAllocatorReport(
            total_records=len(self._records),
            total_splits=len(self._splits),
            total_cost=round(total_cost, 2),
            total_allocated=round(total_allocated, 2),
            total_unallocated=round(total_unallocated, 2),
            unallocated_pct=unallocated_pct,
            by_cost_category=by_category,
            by_allocation_method=by_method,
            by_accuracy=by_accuracy,
            top_cost_teams=top_teams,
            unallocated_resources=unalloc_resource_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._splits.clear()
        logger.info("infra_cost_allocator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, float] = {}
        total_cost = 0.0
        total_unallocated = 0.0
        for r in self._records:
            category_dist[r.cost_category.value] = (
                category_dist.get(r.cost_category.value, 0.0) + r.total_cost
            )
            total_cost += r.total_cost
            total_unallocated += r.unallocated_cost
        unallocated_pct = round(total_unallocated / total_cost * 100, 2) if total_cost else 0.0
        return {
            "total_records": len(self._records),
            "total_splits": len(self._splits),
            "total_cost": round(total_cost, 2),
            "total_unallocated": round(total_unallocated, 2),
            "unallocated_pct": unallocated_pct,
            "max_unallocated_pct": self._max_unallocated_pct,
            "category_distribution": category_dist,
            "unique_teams": len({r.team for r in self._records if r.team}),
        }
