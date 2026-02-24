"""Cost Chargeback Engine — allocate shared costs to teams/departments."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AllocationMethod(StrEnum):
    PROPORTIONAL_USAGE = "proportional_usage"
    EQUAL_SPLIT = "equal_split"
    HEADCOUNT_BASED = "headcount_based"
    REVENUE_WEIGHTED = "revenue_weighted"
    CUSTOM_FORMULA = "custom_formula"


class ChargebackStatus(StrEnum):
    DRAFT = "draft"
    CALCULATED = "calculated"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    INVOICED = "invoiced"


class CostCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    LICENSING = "licensing"
    SUPPORT = "support"


# --- Models ---


class ChargebackRecord(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    team: str = ""
    department: str = ""
    cost_category: CostCategory = CostCategory.COMPUTE
    total_cost: float = 0.0
    allocated_cost: float = 0.0
    allocation_method: AllocationMethod = AllocationMethod.PROPORTIONAL_USAGE
    billing_period: str = ""
    status: ChargebackStatus = ChargebackStatus.DRAFT
    created_at: float = Field(
        default_factory=time.time,
    )


class AllocationRule(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    cost_category: CostCategory = CostCategory.COMPUTE
    method: AllocationMethod = AllocationMethod.PROPORTIONAL_USAGE
    team: str = ""
    weight: float = 0.0
    is_active: bool = True
    created_at: float = Field(
        default_factory=time.time,
    )


class ChargebackReport(BaseModel):
    total_cost: float = 0.0
    total_allocated: float = 0.0
    unallocated_cost: float = 0.0
    by_team: dict[str, float] = Field(
        default_factory=dict,
    )
    by_category: dict[str, float] = Field(
        default_factory=dict,
    )
    by_method: dict[str, int] = Field(
        default_factory=dict,
    )
    allocation_accuracy_pct: float = 0.0
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(
        default_factory=time.time,
    )


# --- Engine ---


class CostChargebackEngine:
    """Allocate shared infrastructure costs to teams."""

    def __init__(
        self,
        max_records: int = 500000,
        unallocated_threshold_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._unallocated_threshold_pct = unallocated_threshold_pct
        self._items: list[ChargebackRecord] = []
        self._rules: list[AllocationRule] = []
        logger.info(
            "chargeback_engine.initialized",
            max_records=max_records,
            unallocated_threshold_pct=(unallocated_threshold_pct),
        )

    # -- record --

    def record_cost(
        self,
        team: str,
        department: str = "",
        cost_category: CostCategory = (CostCategory.COMPUTE),
        total_cost: float = 0.0,
        billing_period: str = "",
        **kw: Any,
    ) -> ChargebackRecord:
        """Record a cost entry."""
        record = ChargebackRecord(
            team=team,
            department=department,
            cost_category=cost_category,
            total_cost=total_cost,
            billing_period=billing_period,
            **kw,
        )
        self._items.append(record)
        if len(self._items) > self._max_records:
            self._items = self._items[-self._max_records :]
        logger.info(
            "chargeback_engine.cost_recorded",
            record_id=record.id,
            team=team,
            total_cost=total_cost,
        )
        return record

    # -- get / list --

    def get_record(
        self,
        record_id: str,
    ) -> ChargebackRecord | None:
        """Get a single record by ID."""
        for item in self._items:
            if item.id == record_id:
                return item
        return None

    def list_records(
        self,
        team: str | None = None,
        cost_category: CostCategory | None = None,
        limit: int = 50,
    ) -> list[ChargebackRecord]:
        """List records with optional filters."""
        results = list(self._items)
        if team is not None:
            results = [r for r in results if r.team == team]
        if cost_category is not None:
            results = [r for r in results if r.cost_category == cost_category]
        return results[-limit:]

    # -- rules --

    def create_rule(
        self,
        cost_category: CostCategory = (CostCategory.COMPUTE),
        method: AllocationMethod = (AllocationMethod.PROPORTIONAL_USAGE),
        team: str = "",
        weight: float = 1.0,
        is_active: bool = True,
        **kw: Any,
    ) -> AllocationRule:
        """Create an allocation rule."""
        rule = AllocationRule(
            cost_category=cost_category,
            method=method,
            team=team,
            weight=weight,
            is_active=is_active,
            **kw,
        )
        self._rules.append(rule)
        logger.info(
            "chargeback_engine.rule_created",
            rule_id=rule.id,
            category=cost_category,
            team=team,
        )
        return rule

    # -- domain operations --

    def allocate_costs(
        self,
        billing_period: str,
    ) -> list[ChargebackRecord]:
        """Allocate costs for a billing period."""
        records = [r for r in self._items if r.billing_period == billing_period]
        active_rules = [r for r in self._rules if r.is_active]
        for record in records:
            matching = [
                rl
                for rl in active_rules
                if rl.cost_category == record.cost_category
                and (rl.team == record.team or rl.team == "")
            ]
            if matching:
                total_weight = sum(rl.weight for rl in matching)
                if total_weight > 0:
                    best = max(
                        matching,
                        key=lambda x: x.weight,
                    )
                    share = best.weight / total_weight
                    record.allocated_cost = round(record.total_cost * share, 2)
                    record.allocation_method = best.method
            else:
                # Default: full cost to the team
                record.allocated_cost = record.total_cost
            record.status = ChargebackStatus.CALCULATED
        logger.info(
            "chargeback_engine.costs_allocated",
            period=billing_period,
            count=len(records),
        )
        return records

    def calculate_team_share(
        self,
        team: str,
    ) -> dict[str, Any]:
        """Calculate total cost share for a team."""
        records = [r for r in self._items if r.team == team]
        total = sum(r.total_cost for r in records)
        allocated = sum(r.allocated_cost for r in records)
        by_category: dict[str, float] = {}
        for r in records:
            key = r.cost_category.value
            by_category[key] = by_category.get(key, 0.0) + r.allocated_cost
        return {
            "team": team,
            "total_cost": round(total, 2),
            "allocated_cost": round(allocated, 2),
            "record_count": len(records),
            "by_category": by_category,
        }

    def detect_allocation_anomalies(
        self,
    ) -> list[dict[str, Any]]:
        """Detect anomalies in cost allocation."""
        anomalies: list[dict[str, Any]] = []
        teams: dict[str, list[ChargebackRecord]] = {}
        for r in self._items:
            teams.setdefault(r.team, []).append(r)
        for team, records in sorted(teams.items()):
            total = sum(r.total_cost for r in records)
            allocated = sum(r.allocated_cost for r in records)
            if total > 0:
                diff_pct = abs((allocated - total) / total * 100)
                if diff_pct > self._unallocated_threshold_pct:
                    anomalies.append(
                        {
                            "team": team,
                            "total_cost": round(
                                total,
                                2,
                            ),
                            "allocated_cost": round(
                                allocated,
                                2,
                            ),
                            "diff_pct": round(
                                diff_pct,
                                2,
                            ),
                        }
                    )
        return anomalies

    def compare_periods(
        self,
        period_a: str,
        period_b: str,
    ) -> dict[str, Any]:
        """Compare costs between two periods."""
        recs_a = [r for r in self._items if r.billing_period == period_a]
        recs_b = [r for r in self._items if r.billing_period == period_b]
        total_a = sum(r.total_cost for r in recs_a)
        total_b = sum(r.total_cost for r in recs_b)
        change = round(total_b - total_a, 2)
        change_pct = round(change / total_a * 100, 2) if total_a else 0.0
        return {
            "period_a": period_a,
            "period_b": period_b,
            "total_a": round(total_a, 2),
            "total_b": round(total_b, 2),
            "change": change,
            "change_pct": change_pct,
        }

    # -- report --

    def generate_chargeback_report(
        self,
    ) -> ChargebackReport:
        """Generate a comprehensive chargeback report."""
        total = sum(r.total_cost for r in self._items)
        allocated = sum(r.allocated_cost for r in self._items)
        unallocated = round(total - allocated, 2)
        by_team: dict[str, float] = {}
        for r in self._items:
            by_team[r.team] = by_team.get(r.team, 0.0) + r.allocated_cost
        by_category: dict[str, float] = {}
        for r in self._items:
            key = r.cost_category.value
            by_category[key] = by_category.get(key, 0.0) + r.total_cost
        by_method: dict[str, int] = {}
        for r in self._items:
            key = r.allocation_method.value
            by_method[key] = by_method.get(key, 0) + 1
        accuracy = round(allocated / total * 100, 2) if total else 0.0
        recs = self._build_recommendations(
            total,
            unallocated,
            accuracy,
        )
        return ChargebackReport(
            total_cost=round(total, 2),
            total_allocated=round(allocated, 2),
            unallocated_cost=unallocated,
            by_team=by_team,
            by_category=by_category,
            by_method=by_method,
            allocation_accuracy_pct=accuracy,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all records and rules."""
        count = len(self._items)
        self._items.clear()
        self._rules.clear()
        logger.info(
            "chargeback_engine.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        team_dist: dict[str, int] = {}
        for r in self._items:
            team_dist[r.team] = team_dist.get(r.team, 0) + 1
        return {
            "total_records": len(self._items),
            "total_rules": len(self._rules),
            "unallocated_threshold_pct": (self._unallocated_threshold_pct),
            "team_distribution": team_dist,
        }

    # -- internal helpers --

    def _build_recommendations(
        self,
        total: float,
        unallocated: float,
        accuracy: float,
    ) -> list[str]:
        recs: list[str] = []
        if unallocated > 0 and total > 0:
            pct = round(
                unallocated / total * 100,
                2,
            )
            if pct > self._unallocated_threshold_pct:
                recs.append(f"{pct}% costs unallocated - review rules")
        if accuracy < 90:
            recs.append("Allocation accuracy below 90% - refine allocation rules")
        if not self._rules:
            recs.append("No allocation rules defined - create rules")
        if not recs:
            recs.append("Cost allocation operating normally")
        return recs
