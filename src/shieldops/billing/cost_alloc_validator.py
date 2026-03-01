"""Cost Allocation Validator — validate allocations, detect variance, track accuracy."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AllocationType(StrEnum):
    DIRECT = "direct"
    SHARED = "shared"
    PROPORTIONAL = "proportional"
    FIXED = "fixed"
    USAGE_BASED = "usage_based"


class AllocationStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    PENDING_REVIEW = "pending_review"
    ADJUSTED = "adjusted"
    DISPUTED = "disputed"


class CostCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    LICENSE = "license"
    SUPPORT = "support"


# --- Models ---


class AllocationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    allocation_type: AllocationType = AllocationType.DIRECT
    status: AllocationStatus = AllocationStatus.PENDING_REVIEW
    cost_category: CostCategory = CostCategory.COMPUTE
    allocated_amount: float = 0.0
    actual_amount: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AllocationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_pattern: str = ""
    allocation_type: AllocationType = AllocationType.DIRECT
    cost_category: CostCategory = CostCategory.COMPUTE
    allocation_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostAllocationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    valid_allocations: int = 0
    variance_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    high_variance: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostAllocationValidator:
    """Validate cost allocations, detect variance, track allocation accuracy."""

    def __init__(
        self,
        max_records: int = 200000,
        max_variance_pct: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._max_variance_pct = max_variance_pct
        self._records: list[AllocationRecord] = []
        self._rules: list[AllocationRule] = []
        logger.info(
            "cost_alloc_validator.initialized",
            max_records=max_records,
            max_variance_pct=max_variance_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_allocation(
        self,
        service_name: str,
        allocation_type: AllocationType = AllocationType.DIRECT,
        status: AllocationStatus = AllocationStatus.PENDING_REVIEW,
        cost_category: CostCategory = CostCategory.COMPUTE,
        allocated_amount: float = 0.0,
        actual_amount: float = 0.0,
        team: str = "",
    ) -> AllocationRecord:
        record = AllocationRecord(
            service_name=service_name,
            allocation_type=allocation_type,
            status=status,
            cost_category=cost_category,
            allocated_amount=allocated_amount,
            actual_amount=actual_amount,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_alloc_validator.allocation_recorded",
            record_id=record.id,
            service_name=service_name,
            allocation_type=allocation_type.value,
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
        allocation_type: AllocationType | None = None,
        status: AllocationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AllocationRecord]:
        results = list(self._records)
        if allocation_type is not None:
            results = [r for r in results if r.allocation_type == allocation_type]
        if status is not None:
            results = [r for r in results if r.status == status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        service_pattern: str,
        allocation_type: AllocationType = AllocationType.DIRECT,
        cost_category: CostCategory = CostCategory.COMPUTE,
        allocation_pct: float = 0.0,
        description: str = "",
    ) -> AllocationRule:
        rule = AllocationRule(
            service_pattern=service_pattern,
            allocation_type=allocation_type,
            cost_category=cost_category,
            allocation_pct=allocation_pct,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "cost_alloc_validator.rule_added",
            service_pattern=service_pattern,
            allocation_type=allocation_type.value,
            allocation_pct=allocation_pct,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_allocation_accuracy(self) -> dict[str, Any]:
        """Group by allocation_type; return count and avg variance per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.allocation_type.value
            if r.allocated_amount != 0:
                variance = abs((r.actual_amount - r.allocated_amount) / r.allocated_amount * 100)
            else:
                variance = 0.0
            type_data.setdefault(key, []).append(variance)
        result: dict[str, Any] = {}
        for alloc_type, variances in type_data.items():
            result[alloc_type] = {
                "count": len(variances),
                "avg_variance_pct": round(sum(variances) / len(variances), 2),
            }
        return result

    def identify_high_variance(self) -> list[dict[str, Any]]:
        """Return records where variance exceeds max_variance_pct."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.allocated_amount != 0:
                variance = abs((r.actual_amount - r.allocated_amount) / r.allocated_amount * 100)
            else:
                variance = 0.0
            if variance > self._max_variance_pct:
                results.append(
                    {
                        "record_id": r.id,
                        "service_name": r.service_name,
                        "variance_pct": round(variance, 2),
                        "allocation_type": r.allocation_type.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_variance(self) -> list[dict[str, Any]]:
        """Group by team, total records, sort descending by count."""
        team_counts: dict[str, int] = {}
        for r in self._records:
            team_counts[r.team] = team_counts.get(r.team, 0) + 1
        results: list[dict[str, Any]] = []
        for team, count in team_counts.items():
            results.append(
                {
                    "team": team,
                    "allocation_count": count,
                }
            )
        results.sort(key=lambda x: x["allocation_count"], reverse=True)
        return results

    def detect_allocation_trends(self) -> dict[str, Any]:
        """Split-half on allocation_pct; delta threshold 5.0."""
        if len(self._rules) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        pcts = [rule.allocation_pct for rule in self._rules]
        mid = len(pcts) // 2
        first_half = pcts[:mid]
        second_half = pcts[mid:]
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

    def generate_report(self) -> CostAllocationReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_type[r.allocation_type.value] = by_type.get(r.allocation_type.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_category[r.cost_category.value] = by_category.get(r.cost_category.value, 0) + 1
        valid_count = sum(1 for r in self._records if r.status == AllocationStatus.VALID)
        total_allocated = sum(r.allocated_amount for r in self._records)
        total_actual = sum(r.actual_amount for r in self._records)
        variance_pct = (
            round(
                abs(total_actual - total_allocated) / total_allocated * 100,
                2,
            )
            if total_allocated
            else 0.0
        )
        high_var = self.identify_high_variance()
        high_variance_ids = [hv["service_name"] for hv in high_var[:5]]
        recs: list[str] = []
        if variance_pct > self._max_variance_pct:
            recs.append(
                f"Overall variance {variance_pct}% exceeds threshold ({self._max_variance_pct}%)"
            )
        if len(high_var) > 0:
            recs.append(f"{len(high_var)} high-variance allocation(s) detected — review cost rules")
        if not recs:
            recs.append("Allocation accuracy is acceptable")
        return CostAllocationReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            valid_allocations=valid_count,
            variance_pct=variance_pct,
            by_type=by_type,
            by_status=by_status,
            by_category=by_category,
            high_variance=high_variance_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("cost_alloc_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.allocation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "max_variance_pct": self._max_variance_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service_name for r in self._records}),
        }
