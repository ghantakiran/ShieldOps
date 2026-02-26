"""Capacity Demand Modeler — model demand patterns vs capacity supply."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DemandPattern(StrEnum):
    STEADY = "steady"
    CYCLICAL = "cyclical"
    GROWING = "growing"
    DECLINING = "declining"
    SPIKY = "spiky"


class ResourceType(StrEnum):
    COMPUTE = "compute"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    GPU = "gpu"


class SupplyStatus(StrEnum):
    SURPLUS = "surplus"
    BALANCED = "balanced"
    TIGHT = "tight"
    DEFICIT = "deficit"
    CRITICAL = "critical"


# --- Models ---


class DemandRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    resource_type: ResourceType = ResourceType.COMPUTE
    demand_pattern: DemandPattern = DemandPattern.STEADY
    current_usage_pct: float = 0.0
    peak_usage_pct: float = 0.0
    supply_status: SupplyStatus = SupplyStatus.BALANCED
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class SupplyGap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    resource_type: ResourceType = ResourceType.COMPUTE
    gap_pct: float = 0.0
    projected_deficit_date: str = ""
    mitigation: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityDemandReport(BaseModel):
    total_demands: int = 0
    total_supply_gaps: int = 0
    avg_usage_pct: float = 0.0
    by_resource_type: dict[str, float] = Field(default_factory=dict)
    by_supply_status: dict[str, int] = Field(default_factory=dict)
    deficit_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityDemandModeler:
    """Model demand patterns vs capacity supply."""

    def __init__(
        self,
        max_records: int = 200000,
        deficit_threshold_pct: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._deficit_threshold_pct = deficit_threshold_pct
        self._records: list[DemandRecord] = []
        self._supply_gaps: list[SupplyGap] = []
        logger.info(
            "capacity_demand.initialized",
            max_records=max_records,
            deficit_threshold_pct=deficit_threshold_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _usage_to_status(self, usage: float) -> SupplyStatus:
        if usage >= 95:
            return SupplyStatus.CRITICAL
        if usage >= 85:
            return SupplyStatus.DEFICIT
        if usage >= 70:
            return SupplyStatus.TIGHT
        if usage >= 40:
            return SupplyStatus.BALANCED
        return SupplyStatus.SURPLUS

    # -- record / get / list ---------------------------------------------

    def record_demand(
        self,
        service_name: str,
        resource_type: ResourceType = ResourceType.COMPUTE,
        demand_pattern: DemandPattern = DemandPattern.STEADY,
        current_usage_pct: float = 0.0,
        peak_usage_pct: float = 0.0,
        supply_status: SupplyStatus | None = None,
        details: str = "",
    ) -> DemandRecord:
        if supply_status is None:
            supply_status = self._usage_to_status(current_usage_pct)
        record = DemandRecord(
            service_name=service_name,
            resource_type=resource_type,
            demand_pattern=demand_pattern,
            current_usage_pct=current_usage_pct,
            peak_usage_pct=peak_usage_pct,
            supply_status=supply_status,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capacity_demand.demand_recorded",
            record_id=record.id,
            service_name=service_name,
            supply_status=supply_status.value,
        )
        return record

    def get_demand(self, record_id: str) -> DemandRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_demands(
        self,
        service_name: str | None = None,
        resource_type: ResourceType | None = None,
        limit: int = 50,
    ) -> list[DemandRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if resource_type is not None:
            results = [r for r in results if r.resource_type == resource_type]
        return results[-limit:]

    def record_supply_gap(
        self,
        service_name: str,
        resource_type: ResourceType = ResourceType.COMPUTE,
        gap_pct: float = 0.0,
        projected_deficit_date: str = "",
        mitigation: str = "",
    ) -> SupplyGap:
        gap = SupplyGap(
            service_name=service_name,
            resource_type=resource_type,
            gap_pct=gap_pct,
            projected_deficit_date=projected_deficit_date,
            mitigation=mitigation,
        )
        self._supply_gaps.append(gap)
        if len(self._supply_gaps) > self._max_records:
            self._supply_gaps = self._supply_gaps[-self._max_records :]
        logger.info(
            "capacity_demand.supply_gap_recorded",
            service_name=service_name,
            gap_pct=gap_pct,
        )
        return gap

    # -- domain operations -----------------------------------------------

    def analyze_demand_pattern(self, service_name: str) -> dict[str, Any]:
        """Analyze demand pattern for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        latest = records[-1]
        return {
            "service_name": service_name,
            "resource_type": latest.resource_type.value,
            "demand_pattern": latest.demand_pattern.value,
            "current_usage_pct": latest.current_usage_pct,
            "supply_status": latest.supply_status.value,
        }

    def identify_supply_deficits(self) -> list[dict[str, Any]]:
        """Find services with supply deficit or critical status."""
        deficit = {SupplyStatus.DEFICIT, SupplyStatus.CRITICAL}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.supply_status in deficit:
                results.append(
                    {
                        "service_name": r.service_name,
                        "resource_type": r.resource_type.value,
                        "current_usage_pct": r.current_usage_pct,
                        "supply_status": r.supply_status.value,
                        "gap_pct": round(
                            r.current_usage_pct - self._deficit_threshold_pct,
                            2,
                        ),
                    }
                )
        results.sort(key=lambda x: x["current_usage_pct"], reverse=True)
        return results

    def rank_by_peak_usage(self) -> list[dict[str, Any]]:
        """Rank services by peak usage descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "service_name": r.service_name,
                    "peak_usage_pct": r.peak_usage_pct,
                    "current_usage_pct": r.current_usage_pct,
                    "resource_type": r.resource_type.value,
                }
            )
        results.sort(key=lambda x: x["peak_usage_pct"], reverse=True)
        return results

    def forecast_demand_growth(self) -> list[dict[str, Any]]:
        """Forecast demand growth based on pattern."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.demand_pattern == DemandPattern.GROWING:
                growth_rate = round(
                    (r.peak_usage_pct - r.current_usage_pct) / max(r.current_usage_pct, 1) * 100,
                    2,
                )
                results.append(
                    {
                        "service_name": r.service_name,
                        "current_usage_pct": r.current_usage_pct,
                        "peak_usage_pct": r.peak_usage_pct,
                        "growth_rate_pct": growth_rate,
                    }
                )
        results.sort(key=lambda x: x["growth_rate_pct"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CapacityDemandReport:
        by_status: dict[str, int] = {}
        res_usage: dict[str, list[float]] = {}
        for r in self._records:
            by_status[r.supply_status.value] = by_status.get(r.supply_status.value, 0) + 1
            res_usage.setdefault(r.resource_type.value, []).append(r.current_usage_pct)
        by_resource: dict[str, float] = {}
        for res, usages in res_usage.items():
            by_resource[res] = round(sum(usages) / len(usages), 2)
        avg_usage = (
            round(
                sum(r.current_usage_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        deficit = {SupplyStatus.DEFICIT, SupplyStatus.CRITICAL}
        deficit_count = sum(1 for r in self._records if r.supply_status in deficit)
        recs: list[str] = []
        if deficit_count > 0:
            recs.append(f"{deficit_count} service(s) in deficit/critical supply")
        growing = sum(1 for r in self._records if r.demand_pattern == DemandPattern.GROWING)
        if growing > 0:
            recs.append(f"{growing} service(s) with growing demand")
        if not recs:
            recs.append("Capacity demand within acceptable limits")
        return CapacityDemandReport(
            total_demands=len(self._records),
            total_supply_gaps=len(self._supply_gaps),
            avg_usage_pct=avg_usage,
            by_resource_type=by_resource,
            by_supply_status=by_status,
            deficit_count=deficit_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._supply_gaps.clear()
        logger.info("capacity_demand.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        res_dist: dict[str, int] = {}
        for r in self._records:
            key = r.resource_type.value
            res_dist[key] = res_dist.get(key, 0) + 1
        return {
            "total_demands": len(self._records),
            "total_supply_gaps": len(self._supply_gaps),
            "deficit_threshold_pct": self._deficit_threshold_pct,
            "resource_distribution": res_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
