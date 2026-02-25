"""Cost Unit Economics Engine — compute cost per unit of business value."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class UnitType(StrEnum):
    PER_REQUEST = "per_request"
    PER_USER = "per_user"
    PER_TRANSACTION = "per_transaction"
    PER_GB_PROCESSED = "per_gb_processed"
    PER_EVENT = "per_event"


class EfficiencyTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class CostTier(StrEnum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


# --- Models ---


class UnitCostRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    unit_type: UnitType = UnitType.PER_REQUEST
    total_cost: float = 0.0
    total_units: int = 0
    cost_per_unit: float = 0.0
    tier: CostTier = CostTier.MODERATE
    team: str = ""
    period: str = ""
    created_at: float = Field(default_factory=time.time)


class UnitBenchmark(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    unit_type: UnitType = UnitType.PER_REQUEST
    avg_cost_per_unit: float = 0.0
    p50_cost: float = 0.0
    p90_cost: float = 0.0
    industry_avg: float = 0.0
    sample_count: int = 0
    created_at: float = Field(default_factory=time.time)


class UnitEconomicsReport(BaseModel):
    total_records: int = 0
    avg_cost_per_unit: float = 0.0
    by_unit_type: dict[str, float] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    expensive_services: list[str] = Field(default_factory=list)
    trend: str = ""
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostUnitEconomicsEngine:
    """Compute cost per unit of business value for services."""

    def __init__(
        self,
        max_records: int = 200000,
        high_cost_threshold: float = 0.01,
    ) -> None:
        self._max_records = max_records
        self._high_cost_threshold = high_cost_threshold
        self._records: list[UnitCostRecord] = []
        self._benchmarks: list[UnitBenchmark] = []
        logger.info(
            "unit_economics.initialized",
            max_records=max_records,
            high_cost_threshold=high_cost_threshold,
        )

    # -- record / get / list -----------------------------------------

    def record_unit_cost(
        self,
        service_name: str,
        unit_type: UnitType = UnitType.PER_REQUEST,
        total_cost: float = 0.0,
        total_units: int = 0,
        team: str = "",
        period: str = "",
    ) -> UnitCostRecord:
        """Record a unit cost entry and compute cost_per_unit and tier."""
        cost_per_unit = round(total_cost / total_units, 6) if total_units > 0 else 0.0
        tier = self._classify_tier(cost_per_unit)
        record = UnitCostRecord(
            service_name=service_name,
            unit_type=unit_type,
            total_cost=total_cost,
            total_units=total_units,
            cost_per_unit=cost_per_unit,
            tier=tier,
            team=team,
            period=period,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "unit_economics.cost_recorded",
            record_id=record.id,
            service_name=service_name,
            cost_per_unit=cost_per_unit,
            tier=tier.value,
        )
        return record

    def get_record(self, record_id: str) -> UnitCostRecord | None:
        """Get a single unit cost record by ID."""
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        service_name: str | None = None,
        unit_type: UnitType | None = None,
        limit: int = 50,
    ) -> list[UnitCostRecord]:
        """List unit cost records with optional filters."""
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if unit_type is not None:
            results = [r for r in results if r.unit_type == unit_type]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def compute_cost_per_unit(
        self,
        total_cost: float,
        total_units: int,
    ) -> dict[str, Any]:
        """Standalone cost-per-unit computation."""
        cost_per_unit = round(total_cost / total_units, 6) if total_units > 0 else 0.0
        tier = self._classify_tier(cost_per_unit)
        return {
            "total_cost": total_cost,
            "total_units": total_units,
            "cost_per_unit": cost_per_unit,
            "tier": tier.value,
            "above_threshold": cost_per_unit > self._high_cost_threshold,
        }

    def create_benchmark(
        self,
        service_name: str,
        unit_type: UnitType = UnitType.PER_REQUEST,
    ) -> UnitBenchmark:
        """Create a benchmark from historical records for a service."""
        records = [
            r for r in self._records if r.service_name == service_name and r.unit_type == unit_type
        ]
        costs = sorted([r.cost_per_unit for r in records]) if records else []
        sample_count = len(costs)
        avg_cost = round(sum(costs) / len(costs), 6) if costs else 0.0
        p50 = costs[len(costs) // 2] if costs else 0.0
        p90_idx = int(len(costs) * 0.9) if costs else 0
        p90 = costs[min(p90_idx, len(costs) - 1)] if costs else 0.0
        benchmark = UnitBenchmark(
            service_name=service_name,
            unit_type=unit_type,
            avg_cost_per_unit=avg_cost,
            p50_cost=round(p50, 6),
            p90_cost=round(p90, 6),
            industry_avg=round(avg_cost * 1.2, 6),
            sample_count=sample_count,
        )
        self._benchmarks.append(benchmark)
        logger.info(
            "unit_economics.benchmark_created",
            benchmark_id=benchmark.id,
            service_name=service_name,
            sample_count=sample_count,
        )
        return benchmark

    def identify_expensive_services(
        self,
        threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Identify services with cost_per_unit above threshold."""
        cutoff = threshold if threshold is not None else self._high_cost_threshold
        by_service: dict[str, list[float]] = {}
        for r in self._records:
            by_service.setdefault(r.service_name, []).append(r.cost_per_unit)
        results: list[dict[str, Any]] = []
        for service, costs in by_service.items():
            avg_cost = round(sum(costs) / len(costs), 6)
            if avg_cost > cutoff:
                results.append(
                    {
                        "service_name": service,
                        "avg_cost_per_unit": avg_cost,
                        "sample_count": len(costs),
                        "tier": self._classify_tier(avg_cost).value,
                    }
                )
        results.sort(key=lambda x: x["avg_cost_per_unit"], reverse=True)
        return results

    def compute_efficiency_trend(
        self,
        service_name: str,
    ) -> dict[str, Any]:
        """Compare recent vs older records to determine trend."""
        records = [r for r in self._records if r.service_name == service_name]
        if len(records) < 2:
            return {
                "service_name": service_name,
                "trend": EfficiencyTrend.UNKNOWN.value,
                "reason": "Insufficient data",
            }
        mid = len(records) // 2
        older = records[:mid]
        recent = records[mid:]
        older_avg = sum(r.cost_per_unit for r in older) / len(older)
        recent_avg = sum(r.cost_per_unit for r in recent) / len(recent)
        if older_avg == 0:
            trend = EfficiencyTrend.UNKNOWN
        else:
            change_pct = ((recent_avg - older_avg) / older_avg) * 100
            if change_pct < -10:
                trend = EfficiencyTrend.IMPROVING
            elif change_pct > 10:
                trend = EfficiencyTrend.DEGRADING
            elif abs(change_pct) <= 10:
                trend = EfficiencyTrend.STABLE
            else:
                trend = EfficiencyTrend.VOLATILE
        return {
            "service_name": service_name,
            "trend": trend.value,
            "older_avg_cost": round(older_avg, 6),
            "recent_avg_cost": round(recent_avg, 6),
            "sample_count": len(records),
        }

    def rank_by_cost_efficiency(self) -> list[dict[str, Any]]:
        """Rank all services by cost_per_unit (most expensive first)."""
        by_service: dict[str, list[float]] = {}
        for r in self._records:
            by_service.setdefault(r.service_name, []).append(r.cost_per_unit)
        results: list[dict[str, Any]] = []
        for service, costs in by_service.items():
            avg_cost = round(sum(costs) / len(costs), 6)
            results.append(
                {
                    "service_name": service,
                    "avg_cost_per_unit": avg_cost,
                    "record_count": len(costs),
                    "tier": self._classify_tier(avg_cost).value,
                }
            )
        results.sort(key=lambda x: x["avg_cost_per_unit"], reverse=True)
        return results

    # -- report / stats ----------------------------------------------

    def generate_economics_report(self) -> UnitEconomicsReport:
        """Generate a comprehensive unit economics report."""
        by_unit_type: dict[str, float] = {}
        by_tier: dict[str, int] = {}
        costs: list[float] = []
        for r in self._records:
            costs.append(r.cost_per_unit)
            by_tier[r.tier.value] = by_tier.get(r.tier.value, 0) + 1
            type_key = r.unit_type.value
            by_unit_type.setdefault(type_key, 0.0)
            by_unit_type[type_key] = round(
                by_unit_type[type_key] + r.cost_per_unit,
                6,
            )
        avg_cost = round(sum(costs) / len(costs), 6) if costs else 0.0
        # Average per unit type
        type_counts: dict[str, int] = {}
        for r in self._records:
            type_counts[r.unit_type.value] = type_counts.get(r.unit_type.value, 0) + 1
        for key in by_unit_type:
            count = type_counts.get(key, 1)
            by_unit_type[key] = round(by_unit_type[key] / count, 6)
        expensive = self.identify_expensive_services()
        expensive_names = [e["service_name"] for e in expensive[:5]]
        # Overall trend
        all_costs = [r.cost_per_unit for r in self._records]
        if len(all_costs) >= 4:
            mid = len(all_costs) // 2
            older_avg = sum(all_costs[:mid]) / mid
            recent_avg = sum(all_costs[mid:]) / (len(all_costs) - mid)
            if older_avg > 0 and (recent_avg - older_avg) / older_avg < -0.1:
                trend = EfficiencyTrend.IMPROVING.value
            elif older_avg > 0 and (recent_avg - older_avg) / older_avg > 0.1:
                trend = EfficiencyTrend.DEGRADING.value
            else:
                trend = EfficiencyTrend.STABLE.value
        else:
            trend = EfficiencyTrend.UNKNOWN.value
        recs = self._build_recommendations(expensive, avg_cost, trend)
        return UnitEconomicsReport(
            total_records=len(self._records),
            avg_cost_per_unit=avg_cost,
            by_unit_type=by_unit_type,
            by_tier=by_tier,
            expensive_services=expensive_names,
            trend=trend,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all stored records and benchmarks."""
        self._records.clear()
        self._benchmarks.clear()
        logger.info("unit_economics.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_benchmarks": len(self._benchmarks),
            "high_cost_threshold": self._high_cost_threshold,
            "tier_distribution": tier_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }

    # -- internal helpers --------------------------------------------

    def _classify_tier(self, cost_per_unit: float) -> CostTier:
        """Classify cost tier based on threshold."""
        if cost_per_unit <= self._high_cost_threshold * 0.1:
            return CostTier.VERY_LOW
        if cost_per_unit <= self._high_cost_threshold * 0.5:
            return CostTier.LOW
        if cost_per_unit <= self._high_cost_threshold:
            return CostTier.MODERATE
        if cost_per_unit <= self._high_cost_threshold * 5:
            return CostTier.HIGH
        return CostTier.VERY_HIGH

    def _build_recommendations(
        self,
        expensive: list[dict[str, Any]],
        avg_cost: float,
        trend: str,
    ) -> list[str]:
        """Build recommendations from unit economics analysis."""
        recs: list[str] = []
        if expensive:
            recs.append(f"{len(expensive)} service(s) above cost threshold — review efficiency")
        if trend == EfficiencyTrend.DEGRADING.value:
            recs.append("Unit costs trending upward — investigate cost drivers")
        if avg_cost > self._high_cost_threshold:
            recs.append(
                f"Average cost ${avg_cost:.6f}/unit exceeds"
                f" ${self._high_cost_threshold:.6f} threshold"
            )
        if not recs:
            recs.append("Unit economics are within acceptable bounds")
        return recs
