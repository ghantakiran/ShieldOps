"""Spend Allocation Engine — shared infrastructure cost allocation across teams/features."""

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
    USAGE_BASED = "usage_based"
    HEADCOUNT_BASED = "headcount_based"
    EVEN_SPLIT = "even_split"
    WEIGHTED = "weighted"
    CUSTOM_FORMULA = "custom_formula"


class CostCategory(StrEnum):
    SHARED_INFRASTRUCTURE = "shared_infrastructure"
    DEDICATED_RESOURCES = "dedicated_resources"
    PLATFORM_OVERHEAD = "platform_overhead"
    NETWORK_TRANSFER = "network_transfer"
    SUPPORT_COSTS = "support_costs"
    LICENSE_FEES = "license_fees"


class ChargebackModel(StrEnum):
    SHOWBACK = "showback"
    CHARGEBACK = "chargeback"
    HYBRID = "hybrid"
    DIRECT = "direct"
    TIERED = "tiered"


# --- Models ---


class SharedCostPool(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pool_name: str = ""
    total_cost: float = 0.0
    category: CostCategory = CostCategory.SHARED_INFRASTRUCTURE
    strategy: AllocationStrategy = AllocationStrategy.EVEN_SPLIT
    chargeback_model: ChargebackModel = ChargebackModel.SHOWBACK
    created_at: float = Field(default_factory=time.time)


class TeamAllocation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pool_id: str = ""
    team_name: str = ""
    allocation_pct: float = 0.0
    allocated_amount: float = 0.0
    usage_units: float = 0.0
    headcount: int = 0
    created_at: float = Field(default_factory=time.time)


class AllocationReport(BaseModel):
    total_pools: int = 0
    total_cost_allocated: float = 0.0
    team_count: int = 0
    strategy_distribution: dict[str, int] = Field(default_factory=dict)
    largest_pool: str = ""
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SpendAllocationEngine:
    """Shared infrastructure cost allocation across teams, features, and business units."""

    def __init__(
        self,
        max_pools: int = 50000,
        min_allocation_threshold: float = 0.01,
    ) -> None:
        self._max_pools = max_pools
        self._min_allocation_threshold = min_allocation_threshold
        self._pools: list[SharedCostPool] = []
        self._allocations: list[TeamAllocation] = []
        logger.info(
            "spend_allocation.initialized",
            max_pools=max_pools,
            min_allocation_threshold=min_allocation_threshold,
        )

    def register_pool(
        self,
        pool_name: str,
        total_cost: float,
        category: CostCategory = CostCategory.SHARED_INFRASTRUCTURE,
        strategy: AllocationStrategy = AllocationStrategy.EVEN_SPLIT,
        chargeback_model: ChargebackModel = ChargebackModel.SHOWBACK,
    ) -> SharedCostPool:
        """Register a shared cost pool for allocation."""
        pool = SharedCostPool(
            pool_name=pool_name,
            total_cost=total_cost,
            category=category,
            strategy=strategy,
            chargeback_model=chargeback_model,
        )
        self._pools.append(pool)
        if len(self._pools) > self._max_pools:
            self._pools = self._pools[-self._max_pools :]
        logger.info(
            "spend_allocation.pool_registered",
            pool_id=pool.id,
            pool_name=pool_name,
            total_cost=total_cost,
            strategy=strategy,
        )
        return pool

    def get_pool(self, pool_id: str) -> SharedCostPool | None:
        """Retrieve a single cost pool by ID."""
        for p in self._pools:
            if p.id == pool_id:
                return p
        return None

    def list_pools(
        self,
        category: CostCategory | None = None,
        strategy: AllocationStrategy | None = None,
        limit: int = 100,
    ) -> list[SharedCostPool]:
        """List cost pools with optional filtering by category and strategy."""
        results = list(self._pools)
        if category is not None:
            results = [p for p in results if p.category == category]
        if strategy is not None:
            results = [p for p in results if p.strategy == strategy]
        return results[-limit:]

    def add_team_allocation(
        self,
        pool_id: str,
        team_name: str,
        allocation_pct: float = 0.0,
        usage_units: float = 0.0,
        headcount: int = 0,
    ) -> TeamAllocation | None:
        """Add a team allocation to a cost pool.

        Auto-calculates allocated_amount from pool total * allocation_pct / 100.
        """
        pool = self.get_pool(pool_id)
        if pool is None:
            logger.warning(
                "spend_allocation.pool_not_found",
                pool_id=pool_id,
            )
            return None

        allocated_amount = round(pool.total_cost * allocation_pct / 100, 2)

        allocation = TeamAllocation(
            pool_id=pool_id,
            team_name=team_name,
            allocation_pct=allocation_pct,
            allocated_amount=allocated_amount,
            usage_units=usage_units,
            headcount=headcount,
        )
        self._allocations.append(allocation)
        if len(self._allocations) > self._max_pools * 10:
            self._allocations = self._allocations[-(self._max_pools * 10) :]
        logger.info(
            "spend_allocation.team_allocation_added",
            allocation_id=allocation.id,
            pool_id=pool_id,
            team_name=team_name,
            allocation_pct=allocation_pct,
            allocated_amount=allocated_amount,
        )
        return allocation

    def calculate_allocations(self, pool_id: str) -> list[TeamAllocation]:
        """Recalculate all allocations for a pool based on its strategy.

        Strategies:
        - EVEN_SPLIT: equal shares among all teams in the pool
        - USAGE_BASED: proportional to each team's usage_units
        - HEADCOUNT_BASED: proportional to each team's headcount
        - WEIGHTED: use each team's allocation_pct directly
        - CUSTOM_FORMULA: falls back to allocation_pct (weighted)
        """
        pool = self.get_pool(pool_id)
        if pool is None:
            return []

        pool_allocations = [a for a in self._allocations if a.pool_id == pool_id]
        if not pool_allocations:
            return []

        team_count = len(pool_allocations)

        if pool.strategy == AllocationStrategy.EVEN_SPLIT:
            share = round(pool.total_cost / team_count, 2) if team_count > 0 else 0.0
            pct = round(100.0 / team_count, 4) if team_count > 0 else 0.0
            for alloc in pool_allocations:
                alloc.allocated_amount = share
                alloc.allocation_pct = pct

        elif pool.strategy == AllocationStrategy.USAGE_BASED:
            total_usage = sum(a.usage_units for a in pool_allocations)
            for alloc in pool_allocations:
                if total_usage > 0:
                    proportion = alloc.usage_units / total_usage
                    alloc.allocation_pct = round(proportion * 100, 4)
                    alloc.allocated_amount = round(pool.total_cost * proportion, 2)
                else:
                    # Fall back to even split if no usage data
                    alloc.allocation_pct = round(100.0 / team_count, 4)
                    alloc.allocated_amount = round(pool.total_cost / team_count, 2)

        elif pool.strategy == AllocationStrategy.HEADCOUNT_BASED:
            total_headcount = sum(a.headcount for a in pool_allocations)
            for alloc in pool_allocations:
                if total_headcount > 0:
                    proportion = alloc.headcount / total_headcount
                    alloc.allocation_pct = round(proportion * 100, 4)
                    alloc.allocated_amount = round(pool.total_cost * proportion, 2)
                else:
                    alloc.allocation_pct = round(100.0 / team_count, 4)
                    alloc.allocated_amount = round(pool.total_cost / team_count, 2)

        elif pool.strategy in (AllocationStrategy.WEIGHTED, AllocationStrategy.CUSTOM_FORMULA):
            total_pct = sum(a.allocation_pct for a in pool_allocations)
            for alloc in pool_allocations:
                if total_pct > 0:
                    normalized_pct = alloc.allocation_pct / total_pct * 100
                    alloc.allocation_pct = round(normalized_pct, 4)
                    alloc.allocated_amount = round(pool.total_cost * normalized_pct / 100, 2)
                else:
                    alloc.allocation_pct = round(100.0 / team_count, 4)
                    alloc.allocated_amount = round(pool.total_cost / team_count, 2)

        logger.info(
            "spend_allocation.allocations_calculated",
            pool_id=pool_id,
            strategy=pool.strategy,
            team_count=team_count,
        )
        return pool_allocations

    def get_team_total_spend(self, team_name: str) -> dict[str, Any]:
        """Sum a team's allocated amounts across all pools."""
        team_allocs = [a for a in self._allocations if a.team_name == team_name]
        total_allocated = sum(a.allocated_amount for a in team_allocs)

        pool_breakdown: list[dict[str, Any]] = []
        for alloc in team_allocs:
            pool = self.get_pool(alloc.pool_id)
            pool_name = pool.pool_name if pool else "unknown"
            pool_breakdown.append(
                {
                    "pool_id": alloc.pool_id,
                    "pool_name": pool_name,
                    "allocation_pct": alloc.allocation_pct,
                    "allocated_amount": alloc.allocated_amount,
                }
            )

        return {
            "team_name": team_name,
            "total_allocated": round(total_allocated, 2),
            "pool_count": len(team_allocs),
            "pool_breakdown": pool_breakdown,
        }

    def compare_team_allocations(self) -> list[dict[str, Any]]:
        """Compare per-team totals across all pools, sorted descending by spend."""
        team_totals: dict[str, dict[str, Any]] = {}
        for alloc in self._allocations:
            if alloc.team_name not in team_totals:
                team_totals[alloc.team_name] = {
                    "team_name": alloc.team_name,
                    "total_allocated": 0.0,
                    "pool_count": 0,
                    "total_usage_units": 0.0,
                    "total_headcount": 0,
                }
            entry = team_totals[alloc.team_name]
            entry["total_allocated"] += alloc.allocated_amount
            entry["pool_count"] += 1
            entry["total_usage_units"] += alloc.usage_units
            entry["total_headcount"] += alloc.headcount

        for entry in team_totals.values():
            entry["total_allocated"] = round(entry["total_allocated"], 2)
            entry["total_usage_units"] = round(entry["total_usage_units"], 2)
            # Cost per headcount
            if entry["total_headcount"] > 0:
                entry["cost_per_headcount"] = round(
                    entry["total_allocated"] / entry["total_headcount"], 2
                )
            else:
                entry["cost_per_headcount"] = 0.0

        comparisons = sorted(team_totals.values(), key=lambda x: x["total_allocated"], reverse=True)
        return comparisons

    def detect_allocation_anomalies(self) -> list[dict[str, Any]]:
        """Detect allocation anomalies.

        Flags:
        - Teams consuming >50% of any single pool
        - Teams with allocation below min_allocation_threshold
        """
        anomalies: list[dict[str, Any]] = []

        # Check for dominant allocations (>50% of a pool)
        for pool in self._pools:
            pool_allocs = [a for a in self._allocations if a.pool_id == pool.id]
            for alloc in pool_allocs:
                if alloc.allocation_pct > 50.0:
                    anomalies.append(
                        {
                            "type": "dominant_allocation",
                            "team_name": alloc.team_name,
                            "pool_id": pool.id,
                            "pool_name": pool.pool_name,
                            "allocation_pct": alloc.allocation_pct,
                            "allocated_amount": alloc.allocated_amount,
                            "description": (
                                f"Team {alloc.team_name} consumes {alloc.allocation_pct:.1f}% "
                                f"of pool {pool.pool_name} — consider dedicated resource allocation"
                            ),
                        }
                    )

        # Check for below-threshold allocations
        for alloc in self._allocations:
            if 0 < alloc.allocation_pct < self._min_allocation_threshold * 100:
                alloc_pool = self.get_pool(alloc.pool_id)
                pool_name = alloc_pool.pool_name if alloc_pool else "unknown"
                anomalies.append(
                    {
                        "type": "below_threshold",
                        "team_name": alloc.team_name,
                        "pool_id": alloc.pool_id,
                        "pool_name": pool_name,
                        "allocation_pct": alloc.allocation_pct,
                        "allocated_amount": alloc.allocated_amount,
                        "description": (
                            f"Team {alloc.team_name} has only {alloc.allocation_pct:.2f}% "
                            f"of pool {pool_name} — below minimum threshold, consider merging"
                        ),
                    }
                )

        logger.info(
            "spend_allocation.anomalies_detected",
            anomaly_count=len(anomalies),
        )
        return anomalies

    def generate_allocation_report(self) -> AllocationReport:
        """Generate a comprehensive allocation report across all pools and teams."""
        total_cost_allocated = sum(a.allocated_amount for a in self._allocations)
        unique_teams = {a.team_name for a in self._allocations}

        # Strategy distribution
        strategy_dist: dict[str, int] = {}
        for pool in self._pools:
            key = pool.strategy.value
            strategy_dist[key] = strategy_dist.get(key, 0) + 1

        # Find largest pool
        largest_pool = ""
        largest_cost = 0.0
        for pool in self._pools:
            if pool.total_cost > largest_cost:
                largest_cost = pool.total_cost
                largest_pool = pool.pool_name

        # Build recommendations
        recommendations: list[str] = []
        anomalies = self.detect_allocation_anomalies()
        dominant = [a for a in anomalies if a["type"] == "dominant_allocation"]
        if dominant:
            recommendations.append(
                f"{len(dominant)} team(s) dominate their cost pools (>50%) — "
                f"consider splitting into dedicated and shared tiers"
            )

        below = [a for a in anomalies if a["type"] == "below_threshold"]
        if below:
            recommendations.append(
                f"{len(below)} allocation(s) below minimum threshold — "
                f"consolidate small allocations to reduce accounting overhead"
            )

        even_pools = [p for p in self._pools if p.strategy == AllocationStrategy.EVEN_SPLIT]
        if even_pools and len(even_pools) > len(self._pools) / 2:
            recommendations.append(
                "Majority of pools use EVEN_SPLIT — consider migrating to USAGE_BASED "
                "for more equitable cost distribution"
            )

        if not unique_teams:
            recommendations.append(
                "No team allocations found — add teams to cost pools to enable chargeback"
            )

        report = AllocationReport(
            total_pools=len(self._pools),
            total_cost_allocated=round(total_cost_allocated, 2),
            team_count=len(unique_teams),
            strategy_distribution=strategy_dist,
            largest_pool=largest_pool,
            recommendations=recommendations,
        )
        logger.info(
            "spend_allocation.report_generated",
            total_pools=len(self._pools),
            total_cost_allocated=round(total_cost_allocated, 2),
            team_count=len(unique_teams),
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored pools and allocations."""
        self._pools.clear()
        self._allocations.clear()
        logger.info("spend_allocation.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about pools and allocations."""
        category_counts: dict[str, int] = {}
        strategy_counts: dict[str, int] = {}
        for p in self._pools:
            category_counts[p.category.value] = category_counts.get(p.category.value, 0) + 1
            strategy_counts[p.strategy.value] = strategy_counts.get(p.strategy.value, 0) + 1

        team_counts: dict[str, int] = {}
        for a in self._allocations:
            team_counts[a.team_name] = team_counts.get(a.team_name, 0) + 1

        return {
            "total_pools": len(self._pools),
            "total_allocations": len(self._allocations),
            "unique_teams": len(team_counts),
            "category_distribution": category_counts,
            "strategy_distribution": strategy_counts,
            "team_allocation_counts": team_counts,
            "max_pools": self._max_pools,
            "min_allocation_threshold": self._min_allocation_threshold,
        }
