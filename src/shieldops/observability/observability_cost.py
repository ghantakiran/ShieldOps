"""Observability Cost Allocator — monitoring costs per team."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SignalType(StrEnum):
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"
    EVENTS = "events"
    PROFILES = "profiles"


class CostDriver(StrEnum):
    CARDINALITY = "cardinality"
    VOLUME = "volume"
    RETENTION = "retention"
    QUERY_LOAD = "query_load"
    INGESTION_RATE = "ingestion_rate"


class AllocationTrend(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class ObservabilityCostRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_name: str = ""
    signal_type: SignalType = SignalType.METRICS
    cost_driver: CostDriver = CostDriver.VOLUME
    monthly_cost_usd: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CostAllocation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    allocation_name: str = ""
    signal_type: SignalType = SignalType.METRICS
    cost_driver: CostDriver = CostDriver.VOLUME
    allocated_amount_usd: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ObservabilityCostReport(BaseModel):
    total_records: int = 0
    total_allocations: int = 0
    avg_monthly_cost_usd: float = 0.0
    by_signal: dict[str, int] = Field(default_factory=dict)
    by_driver: dict[str, int] = Field(default_factory=dict)
    high_cost_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ObservabilityCostAllocator:
    """Allocate monitoring and logging infrastructure costs per team and service."""

    def __init__(
        self,
        max_records: int = 200000,
        high_cost_threshold: float = 1000.0,
    ) -> None:
        self._max_records = max_records
        self._high_cost_threshold = high_cost_threshold
        self._records: list[ObservabilityCostRecord] = []
        self._allocations: list[CostAllocation] = []
        logger.info(
            "observability_cost.initialized",
            max_records=max_records,
            high_cost_threshold=high_cost_threshold,
        )

    # -- record / get / list ---------------------------------------------

    def record_cost(
        self,
        team_name: str,
        signal_type: SignalType = SignalType.METRICS,
        cost_driver: CostDriver = CostDriver.VOLUME,
        monthly_cost_usd: float = 0.0,
        details: str = "",
    ) -> ObservabilityCostRecord:
        record = ObservabilityCostRecord(
            team_name=team_name,
            signal_type=signal_type,
            cost_driver=cost_driver,
            monthly_cost_usd=monthly_cost_usd,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "observability_cost.cost_recorded",
            record_id=record.id,
            team_name=team_name,
            signal_type=signal_type.value,
        )
        return record

    def get_cost(self, record_id: str) -> ObservabilityCostRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_costs(
        self,
        team_name: str | None = None,
        signal_type: SignalType | None = None,
        limit: int = 50,
    ) -> list[ObservabilityCostRecord]:
        results = list(self._records)
        if team_name is not None:
            results = [r for r in results if r.team_name == team_name]
        if signal_type is not None:
            results = [r for r in results if r.signal_type == signal_type]
        return results[-limit:]

    def add_allocation(
        self,
        allocation_name: str,
        signal_type: SignalType = SignalType.METRICS,
        cost_driver: CostDriver = CostDriver.VOLUME,
        allocated_amount_usd: float = 0.0,
        description: str = "",
    ) -> CostAllocation:
        allocation = CostAllocation(
            allocation_name=allocation_name,
            signal_type=signal_type,
            cost_driver=cost_driver,
            allocated_amount_usd=allocated_amount_usd,
            description=description,
        )
        self._allocations.append(allocation)
        if len(self._allocations) > self._max_records:
            self._allocations = self._allocations[-self._max_records :]
        logger.info(
            "observability_cost.allocation_added",
            allocation_name=allocation_name,
            signal_type=signal_type.value,
        )
        return allocation

    # -- domain operations -----------------------------------------------

    def analyze_team_costs(self, team_name: str) -> dict[str, Any]:
        """Analyze costs for a specific team."""
        records = [r for r in self._records if r.team_name == team_name]
        if not records:
            return {
                "team_name": team_name,
                "status": "no_data",
            }
        total_cost = sum(r.monthly_cost_usd for r in records)
        avg_cost = round(total_cost / len(records), 2)
        return {
            "team_name": team_name,
            "total_monthly_cost_usd": round(total_cost, 2),
            "avg_monthly_cost_usd": avg_cost,
            "record_count": len(records),
            "meets_threshold": avg_cost <= self._high_cost_threshold,
        }

    def identify_high_cost_teams(self) -> list[dict[str, Any]]:
        """Find teams with more than one cost record above threshold."""
        by_team: dict[str, list[float]] = {}
        for r in self._records:
            by_team.setdefault(r.team_name, []).append(r.monthly_cost_usd)
        results: list[dict[str, Any]] = []
        for team, costs in by_team.items():
            high_count = sum(1 for c in costs if c > self._high_cost_threshold)
            if high_count > 1:
                results.append(
                    {
                        "team_name": team,
                        "high_cost_count": high_count,
                        "total_monthly_cost_usd": round(sum(costs), 2),
                        "avg_monthly_cost_usd": round(sum(costs) / len(costs), 2),
                    }
                )
        results.sort(key=lambda x: x["total_monthly_cost_usd"], reverse=True)
        return results

    def rank_by_monthly_cost(self) -> list[dict[str, Any]]:
        """Rank teams by average monthly cost (descending)."""
        by_team: dict[str, list[float]] = {}
        for r in self._records:
            by_team.setdefault(r.team_name, []).append(r.monthly_cost_usd)
        results: list[dict[str, Any]] = []
        for team, costs in by_team.items():
            avg_cost = round(sum(costs) / len(costs), 2)
            results.append(
                {
                    "team_name": team,
                    "avg_monthly_cost_usd": avg_cost,
                    "record_count": len(costs),
                }
            )
        results.sort(key=lambda x: x["avg_monthly_cost_usd"], reverse=True)
        return results

    def detect_cost_trends(self) -> list[dict[str, Any]]:
        """Detect cost trends for teams with more than 3 records."""
        by_team: dict[str, list[ObservabilityCostRecord]] = {}
        for r in self._records:
            by_team.setdefault(r.team_name, []).append(r)
        results: list[dict[str, Any]] = []
        for team, records in by_team.items():
            if len(records) <= 3:
                continue
            mid = len(records) // 2
            older_avg = sum(r.monthly_cost_usd for r in records[:mid]) / mid
            recent_avg = sum(r.monthly_cost_usd for r in records[mid:]) / (len(records) - mid)
            if older_avg == 0:
                trend = AllocationTrend.INSUFFICIENT_DATA
            else:
                change_pct = ((recent_avg - older_avg) / older_avg) * 100
                if change_pct > 20:
                    trend = AllocationTrend.INCREASING
                elif change_pct < -20:
                    trend = AllocationTrend.DECREASING
                elif abs(change_pct) <= 20:
                    trend = AllocationTrend.STABLE
                else:
                    trend = AllocationTrend.VOLATILE
            results.append(
                {
                    "team_name": team,
                    "trend": trend.value,
                    "older_avg_cost": round(older_avg, 2),
                    "recent_avg_cost": round(recent_avg, 2),
                    "record_count": len(records),
                }
            )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ObservabilityCostReport:
        by_signal: dict[str, int] = {}
        by_driver: dict[str, int] = {}
        for r in self._records:
            by_signal[r.signal_type.value] = by_signal.get(r.signal_type.value, 0) + 1
            by_driver[r.cost_driver.value] = by_driver.get(r.cost_driver.value, 0) + 1
        avg_cost = (
            round(
                sum(r.monthly_cost_usd for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_cost = sum(1 for r in self._records if r.monthly_cost_usd > self._high_cost_threshold)
        recs: list[str] = []
        if high_cost > 0:
            recs.append(f"{high_cost} record(s) with monthly cost > ${self._high_cost_threshold}")
        if avg_cost > self._high_cost_threshold and self._records:
            recs.append(
                f"Average monthly cost ${avg_cost} exceeds threshold ${self._high_cost_threshold}"
            )
        if not recs:
            recs.append("Observability costs are within acceptable bounds")
        return ObservabilityCostReport(
            total_records=len(self._records),
            total_allocations=len(self._allocations),
            avg_monthly_cost_usd=avg_cost,
            by_signal=by_signal,
            by_driver=by_driver,
            high_cost_count=high_cost,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._allocations.clear()
        logger.info("observability_cost.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        signal_dist: dict[str, int] = {}
        for r in self._records:
            key = r.signal_type.value
            signal_dist[key] = signal_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_allocations": len(self._allocations),
            "high_cost_threshold": self._high_cost_threshold,
            "signal_distribution": signal_dist,
            "unique_teams": len({r.team_name for r in self._records}),
        }
